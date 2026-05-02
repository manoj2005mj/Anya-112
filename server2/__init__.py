"""
Anya LiveKit Agents Backend (server2)

A separate FastAPI backend with LiveKit Agents integration for emergency dispatch.
"""

__version__ = "2.0.0"

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from server2.main import app
        return app
    raise AttributeError(f"module 'server2' has no attribute {name!r}")
