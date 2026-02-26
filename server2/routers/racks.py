"""
Rack data router for server2 backend.
"""

import json
import logging

from fastapi import APIRouter

from server2.models import RackQueryRequest
from server2.tools import ExternalDataTools

logger = logging.getLogger("anya.server2.routers.racks")

router = APIRouter(prefix="/racks", tags=["racks"])


@router.post("/query")
async def get_rack_data(request: RackQueryRequest):
    """
    Fetch the latest rack data from external API.

    This endpoint provides direct access to the rack_tool functionality
    without going through the LiveKit agent.
    """
    result = await ExternalDataTools.rack_tool(
        context=None,  # No RunContext for manual trigger
        query=request.query,
        rack_id=request.rack_id,
        location=request.location,
        department=request.department,
    )

    return json.loads(result)
