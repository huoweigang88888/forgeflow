"""
ForgeFlow AI - WebSocket Endpoint for Real-Time Ticket Status.

Provides real-time status updates via WebSocket using Redis Pub/Sub.
Clients connect to /ws/v1/tickets/{ticket_id} and receive step-by-step
agent progress events as they happen.

From PRD Section 9.4: WebSocket Protocol for Real-Time Updates.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from forgeflow.core.config import get_settings
from forgeflow.monitoring.logger import get_logger

logger = get_logger(component="ws")

router = APIRouter(prefix="/ws/v1", tags=["websocket"])

settings = get_settings()

# Redis connection pool (shared across all WS connections)
_redis_pool: redis_asyncio.ConnectionPool[Any] | None = None


async def get_redis() -> redis_asyncio.Redis[Any]:
    """Return a Redis client from the shared connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis_asyncio.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=True,
        )
    return redis_asyncio.Redis(connection_pool=_redis_pool)


async def close_redis_pool() -> None:
    """Close the Redis connection pool on shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


# ── Ticket status event types ──
# These mirror the event types produced by AgentService._publish_status()


@router.websocket("/tickets/{ticket_id}")
async def ticket_status_ws(websocket: WebSocket, ticket_id: str) -> None:
    """WebSocket endpoint for real-time ticket status updates.

    Clients receive JSON messages of the form:
        {
            "type": "step_update" | "pending_approval" | "completed" | "error",
            "ticket_id": "tkt_xxx",
            "step": "detect_intent",
            "status": "processing",
            "timestamp": "2026-06-19T12:00:00Z",
            "data": { ... }
        }

    The server also sends a "connected" event on successful subscription.
    """
    await websocket.accept()

    # Send initial connection confirmation
    await _send_json(
        websocket,
        {
            "type": "connected",
            "ticket_id": ticket_id,
            "timestamp": _now_iso(),
            "data": {"message": f"Subscribed to ticket:{ticket_id}"},
        },
    )

    redis_client = await get_redis()
    pubsub = redis_client.pubsub()
    channel = f"ticket:{ticket_id}"

    try:
        await pubsub.subscribe(channel)
        logger.info("ws_client_connected", ticket_id=ticket_id)

        # Listen for messages from Redis Pub/Sub
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            # Forward the Redis message directly to the WebSocket client
            try:
                data_str = message["data"]
                if isinstance(data_str, str):
                    await websocket.send_text(data_str)
                elif isinstance(data_str, bytes):
                    await websocket.send_text(data_str.decode("utf-8"))
            except Exception:
                logger.warning(
                    "ws_send_failed",
                    ticket_id=ticket_id,
                    exc_info=True,
                )
                break

            # Check if client is still connected
            if websocket.client_state != WebSocketState.CONNECTED:
                break

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", ticket_id=ticket_id)
    except asyncio.CancelledError:
        logger.info("ws_cancelled", ticket_id=ticket_id)
    except Exception:
        logger.error("ws_unexpected_error", ticket_id=ticket_id, exc_info=True)
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(channel)
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass


async def _send_json(websocket: WebSocket, data: dict[str, Any]) -> None:
    """Send a JSON message through the WebSocket, swallowing errors."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps(data))
    except Exception:
        pass


def _now_iso() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
