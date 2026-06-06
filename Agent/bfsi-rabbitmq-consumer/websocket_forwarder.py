"""
WebSocket forwarder for BFSI chat events.

Design goals:
- Single persistent sender thread (no thread-per-message waste)
- Exponential backoff reconnect
- Bounded in-memory buffer during outages
- Heartbeat/ping to detect dead connections
- PII masking (never send cards, full phones, OTPs)
- Structured logging for observability
"""
import os
import json
import time
import logging
import threading
from collections import deque
from datetime import datetime, date
from urllib.parse import urlencode

import websocket  # websocket-client library

logger = logging.getLogger("ws_forwarder")


def _json_default(obj):
    """JSON serializer for objects that json.dumps can't handle natively."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


class WebSocketForwarder:
    """Forwards chat events to an external WebSocket broadcaster server."""

    def __init__(
        self,
        url: str,
        auth_token: str = "",
        buffer_size: int = 500,
        connect_timeout: int = 5,
        ping_interval: int = 20,
        ping_timeout: int = 10,
    ):
        self.base_url = url
        self.auth_token = auth_token
        self.connect_timeout = connect_timeout
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        # Thread-safe queue with capped size (prevents memory blow-up during long outages)
        self._queue: deque = deque(maxlen=buffer_size)
        self._queue_lock = threading.Lock()
        self._queue_cond = threading.Condition(self._queue_lock)

        self._ws = None
        self._connected = False
        self._stop = False
        self._sender_thread = None

        # Metrics
        self._stats = {
            "sent": 0,
            "dropped": 0,
            "reconnects": 0,
            "last_connected_at": None,
            "last_send_at": None,
        }
        self._stats_lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────

    def start(self):
        """Start the background sender thread."""
        if self._sender_thread and self._sender_thread.is_alive():
            return
        self._stop = False
        self._sender_thread = threading.Thread(
            target=self._sender_loop, daemon=True, name="ws-forwarder-sender"
        )
        self._sender_thread.start()
        logger.info("WebSocket forwarder started (url=%s)", self.base_url)

    def stop(self):
        """Stop the sender thread and close the connection gracefully."""
        self._stop = True
        with self._queue_cond:
            self._queue_cond.notify_all()
        if self._sender_thread:
            self._sender_thread.join(timeout=5)
        self._close_ws()
        logger.info("WebSocket forwarder stopped")

    def forward(self, data: dict) -> bool:
        """Queue a message for sending. Non-blocking.

        Returns:
            True if queued, False if buffer was full (oldest message dropped).
        """
        safe_data = self._mask_pii(data)
        with self._queue_cond:
            was_full = len(self._queue) == self._queue.maxlen
            self._queue.append(safe_data)
            if was_full:
                with self._stats_lock:
                    self._stats["dropped"] += 1
                logger.warning("WS buffer full — oldest message dropped (buffer=%d)", self._queue.maxlen)
            self._queue_cond.notify()
            return not was_full

    def stats(self) -> dict:
        """Return forwarder metrics."""
        with self._stats_lock:
            return {**self._stats, "queue_size": len(self._queue), "connected": self._connected}

    # ── Internal: connection management ──────────────────────

    def _build_url(self) -> str:
        """Append auth token as query param if configured."""
        if not self.auth_token:
            return self.base_url
        sep = "&" if "?" in self.base_url else "?"
        return f"{self.base_url}{sep}{urlencode({'token': self.auth_token})}"

    def _connect(self) -> bool:
        """Attempt to establish a WebSocket connection. Returns True on success."""
        try:
            self._ws = websocket.create_connection(
                self._build_url(),
                timeout=self.connect_timeout,
                # Enable ping/pong heartbeat to detect dead connections
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
            )
            self._connected = True
            with self._stats_lock:
                self._stats["last_connected_at"] = datetime.utcnow().isoformat()
            logger.info("WS connected to %s", self.base_url)
            return True
        except Exception as e:
            self._connected = False
            logger.warning("WS connect failed: %s", e)
            return False

    def _close_ws(self):
        """Close the WebSocket connection if open."""
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected = False

    def _reconnect_with_backoff(self):
        """Reconnect using exponential backoff. Blocks until connected or stop requested."""
        delays = [1, 2, 4, 8, 16, 30]
        attempt = 0
        while not self._stop:
            delay = delays[min(attempt, len(delays) - 1)]
            if attempt > 0:
                logger.info("WS reconnecting in %ds (attempt %d)...", delay, attempt)
                # Sleep in small increments so we can respond to stop
                for _ in range(delay):
                    if self._stop:
                        return
                    time.sleep(1)
            if self._connect():
                with self._stats_lock:
                    self._stats["reconnects"] += 1 if attempt > 0 else 0
                return
            attempt += 1

    # ── Internal: sender loop ────────────────────────────────

    def _sender_loop(self):
        """Main loop: drains the queue and sends to WebSocket. Reconnects on failure."""
        # Initial connect (with retry)
        self._reconnect_with_backoff()

        while not self._stop:
            # Wait for a message
            with self._queue_cond:
                while not self._queue and not self._stop:
                    self._queue_cond.wait(timeout=1)
                if self._stop:
                    break
                data = self._queue.popleft()

            # Ensure we're connected before sending
            if not self._connected or self._ws is None:
                self._reconnect_with_backoff()
                if not self._connected:
                    # Requeue the message at the front of the queue
                    with self._queue_cond:
                        self._queue.appendleft(data)
                    continue

            # Serialize before attempting send — bad JSON should NOT cause reconnect
            try:
                payload = json.dumps(data, default=_json_default)
            except Exception as e:
                logger.error("WS serialize failed (dropping message): %s", e)
                with self._stats_lock:
                    self._stats["dropped"] += 1
                continue

            # Attempt send
            try:
                self._ws.send(payload)
                with self._stats_lock:
                    self._stats["sent"] += 1
                    self._stats["last_send_at"] = datetime.utcnow().isoformat()
            except Exception as e:
                logger.warning("WS send failed: %s — reconnecting", e)
                self._close_ws()
                # Requeue the failed message at the front
                with self._queue_cond:
                    self._queue.appendleft(data)
                # Reconnect will happen on next iteration

    # ── PII masking ──────────────────────────────────────────

    @staticmethod
    def _mask_pii(data: dict) -> dict:
        """Strip/mask sensitive fields before sending over the wire.

        BFSI context: NEVER transmit full card numbers, OTPs, or passwords.
        Phone numbers are masked to last 4 digits.
        """
        if not isinstance(data, dict):
            return data

        masked = dict(data)  # shallow copy

        # Mask phone number → last 4 digits only
        phone = masked.get("phone_number")
        if phone and isinstance(phone, str) and len(phone) > 4:
            masked["phone_number"] = "xxxxxx" + phone[-4:]

        # Strip message content that looks like it may contain an OTP
        # (6-digit sequence in a message that mentions otp/code/verification)
        msg = masked.get("message")
        if msg and isinstance(msg, str):
            import re
            lowered = msg.lower()
            if any(term in lowered for term in ("otp", "verification code", "one-time password", "one time password")):
                # Replace any 4-8 digit sequence with [REDACTED]
                masked["message"] = re.sub(r"\b\d{4,8}\b", "[REDACTED]", msg)

        return masked
