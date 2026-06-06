# BFSI WebSocket Broadcaster

Real-time fan-out broadcaster for chat events. Receives messages from the middleware
(RabbitMQ consumer) and broadcasts to subscribers (dashboards, supervisor consoles,
QA monitors).

## Architecture

```
Bot → RabbitMQ → Consumer (middleware) → MongoDB (persistent storage)
                       ↓
                  WebSocket Publisher
                       ↓
                 This Server (fan-out)
                       ↓
       ┌───────────┬──────────┬──────────┐
   Dashboard    Supervisor    QA       Analytics
```

## Roles

Connections are authenticated with a token (`?token=...` query param).

| Role       | Token                | What they do            |
|------------|----------------------|-------------------------|
| Publisher  | `PUBLISHER_TOKEN`    | Sends events (consumer) |
| Subscriber | `SUBSCRIBER_TOKEN`   | Receives broadcasts     |

Mismatched/missing tokens get a 1008 close code.

## Setup

```bash
cd /home/koushik/Agent/bfsi-websocket-server
cp .env.example .env
# edit .env with real tokens for production
pip install -r requirements.txt
```

## Run

Foreground (development):
```bash
python3 server.py
```

Via pm2 (production):
```bash
pm2 start ecosystem.config.js
pm2 save
```

## Test it works

In one terminal, run the test subscriber:
```bash
python3 test_subscriber.py
```

In another terminal, send a message as a publisher (simulating the consumer):
```bash
python3 -c "
import asyncio, json, websockets, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path('.env'))
async def send():
    token = os.getenv('PUBLISHER_TOKEN')
    async with websockets.connect(f'ws://localhost:8765?token={token}') as ws:
        await ws.send(json.dumps({'test': 'hello world', 'session_id': 'demo'}))
asyncio.run(send())
"
```

You should see the message print in the subscriber terminal.

## Security Notes

- **Production MUST use `wss://`** with TLS. Terminate TLS at your reverse proxy
  (nginx, HAProxy) and forward to this server over plaintext on the internal network.
- Change both tokens in `.env` from the defaults before deploying.
- Restrict firewall access so only your internal network can reach port 8765.
- Consider rate limiting at the reverse proxy if subscribers can be untrusted.

## Observability

The server logs stats every 60 seconds:
```
STATS|subscribers=3|received=1250|broadcast=3750|failures=2
```

- `subscribers` — current connected subscribers
- `received` — messages received from publishers
- `broadcast` — successful sends to subscribers (messages × subscribers)
- `failures` — failed subscriber sends (dead connections cleaned up)

## Graceful shutdown

`Ctrl+C` or `SIGTERM` shuts down cleanly. Under pm2, `pm2 stop bfsi-ws-server`.
