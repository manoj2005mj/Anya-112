"""
Custom tools that can be called by the LiveKit agent.

These tools demonstrate external data access and action execution.
Note: These tools work both with and without LiveKit installed.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

import aiohttp

# LiveKit Agents imports (optional)
LIVEKIT_AVAILABLE = False
try:
    from livekit.agents import function_tool, RunContext, AgentSession
    LIVEKIT_AVAILABLE = True
except ImportError:
    pass

from server2.config import get_settings
from server2.events import event_broadcaster
from server2.models import ToolEvent, ToolEventType
from server2.logging_utils import ErrorComponent, get_logger

logger = get_logger("anya.server2.tools")


def make_function_tool(func):
    """
    Decorator factory that applies @function_tool() if LiveKit is available,
    otherwise returns the function as-is.
    """
    if LIVEKIT_AVAILABLE:
        return function_tool()(func)
    return func


class ExternalDataTools:
    """
    Custom tools that can be called by the LiveKit agent.

    These tools demonstrate external data access and action execution.
    """

    @staticmethod
    @make_function_tool
    async def rack_tool(
        context: Any = None,  # RunContext[AgentSession] when LiveKit is available
        query: str = "",
        rack_id: Optional[str] = None,
        location: Optional[str] = None,
        department: Optional[str] = None,
    ) -> str:
        """
        Fetch rack data from external database or API.

        This tool queries the external rack management system to retrieve
        real-time information about equipment racks, their status, and contents.

        Args:
            query: Search query for rack data (e.g., "server status", "temperature")
            rack_id: Optional specific rack identifier
            location: Optional location filter (e.g., "datacenter-1", "floor-3")
            department: Optional department filter (e.g., "IT", "Electrical")

        Returns:
            JSON string containing the fetched rack data
        """
        print("\n[TOOL] → rack_tool called")
        print(f"[TOOL]   query: {query}")
        print(f"[TOOL]   rack_id: {rack_id}")
        print(f"[TOOL]   location: {location}")
        print(f"[TOOL]   department: {department}")

        settings = get_settings()

        # Create event for tool invocation
        event = ToolEvent(
            event_type=ToolEventType.TOOL_INVOKED,
            tool_name="rack_tool",
            timestamp=datetime.now(timezone.utc),
            payload={
                "query": query,
                "rack_id": rack_id,
                "location": location,
                "department": department,
            }
        )
        await event_broadcaster.broadcast(event)

        logger.info(f"rack_tool called with query={query}, rack_id={rack_id}")

        try:
            # Simulate external API call (replace with actual API call)
            # In production, this would call your actual rack management API
            async with aiohttp.ClientSession() as session:
                # Example API call structure
                url = f"{settings.RACK_API_BASE_URL}/search"
                params = {
                    "q": query,
                    **({"rack_id": rack_id} if rack_id else {}),
                    **({"location": location} if location else {}),
                    **({"department": department} if department else {}),
                }

                # Simulated response (in production, await session.get(url, params=params))
                await asyncio.sleep(0.5)  # Simulate network delay

                # Mock response data
                result_data = {
                    "racks": [
                        {
                            "rack_id": rack_id or "RACK-001",
                            "location": location or "Data Center A",
                            "department": department or "IT",
                            "status": "operational",
                            "temperature": 22.5,
                            "power_usage": 450,
                            "last_updated": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                    "query": query,
                    "total": 1,
                }

                # Create completion event
                completion_event = ToolEvent(
                    event_type=ToolEventType.TOOL_COMPLETED,
                    tool_name="rack_tool",
                    timestamp=datetime.now(timezone.utc),
                    payload={"result": result_data}
                )
                await event_broadcaster.broadcast(completion_event)

                print(f"[TOOL] ✓ rack_tool completed - found {result_data['total']} rack(s)\n")
                return json.dumps(result_data, indent=2)

        except Exception as e:
            print(f"[TOOL] ✗ rack_tool failed: {str(e)}\n")
            logger.error(
                f"Error in rack_tool: {str(e)}",
                component=ErrorComponent.TOOL_RACK,
                include_traceback=True,
                query=query,
                rack_id=rack_id,
            )

            # Create failure event
            failure_event = ToolEvent(
                event_type=ToolEventType.TOOL_FAILED,
                tool_name="rack_tool",
                timestamp=datetime.now(timezone.utc),
                payload={"query": query},
                error=str(e)
            )
            await event_broadcaster.broadcast(failure_event)

            return json.dumps({"error": str(e), "query": query})

    @staticmethod
    @make_function_tool
    async def alert_tool(
        context: Any = None,  # RunContext[AgentSession] when LiveKit is available
        incident_type: str = "",
        location: str = "",
        severity: str = "high",
        description: Optional[str] = None,
        coordinates: Optional[List[float]] = None,
    ) -> str:
        """
        Trigger an emergency alert based on AI-detected incident.

        This tool is called when the AI agent detects an emergency situation
        such as a fire, medical emergency, or other critical incident.
        It broadcasts the alert to all connected frontend clients and can
        optionally send notifications to external services.

        Args:
            incident_type: Type of emergency (fire, medical, accident, crime, etc.)
            location: Location description of the incident
            severity: Severity level (low, medium, high, critical)
            description: Optional additional details about the incident
            coordinates: Optional [latitude, longitude] for mapping

        Returns:
            JSON string containing alert confirmation details
        """
        print("\n[TOOL] → alert_tool called")
        print(f"[TOOL]   incident_type: {incident_type}")
        print(f"[TOOL]   location: {location}")
        print(f"[TOOL]   severity: {severity}")
        print(f"[TOOL]   description: {description}")

        settings = get_settings()

        # Create event for tool invocation
        event = ToolEvent(
            event_type=ToolEventType.TOOL_INVOKED,
            tool_name="alert_tool",
            timestamp=datetime.now(timezone.utc),
            payload={
                "incident_type": incident_type,
                "location": location,
                "severity": severity,
                "description": description,
                "coordinates": coordinates,
            }
        )
        await event_broadcaster.broadcast(event)

        logger.warning(f"ALERT TRIGGERED: {incident_type} at {location} (severity: {severity})")

        try:
            # Generate alert ID
            alert_id = f"ALT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

            # Prepare alert data
            alert_data = {
                "alert_id": alert_id,
                "incident_type": incident_type,
                "location": location,
                "severity": severity,
                "description": description,
                "coordinates": coordinates,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "active",
            }

            # Send webhook if configured
            if settings.ALERT_WEBHOOK_URL:
                try:
                    async with aiohttp.ClientSession() as session:
                        await session.post(
                            settings.ALERT_WEBHOOK_URL,
                            json=alert_data,
                            timeout=aiohttp.ClientTimeout(total=5)
                        )
                        logger.info(f"Webhook sent to {settings.ALERT_WEBHOOK_URL}")
                except Exception as e:
                    logger.error(
                        f"Failed to send webhook: {str(e)}",
                        component=ErrorComponent.EXTERNAL_API,
                        webhook_url=settings.ALERT_WEBHOOK_URL,
                    )

            # Create completion event with full alert details
            completion_event = ToolEvent(
                event_type=ToolEventType.TOOL_COMPLETED,
                tool_name="alert_tool",
                timestamp=datetime.now(timezone.utc),
                payload=alert_data
            )
            await event_broadcaster.broadcast(completion_event)

            print(f"[TOOL] ✓ alert_tool completed - Alert ID: {alert_id}")
            print(f"[TOOL]   Emergency alert '{incident_type}' triggered for {location}\n")
            return json.dumps({
                "success": True,
                "alert_id": alert_id,
                "message": f"Emergency alert '{incident_type}' has been triggered for {location}",
                "data": alert_data,
            }, indent=2)

        except Exception as e:
            print(f"[TOOL] ✗ alert_tool failed: {str(e)}\n")
            logger.error(
                f"Error in alert_tool: {str(e)}",
                component=ErrorComponent.TOOL_ALERT,
                include_traceback=True,
                incident_type=incident_type,
                location=location,
            )

            # Create failure event
            failure_event = ToolEvent(
                event_type=ToolEventType.TOOL_FAILED,
                tool_name="alert_tool",
                timestamp=datetime.now(timezone.utc),
                payload={
                    "incident_type": incident_type,
                    "location": location,
                },
                error=str(e)
            )
            await event_broadcaster.broadcast(failure_event)

            return json.dumps({"error": str(e), "incident_type": incident_type})

    @classmethod
    def get_all_tools(cls) -> list:
        """Get all registered tools for the agent"""
        return [
            cls.rack_tool,
            cls.alert_tool,
        ]
