"""
Anya LiveKit Agents Backend (server2)

A separate FastAPI backend with LiveKit Agents integration for emergency dispatch.
"""

__version__ = "2.0.0"

from server2.main import app

__all__ = ["app"]
