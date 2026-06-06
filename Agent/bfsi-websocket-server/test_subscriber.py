"""
Test subscriber — use this to verify broadcasting works end-to-end.

Usage:
  python test_subscriber.py

Connects as a subscriber and prints every message received from the broadcaster.
"""
import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
import websockets

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# When connecting as a client, WS_HOST may be 0.0.0.0 (server bind address).
# 0.0.0.0 is not a valid destination for clients — use localhost instead.
WS_HOST = os.getenv("WS_CLIENT_HOST", "localhost")
WS_PORT = int(os.getenv("WS_PORT", "8766"))
TOKEN = os.getenv("SUBSCRIBER_TOKEN", "change-me-subscriber-token")


async def listen():
    url = f"ws://{WS_HOST}:{WS_PORT}?token={TOKEN}"
    print(f"Connecting to {url}...")
    try:
        async with websockets.connect(url) as ws:
            print("Connected. Waiting for messages...\n")
            async for message in ws:
                print("─" * 60)
                print(message)
    except websockets.ConnectionClosed as e:
        print(f"\nConnection closed by server: code={e.code} reason={e.reason}")
    except Exception as e:
        print(f"\nConnection error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\nExiting.")
