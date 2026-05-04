import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.db.redis import get_redis

router = APIRouter()


@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    """
    WebSocket endpoint for real-time incident updates.

    Architecture:
    - Backend workers publish incident updates to Redis pub/sub channel "incidents"
    - This handler subscribes to that channel
    - Every connected frontend client receives updates within milliseconds
    - Decoupled: workers don't know about WebSocket clients

    Reconnect: frontend useWebSocket hook handles auto-reconnect on disconnect.
    """
    await websocket.accept()
    redis = get_redis()
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe("incidents")
        print(f"[WebSocket] Client connected: {websocket.client}")

        # Send a heartbeat every 30s to keep connection alive
        async def heartbeat():
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

        heartbeat_task = asyncio.create_task(heartbeat())

        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])

    except WebSocketDisconnect:
        print(f"[WebSocket] Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        heartbeat_task.cancel()
        await pubsub.unsubscribe("incidents")
        await pubsub.aclose()