#!/usr/bin/env python3
import asyncio
import json
import logging
from datetime import datetime
from websockets.server import serve
from websockets.exceptions import ConnectionClosed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Track connected clients
bridge_clients = set()
avioco_sessions = {}  # session_id -> websocket
extel_calls = {}      # call_id -> websocket

async def broadcast_to_bridge(message: dict):
    """Send any event to all bridge monitor clients."""
    if bridge_clients:
        data = json.dumps(message)
        await asyncio.gather(*(c.send(data) for c in bridge_clients if c.open))

async def handle_avioco(ws):
    session_id = None
    try:
        logger.info("Avioco client connected (waiting for session_id)")
        async for msg in ws:
            logger.info(f"Received from /avioco: {msg}")
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "audio_data":
                # Register session if first time
                if not session_id:
                    session_id = data.get("session_id")
                    avioco_sessions[session_id] = ws
                    logger.info(f"Registered Avioco session {session_id}")
                # Forward audio to Extel & Bridge
                call_ws = extel_calls.get(session_id)
                if call_ws and call_ws.open:
                    await call_ws.send(json.dumps(data))
                await broadcast_to_bridge({"from": "avioco", **data})

            else:
                await broadcast_to_bridge({"from": "avioco", **data})
    except ConnectionClosed:
        pass
    finally:
        if session_id and avioco_sessions.get(session_id) is ws:
            avioco_sessions.pop(session_id, None)
            logger.info(f"Avioco {session_id} disconnected")

async def handle_extel(ws):
    call_id = None
    try:
        logger.info("Extel client connected (waiting for call_id)")
        async for msg in ws:
            logger.info(f"Received from /extel: {msg}")
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            if data.get("type") in ("call_event", "audio_data"):
                # Register call_id first time
                if not call_id:
                    call_id = data.get("call_id")
                    extel_calls[call_id] = ws
                    logger.info(f"Registered Extel call {call_id}")
                # Forward to Avioco & Bridge
                session_ws = avioco_sessions.get(call_id)
                if session_ws and session_ws.open:
                    await session_ws.send(json.dumps(data))
                await broadcast_to_bridge({"from": "extel", **data})
            else:
                await broadcast_to_bridge({"from": "extel", **data})
    except ConnectionClosed:
        pass
    finally:
        if call_id and extel_calls.get(call_id) is ws:
            extel_calls.pop(call_id, None)
            logger.info(f"Extel {call_id} disconnected")

async def handle_bridge(ws):
    logger.info("Bridge client connected")
    bridge_clients.add(ws)
    try:
        async for msg in ws:
            logger.info(f"Received from /bridge: {msg}")
            # Example: respond with heartbeat confirmation
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "heartbeat":
                await ws.send(json.dumps({"type": "heartbeat_ack", "timestamp": datetime.now().isoformat()}))
    except ConnectionClosed:
        pass
    finally:
        bridge_clients.discard(ws)
        logger.info("Bridge client disconnected")

async def handler(ws, path):
    logger.info(f"connection open: {path}")
    try:
        if path == "/avioco":
            await handle_avioco(ws)
        elif path == "/extel":
            await handle_extel(ws)
        elif path == "/bridge":
            await handle_bridge(ws)
        else:
            await ws.close()
    finally:
        logger.info(f"connection closed: {path}")

async def main():
    host = "0.0.0.0"
    port = 8080
    async with serve(handler, host, port):
        logger.info(f"Bridge server running on ws://{host}:{port}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped manually")
