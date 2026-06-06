# BFSI RabbitMQ Consumer (Middleware)

Consumes chat events from RabbitMQ and does two things:

1. **Persists to MongoDB** (`chat_logs` collection) for durable storage.
2. **Forwards to a WebSocket broadcaster** for real-time fan-out to dashboards/monitors.

## Architecture

```
Bot (gRPC) → RabbitMQ → THIS CONSUMER ─┬→ MongoDB (persistent)
                                       └→ WebSocket Server → subscribers
```

## Features

- **Auto-reconnect** to RabbitMQ on disconnect (5s backoff loop)
- **Persistent sender thread** for WebSocket — no thread-per-message waste
- **Exponential backoff** on WebSocket reconnect (1s → 2s → ... → 30s cap)
- **Bounded in-memory buffer** (500 msgs default) during WebSocket outages
- **Heartbeat (ping/pong)** to detect dead WebSocket connections
- **PII masking** before WebSocket send (phone → last 4 digits, OTPs redacted)
- **Retry limit** on message processing — drops poison messages after N attempts

## Setup

```bash
cd /home/koushik/Agent/bfsi-rabbitmq-consumer
cp .env.example .env
# edit .env with actual values
pip install -r requirements.txt
```

## Config (`.env`)

| Variable | Description |
|----------|-------------|
| `RABBITMQ_HOST/PORT/QUEUE` | RabbitMQ connection |
| `MONGO_URI/DB/COLLECTION` | MongoDB destination |
| `WS_ENABLED` | `true` to forward; `false` to disable (MongoDB only) |
| `WS_URL` | `ws://...` (use `wss://` in production) |
| `WS_AUTH_TOKEN` | Must match `PUBLISHER_TOKEN` on the server |
| `WS_BUFFER_SIZE` | Buffer capacity during outages (default 500) |
| `MAX_REDELIVER_COUNT` | Retries before giving up on poison messages |

## Run

Foreground:
```bash
python3 consumer.py
```

Via pm2:
```bash
pm2 start ecosystem.config.js
pm2 save
```

## PII Masking

The forwarder strips/masks sensitive fields before sending over WebSocket:

| Field | Original | Transmitted |
|-------|----------|-------------|
| `phone_number` | `9164110263` | `xxxxxx0263` |
| `message` (if contains "otp"/"code") | `Your code is 482931` | `Your code is [REDACTED]` |

MongoDB still stores full data for audit/compliance. Only the WebSocket stream is masked.

## Testing end-to-end

1. Start WebSocket server: `cd ../bfsi-websocket-server && python3 server.py`
2. Start test subscriber: `python3 ../bfsi-websocket-server/test_subscriber.py`
3. Start this consumer: `python3 consumer.py`
4. Trigger a chat in the bot → messages should appear in both MongoDB and the subscriber terminal.

## Operational notes

- If WebSocket server is down, messages queue up in the buffer (up to `WS_BUFFER_SIZE`).
  Oldest messages are dropped if the buffer fills.
- MongoDB writes are **NOT** affected by WebSocket outages — storage is independent.
- Set `WS_ENABLED=false` to run with only MongoDB (e.g., during WebSocket maintenance).
