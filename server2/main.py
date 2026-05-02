"""
Main FastAPI application for server2 backend.

This is a separate backend server that integrates LiveKit Agents with custom tools
for real-time emergency response coordination. It does not modify any existing code.
"""

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# LiveKit Agents imports (optional)
LIVEKIT_AVAILABLE = False
openai = None  # type: ignore
cartesia = None  # type: ignore
try:
    from livekit.agents import (
        AgentSession,
        AgentServer,
        ChatContext,
        JobContext,
    )
    # Try to import openai plugin (may not be available in all versions)
    try:
        from livekit.plugins import openai
    except ImportError:
        # Fallback: try direct import pattern
        try:
            from livekit.agents.llm import openai
        except ImportError:
            openai = None

    # Try to import Cartesia TTS plugin
    try:
        from livekit.plugins import cartesia
    except ImportError:
        try:
            from livekit.agents.tts import cartesia
        except ImportError:
            cartesia = None
            logger_temp = logging.getLogger("anya.server2.livekit")
            logger_temp.warning("Cartesia TTS plugin not available")
            logger_temp.warning("Install with: pip install 'livekit-agents[cartesia]'")

    LIVEKIT_AVAILABLE = True
    logger_temp = logging.getLogger("anya.server2.livekit")
    logger_temp.info("LiveKit Agents SDK imported successfully")
except ImportError as e:
    logger_temp = logging.getLogger("anya.server2.livekit")
    logger_temp.warning(f"LiveKit Agents SDK not available: {e}")
    logger_temp.warning("Install with: pip install 'livekit-agents>=1.4.0'")

from server2.config import get_settings
from server2.events import event_broadcaster
from server2.models import ToolEvent, ToolEventType
from server2.agents import EmergencyDispatchAgent
from server2.routers import alerts, racks, events, chat, image, routing
from server2.rag import rag_system
from server2.logging_utils import (
    RequestContextMiddleware,
    ErrorComponent,
    get_logger,
    log_exception_handler
)

# =============================================================================
# Configuration
# =============================================================================

logger = get_logger("anya.server2")


def get_agent_session():
    """
    Create and configure an AgentSession with Gemini LLM and Cartesia TTS.

    Uses:
    - Cartesia TTS for multilingual speech synthesis (when API key is configured)
    - LiveKit Inference for STT (automatic, no keys needed)
    - Gemini or OpenAI for LLM
    """
    settings = get_settings()

    # Configure Gemini API key in environment
    # LiveKit Inference will pick this up automatically
    if settings.GEMINI_API_KEY:
        import os
        os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY
        logger.info(f"Gemini API key configured, model: {settings.GEMINI_MODEL}")

    # Create LLM instance using OpenAI plugin
    llm_instance = "openai/gpt-4o"  # Default string-based model name

    if openai is not None:
        try:
            llm_obj = openai.llm()
            if hasattr(llm_obj, 'with_gpt_4o'):
                llm_instance = llm_obj.with_gpt_4o()
                logger.info("LLM configured with GPT-4o via OpenAI plugin")
            else:
                logger.info("Using OpenAI plugin with default model")
        except Exception as e:
            logger.warning(f"OpenAI plugin warning: {e}, using string model name")
    else:
        logger.info("OpenAI plugin not available, using string model name")

    # Configure Cartesia TTS for multilingual support
    tts_instance = None
    if cartesia is not None and settings.CARTESIA_API_KEY:
        try:
            # Configure API key for Cartesia
            import os
            os.environ["CARTESIA_API_KEY"] = settings.CARTESIA_API_KEY

            tts_instance = cartesia.TTS(
                model=settings.CARTESIA_MODEL,
                voice=settings.CARTESIA_VOICE,
                language=settings.CARTESIA_DEFAULT_LANGUAGE,
                speed=settings.CARTESIA_SPEED,
                volume=settings.CARTESIA_VOLUME,
            )
            logger.info(f"Cartesia TTS configured: model={settings.CARTESIA_MODEL}, "
                       f"default_lang={settings.CARTESIA_DEFAULT_LANGUAGE}, "
                       f"supported={settings.CARTESIA_SUPPORTED_LANGUAGES}")
        except Exception as e:
            logger.warning(f"Cartesia TTS configuration failed: {e}")
            logger.info("Falling back to LiveKit Inference default TTS")
    else:
        if not settings.CARTESIA_API_KEY:
            logger.info("CARTESIA_API_KEY not set, using LiveKit Inference default TTS")
        else:
            logger.info("Cartesia plugin not available, using LiveKit Inference default TTS")

    # Create AgentSession with TTS
    session = AgentSession(
        llm=llm_instance,
        tts=tts_instance,  # Will be None if Cartesia not configured, using default
    )

    return session


# =============================================================================
# LiveKit Agent Server
# =============================================================================

# Create the LiveKit AgentServer (only if LiveKit is available)
if LIVEKIT_AVAILABLE:
    agent_server = AgentServer()

    @agent_server.rtc_session()
    async def emergency_agent_entrypoint(ctx: JobContext):
        """
        Main entrypoint for the LiveKit agent.
        This function is called when a new job is dispatched to this agent.
        """
        settings = get_settings()

        logger.info(f"Agent session started for job: {ctx.job.id}")

        # Initialize RAG system
        if settings.RAG_ENABLED:
            rag_system.initialize()
            logger.info("RAG system initialized")

        # Broadcast agent started event
        start_event = ToolEvent(
            event_type=ToolEventType.AGENT_STARTED,
            tool_name="agent_lifecycle",
            timestamp=datetime.now(timezone.utc),
            payload={"job_id": ctx.job.id, "room": ctx.room.name}
        )
        await event_broadcaster.broadcast(start_event)

        try:
            # Parse job metadata if provided
            metadata = {}
            if ctx.job.metadata:
                try:
                    metadata = json.loads(ctx.job.metadata)
                except json.JSONDecodeError:
                    logger.warning("Invalid metadata JSON")

            # Create initial chat context with metadata
            initial_ctx = ChatContext()
            if metadata.get("user_name"):
                initial_ctx.add_message(
                    role="assistant",
                    content=f"The caller's name is {metadata['user_name']}."
                )
            if metadata.get("context"):
                initial_ctx.add_message(
                    role="assistant",
                    content=f"Context: {metadata['context']}"
                )

            # Create the agent instance
            agent = EmergencyDispatchAgent(chat_ctx=initial_ctx)

            # Get configured session
            session = get_agent_session()

            # Start the session
            await session.start(
                room=ctx.room,
                agent=agent,
            )

            logger.info(f"Agent session active for room: {ctx.room.name}")

            # Keep the session running until the job ends
            await ctx.job.wait_for_done()

        except Exception as e:
            logger.error(f"Error in agent session: {e}")
            raise
        finally:
            # Broadcast agent stopped event
            stop_event = ToolEvent(
                event_type=ToolEventType.AGENT_STOPPED,
                tool_name="agent_lifecycle",
                timestamp=datetime.now(timezone.utc),
                payload={"job_id": ctx.job.id}
            )
            await event_broadcaster.broadcast(stop_event)

            logger.info(f"Agent session ended for job: {ctx.job.id}")

else:
    # LiveKit not available - agent_server will be None
    agent_server = None
    emergency_agent_entrypoint = None


# =============================================================================
# Lifespan Context Manager (replaces deprecated on_event)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("Anya LiveKit Agents Backend Starting")
    logger.info("=" * 60)

    # Check LiveKit availability
    if LIVEKIT_AVAILABLE:
        # Check LiveKit configuration
        if settings.LIVEKIT_API_KEY:
            logger.info(f"LiveKit configured for: {settings.LIVEKIT_URL}")
        else:
            logger.warning("LiveKit SDK available but API key not configured")
            logger.warning("Set LIVEKIT_API_KEY and LIVEKIT_API_SECRET in .env to enable agent features")
    else:
        logger.warning("LiveKit Agents SDK not installed")
        logger.warning("HTTP endpoints will work, but LiveKit agent features are disabled")
        logger.warning("Install with: pip install 'livekit-agents>=1.4.0' 'livekit-plugins-openai'")

    # Initialize RAG system
    if settings.RAG_ENABLED:
        rag_system.initialize()
        logger.info("RAG system initialized")

    # Application is running
    yield

    # Shutdown: Cleanup resources
    logger.info("Shutting down Anya LiveKit Agents Backend")

    # Close all WebSocket connections
    for ws in event_broadcaster._connections[:]:
        try:
            await ws.close()
        except Exception:
            pass

    logger.info("All connections closed")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Anya LiveKit Agents Backend",
    description="FastAPI backend with LiveKit Agents integration for emergency dispatch",
    version="2.0.0",
    lifespan=lifespan,
)

# Add request tracking middleware (must be before CORS)
app.add_middleware(RequestContextMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handler
app.add_exception_handler(Exception, log_exception_handler)

# Include routers
app.include_router(alerts.router)
app.include_router(racks.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(image.router)
app.include_router(routing.router)


# =============================================================================
# Root Endpoints
# =============================================================================

@app.get("/")
async def root():
    """Root endpoint with server information"""
    return {
        "server": "Anya LiveKit Agents Backend",
        "version": "2.0.0",
        "status": "running",
        "livekit_available": LIVEKIT_AVAILABLE,
        "rag_available": rag_system.is_available(),
        "websocket_connections": event_broadcaster.get_connection_count(),
        "endpoints": {
            "health": "/health",
            "chat": "/chat",
            "image": "/image",
            "alerts": "/alerts/trigger",
            "racks": "/racks/query",
            "events_ws": "/events/ws",
            "events_sse": "/events/sse",
            "events_history": "/events/history",
            "livekit_status": "/livekit/status",
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "livekit_available": LIVEKIT_AVAILABLE,
        "rag_available": rag_system.is_available(),
        "active_connections": event_broadcaster.get_connection_count(),
    }


@app.get("/livekit/status")
async def livekit_status():
    """Get LiveKit agent server status"""
    settings = get_settings()
    return {
        "configured": LIVEKIT_AVAILABLE and bool(settings.LIVEKIT_API_KEY and settings.LIVEKIT_API_SECRET),
        "url": settings.LIVEKIT_URL,
        "room_name": settings.LIVEKIT_ROOM_NAME,
        "gemini_model": settings.GEMINI_MODEL,
        "rag_enabled": settings.RAG_ENABLED,
        "active_sessions": event_broadcaster.get_connection_count(),
    }


@app.get("/errors")
async def get_error_info():
    """
    Get error tracking information and component status.

    Returns information about error tracking configuration
    and which components are currently active.
    """
    from server2.logging_utils import ErrorComponent, get_error_summary
    return {
        "error_tracking_enabled": True,
        "components": {
            c.value: c.value for c in ErrorComponent
        },
        "description": {
            "fastapi": "FastAPI endpoints and routing",
            "livekit_agent": "LiveKit voice agent sessions",
            "livekit_worker": "LiveKit worker processes",
            "rag": "Retrieval-Augmented Generation system",
            "tool_rack": "Rack data tool",
            "tool_alert": "Emergency alert tool",
            "gemini_llm": "Gemini LLM API calls",
            "gemini_image": "Gemini image analysis",
            "external_api": "External API calls",
            "websocket": "WebSocket connections",
            "database": "Database operations (if any)",
            "unknown": "Unknown error sources"
        },
        "how_to_track": "Check server logs for detailed error information with request_id, component, and traceback"
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")

    # Run directly without using __main__ module to avoid RuntimeWarning
    uvicorn.run(
        "server2.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info",
    )
