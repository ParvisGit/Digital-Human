"""
BFSI WebSocket broadcaster.

Accepts two types of WebSocket connections:

1. Publisher connections (authenticated with PUBLISHER_TOKEN):
   - The consumer/middleware sends chat events here
   - Every received message is fan-out broadcast to all subscribers

2. Subscriber connections (authenticated with SUBSCRIBER_TOKEN):
   - Dashboards, supervisor consoles, QA tools, etc.
   - Receive every message forwarded from the publisher

Authentication is via `?token=...` query param. In production, use `wss://`
with proper TLS certificates (handled at reverse proxy / load balancer layer).

Compatible with websockets library >= 11.0 (uses ws.request.path).
"""
import os
import logging
import asyncio
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
import websockets

# ── Config ───────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

WS_HOST           = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT           = int(os.getenv("WS_PORT", "8765"))
PUBLISHER_TOKEN   = os.getenv("PUBLISHER_TOKEN", "change-me-in-production")
SUBSCRIBER_TOKEN  = os.getenv("SUBSCRIBER_TOKEN", "change-me-in-production")
PING_INTERVAL     = int(os.getenv("PING_INTERVAL", "20"))
PING_TIMEOUT      = int(os.getenv("PING_TIMEOUT", "10"))
MAX_MESSAGE_SIZE  = int(os.getenv("MAX_MESSAGE_SIZE", str(64 * 1024)))
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO")

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ws_server")

# ── Connection state ─────────────────────────────────────────────────
_subscribers: set = set()
_subscribers_lock = asyncio.Lock()

_stats = {"messages_received": 0, "messages_broadcast": 0, "broadcast_failures": 0}


# ── Path helpers ─────────────────────────────────────────────────────

def _get_path(ws) -> str:
    """Extract the full request path (with query string).

    Works across websockets library versions 11/12/13/14/15.
    """
    # websockets >= 11: ws.request.path holds the full path including query
    if hasattr(ws, "request") and ws.request is not None:
        path = getattr(ws.request, "path", None)
        if path:
            return path
    # Fallback for older versions
    return getattr(ws, "path", "") or ""


def _extract_token(path: str) -> str:
    try:
        query = parse_qs(urlparse(path).query)
        return query.get("token", [""])[0]
    except Exception:
        return ""


def _authenticate(path: str):
    token = _extract_token(path)
    if token == PUBLISHER_TOKEN:
        return "publisher"
    if token == SUBSCRIBER_TOKEN:
        return "subscriber"
    return None


# ── Handlers ─────────────────────────────────────────────────────────

async def _handle_publisher(ws):
    client_addr = ws.remote_address
    logger.info("PUB connected from %s", client_addr)
    try:
        async for message in ws:
            _stats["messages_received"] += 1
            logger.debug("PUB msg received (len=%d)", len(message) if isinstance(message, (str, bytes)) else 0)
            await _broadcast(message)
    except websockets.ConnectionClosed as e:
        logger.info("PUB disconnected %s (code=%s)", client_addr, e.code)
    except Exception as e:
        logger.exception("PUB error from %s: %s", client_addr, e)


async def _handle_subscriber(ws):
    client_addr = ws.remote_address
    async with _subscribers_lock:
        _subscribers.add(ws)
    logger.info("SUB connected from %s (total=%d)", client_addr, len(_subscribers))

    try:
        async for _ in ws:
            pass
    except websockets.ConnectionClosed as e:
        logger.info("SUB disconnected %s (code=%s)", client_addr, e.code)
    except Exception as e:
        logger.exception("SUB error from %s: %s", client_addr, e)
    finally:
        async with _subscribers_lock:
            _subscribers.discard(ws)
        logger.info("SUB removed %s (total=%d)", client_addr, len(_subscribers))


async def _broadcast(message) -> None:
    async with _subscribers_lock:
        targets = list(_subscribers)

    if not targets:
        logger.debug("broadcast skipped — no subscribers")
        return

    results = await asyncio.gather(
        *(_safe_send(ws, message) for ws in targets),
        return_exceptions=True,
    )
    ok = sum(1 for r in results if r is True)
    _stats["messages_broadcast"] += ok
    _stats["broadcast_failures"] += (len(results) - ok)
    logger.debug("broadcast sent to %d/%d subscribers", ok, len(targets))


async def _safe_send(ws, message) -> bool:
    try:
        await ws.send(message)
        return True
    except Exception as e:
        logger.debug("broadcast send failed: %s", e)
        async with _subscribers_lock:
            _subscribers.discard(ws)
        return False


# ── Main router ──────────────────────────────────────────────────────

async def router(ws):
    """Authenticate and dispatch the connection by role."""
    path = _get_path(ws)
    role = _authenticate(path)

    if role is None:
        logger.warning("AUTH_FAIL from %s (path=%s)", ws.remote_address, path)
        await ws.close(code=1008, reason="authentication required")
        return

    if role == "publisher":
        await _handle_publisher(ws)
    else:
        await _handle_subscriber(ws)


# ── Periodic stats reporter ──────────────────────────────────────────

async def _report_stats():
    while True:
        await asyncio.sleep(60)
        async with _subscribers_lock:
            subs = len(_subscribers)
        logger.info(
            "STATS|subscribers=%d|received=%d|broadcast=%d|failures=%d",
            subs, _stats["messages_received"], _stats["messages_broadcast"], _stats["broadcast_failures"],
        )


# ── Entrypoint ───────────────────────────────────────────────────────

async def main():
    logger.info("=" * 60)
    logger.info("BFSI WebSocket Broadcaster starting")
    logger.info("Listening on ws://%s:%d", WS_HOST, WS_PORT)
    logger.info("Ping interval=%ds timeout=%ds", PING_INTERVAL, PING_TIMEOUT)
    logger.info("=" * 60)

    async with websockets.serve(
        router,
        host=WS_HOST,
        port=WS_PORT,
        ping_interval=PING_INTERVAL,
        ping_timeout=PING_TIMEOUT,
        max_size=MAX_MESSAGE_SIZE,
    ):
        asyncio.create_task(_report_stats())
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
