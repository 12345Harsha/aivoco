#!/usr/bin/env python3
import asyncio
import json
import websockets
from datetime import datetime

SERVER_URL = "ws://localhost:8080"
SESSION_ID = "test_session_123"  # Same ID used for both Avioco & Extel

async def avioco_client():
    """Simulate Avioco sending audio and receiving forwarded events."""
    async with websockets.connect(f"{SERVER_URL}/avioco") as ws:
        print("[Avioco] Connected")

        async def send_audio():
            for i in range(3):
                data = {
                    "type": "audio_data",
                    "session_id": SESSION_ID,
                    "audio": f"audio_chunk_{i}",
                    "timestamp": datetime.now().isoformat()
                }
                await ws.send(json.dumps(data))
                print(f"[Avioco] Sent audio {i}")
                await asyncio.sleep(1)

        async def receive():
            async for msg in ws:
                print(f"[Avioco] Received: {msg}")

        await asyncio.gather(send_audio(), receive())

async def extel_client():
    """Simulate Extel sending call events and receiving forwarded audio."""
    async with websockets.connect(f"{SERVER_URL}/extel") as ws:
        print("[Extel] Connected")

        async def send_events():
            # Send call_started first
            event = {
                "type": "call_event",
                "call_id": SESSION_ID,
                "event": "call_started",
                "timestamp": datetime.now().isoformat()
            }
            await ws.send(json.dumps(event))
            print("[Extel] Sent call_started")

            await asyncio.sleep(2)

            # Send back audio chunks to Avioco
            for i in range(2):
                audio = {
                    "type": "audio_data",
                    "call_id": SESSION_ID,
                    "audio": f"extel_audio_chunk_{i}",
                    "timestamp": datetime.now().isoformat()
                }
                await ws.send(json.dumps(audio))
                print(f"[Extel] Sent audio {i}")
                await asyncio.sleep(1)

        async def receive():
            async for msg in ws:
                print(f"[Extel] Received: {msg}")

        await asyncio.gather(send_events(), receive())

async def bridge_monitor():
    """Simulate a monitoring client to see all traffic."""
    async with websockets.connect(f"{SERVER_URL}/bridge") as ws:
        print("[Bridge] Connected")
        async for msg in ws:
            print(f"[Bridge] Monitor saw: {msg}")

async def main():
    await asyncio.gather(
        avioco_client(),
        extel_client(),
        bridge_monitor()
    )

if __name__ == "__main__":
    asyncio.run(main())
