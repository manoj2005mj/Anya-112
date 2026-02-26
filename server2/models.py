"""
Data models for server2 backend.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolEventType(str, Enum):
    """Types of tool events"""
    TOOL_INVOKED = "tool_invoked"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"


@dataclass
class ToolEvent:
    """Event data for tool invocations"""
    event_type: ToolEventType
    tool_name: str
    timestamp: datetime
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps({
            "event_type": self.event_type.value,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "error": self.error,
        })


class RackQueryRequest(BaseModel):
    """Request model for rack queries"""
    query: str = Field(..., description="Search query for rack data")
    rack_id: Optional[str] = Field(None, description="Specific rack ID to query")
    location: Optional[str] = Field(None, description="Location filter")
    department: Optional[str] = Field(None, description="Department filter")


class AlertRequest(BaseModel):
    """Request model for emergency alerts"""
    incident_type: str = Field(..., description="Type of emergency")
    location: str = Field(..., description="Incident location")
    severity: str = Field(default="high", description="Severity level")
    description: Optional[str] = Field(None, description="Additional details")
    coordinates: Optional[List[float]] = Field(None, description="[lat, lng] coordinates")


class RackDataResponse(BaseModel):
    """Response model for rack data"""
    rack_id: str
    status: str
    location: str
    data: Dict[str, Any]
    timestamp: datetime


class AlertResponse(BaseModel):
    """Response model for alerts"""
    alert_id: str
    status: str
    message: str
    timestamp: datetime
