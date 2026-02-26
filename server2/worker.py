#!/usr/bin/env python3
"""
LiveKit Worker entry point for server2 backend.

This file is meant to be run with the LiveKit CLI to start the agent worker.

Uses:
- LiveKit Inference for STT/TTS/LLM (automatic, no keys needed for STT/TTS)
- Gemini for LLM (via GEMINI_API_KEY when available)
- In-memory RAG with LangChain

Installation:
    pip install livekit livekit-agents
    pip install livekit-plugins-openai  # For OpenAI LLM support

Usage:
    livekit-agent run --url <LIVEKIT_URL> --api-key <API_KEY> --api-secret <SECRET> worker.py
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

# LiveKit Agents imports (required for worker)
try:
    from livekit.agents import (
        AgentSession,
        AgentServer,
        ChatContext,
        JobContext,
    )
    # Try to import openai plugin
    try:
        from livekit.plugins import openai
    except ImportError:
        try:
            from livekit.agents.llm import openai
        except ImportError:
            openai = None

    # Try to import Cartesia TTS plugin
    cartesia = None
    try:
        from livekit.plugins import cartesia
    except ImportError:
        try:
            from livekit.agents.tts import cartesia
        except ImportError:
            cartesia = None
except ImportError as e:
    print(f"ERROR: LiveKit Agents SDK not installed!")
    print(f"Details: {e}")
    print("Install with: pip install 'livekit-agents>=1.4.0'")
    sys.exit(1)

from server2.config import get_settings
from server2.events import event_broadcaster
from server2.models import ToolEvent, ToolEventType
from server2.agents import EmergencyDispatchAgent
from server2.rag import rag_system

# =============================================================================
# Configuration
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("anya.server2.worker")


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

server = AgentServer()


@server.rtc_session()
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


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("Anya LiveKit Agent Worker Starting")
    logger.info("=" * 60)
    logger.info(f"LiveKit URL: {settings.LIVEKIT_URL}")
    logger.info(f"Room Name: {settings.LIVEKIT_ROOM_NAME}")
    logger.info(f"Gemini Model: {settings.GEMINI_MODEL}")
    logger.info(f"RAG Enabled: {settings.RAG_ENABLED}")

    # Run the agent server
    # Note: This is typically started via LiveKit CLI, not directly
    # Use: livekit-agent run --url <URL> --api-key <KEY> --api-secret <SECRET>
    logger.info("Starting agent server...")
    logger.info("Note: This worker is typically started via LiveKit CLI:")
    logger.info("  livekit-agent run --url <URL> --api-key <KEY> --api-secret <SECRET>")
