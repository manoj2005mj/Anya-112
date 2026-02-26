"""
Events router for server2 backend.

Provides WebSocket and SSE endpoints for real-time tool invocation events.
"""

import asyncio
import logging
from typing import AsyncIterator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from server2.events import event_broadcaster
from server2.models import ToolEvent

logger = logging.getLogger("anya.server2.routers.events")

router = APIRouter(prefix="/events", tags=["events"])


@router.websocket("/ws")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time tool invocation events.

    Connect to this endpoint to receive live updates when:
    - Tools are invoked by the LiveKit agent
    - Tools complete execution
    - Tools fail with errors
    - Agent sessions start/stop

    Example usage in frontend:
    ```
    const ws = new WebSocket('ws://localhost:8000/ws/events');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Tool event:', data);
    };
    ```
    """
    await event_broadcaster.connect(websocket)

    try:
        # Keep connection alive and handle incoming messages
        while True:
            # Receive any messages from client (for ping/pong, etc.)
            data = await websocket.receive_text()

            # Handle ping/pong for keepalive
            if data == "ping":
                await websocket.send_text("pong")
            else:
                logger.debug(f"Received message from client: {data}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        event_broadcaster.disconnect(websocket)


async def event_stream_generator() -> AsyncIterator[str]:
    """
    Generator for SSE events.
    Yields new tool events as they occur.
    """
    # For simplicity, we'll use polling here
    # In production, implement proper async queue subscription
    last_event_count = len(event_broadcaster._event_history)

    try:
        while True:
            # Check for new events
            current_count = len(event_broadcaster._event_history)
            if current_count > last_event_count:
                # Send new events
                for event in event_broadcaster._event_history[last_event_count:]:
                    yield f"data: {event.to_json()}\n\n"
                last_event_count = current_count

            # Wait a bit before checking again
            await asyncio.sleep(0.5)

    except asyncio.CancelledError:
        logger.info("SSE stream cancelled")


@router.get("/sse")
async def sse_events():
    """
    Server-Sent Events endpoint for tool invocation events.

    Use this as an alternative to WebSocket if you prefer SSE.
    The endpoint keeps the connection open and sends events as they occur.

    Example usage in frontend:
    ```
    const eventSource = new EventSource('http://localhost:8000/events/sse');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Tool event:', data);
    };
    ```
    """
    return StreamingResponse(
        event_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.get("/history")
async def get_event_history(limit: int = 50):
    """Get the history of tool invocation events."""
    events = event_broadcaster._event_history[-limit:]
    return {
        "count": len(events),
        "events": [
            {
                "event_type": e.event_type.value,
                "tool_name": e.tool_name,
                "timestamp": e.timestamp.isoformat(),
                "payload": e.payload,
                "error": e.error,
            }
            for e in events
        ]
    }
