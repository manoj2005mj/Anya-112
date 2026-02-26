"""
Alert router for server2 backend.
"""

import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks

from server2.models import AlertRequest, AlertResponse
from server2.tools import ExternalDataTools
from server2.config import get_settings

logger = logging.getLogger("anya.server2.routers.alerts")

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/trigger", response_model=dict)
async def trigger_alert(request: AlertRequest, background_tasks: BackgroundTasks):
    """
    Manually trigger an emergency alert.

    This endpoint allows the frontend to trigger alerts without going through
    the LiveKit agent. Useful for direct UI interactions.
    """
    settings = get_settings()

    # Trigger the alert tool directly
    async def _trigger():
        result = await ExternalDataTools.alert_tool(
            context=None,  # No RunContext for manual trigger
            incident_type=request.incident_type,
            location=request.location,
            severity=request.severity,
            description=request.description,
            coordinates=request.coordinates,
        )
        return result

    # Run in background
    background_tasks.add_task(_trigger)

    return {
        "status": "alert_triggered",
        "message": f"Alert for {request.incident_type} at {request.location} has been triggered",
        "server": settings.LIVEKIT_URL,
    }
