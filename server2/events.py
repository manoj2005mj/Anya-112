"""
Event broadcasting system for real-time updates to WebSocket clients.
"""

import asyncio
import logging
from typing import List

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from server2.models import ToolEvent

logger = logging.getLogger("anya.server2.events")


class EventBroadcaster:
    """
    Manages WebSocket connections and broadcasts events to all connected clients.
    Implements the observer pattern for real-time event distribution.
    """

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []
        self._event_history: List[ToolEvent] = []
        self._max_history = 100

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self._connections)}")

        # Send recent history to new client
        for event in self._event_history[-10:]:
            try:
                await websocket.send_text(event.to_json())
            except Exception as e:
                logger.error(f"Error sending history: {e}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection"""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self._connections)}")

    async def broadcast(self, event: ToolEvent) -> None:
        """Broadcast an event to all connected clients"""
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Log the event
        logger.info(f"Broadcasting event: {event.event_type.value} - {event.tool_name}")

        # Send to all connected clients
        if self._connections:
            message = event.to_json()
            # Create tasks for all connections
            tasks = []
            for ws in self._connections:
                if ws.client_state == WebSocketState.CONNECTED:
                    tasks.append(self._safe_send(ws, message))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, websocket: WebSocket, message: str) -> None:
        """Safely send a message to a WebSocket, handling disconnections"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            self.disconnect(websocket)

    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self._connections)


# Global event broadcaster instance
event_broadcaster = EventBroadcaster()
