"""
LiveKit Agent for Emergency Dispatch Coordination.

This agent handles voice conversations and can invoke custom tools
to fetch external data and trigger emergency alerts.

Uses Gemini for LLM and in-memory RAG for context.
"""

import logging
from typing import Optional

# LiveKit Agents imports (optional)
LIVEKIT_AVAILABLE = False
try:
    from livekit.agents import Agent, ChatContext, ChatMessage, llm
    LIVEKIT_AVAILABLE = True
except ImportError:
    pass

from server2.config import get_settings
from server2.tools import ExternalDataTools
from server2.rag import rag_system

logger = logging.getLogger("anya.server2.agents")


def get_gemini_llm():
    """
    Get the Gemini LLM instance for LiveKit.

    LiveKit Inference supports Gemini through their llm module.
    """
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, using default LiveKit Inference")
        return None

    # Use LiveKit's llm.with_gemini() if available
    # Otherwise, we'll let LiveKit Inference handle it automatically
    try:
        # Try using LiveKit's Gemini integration
        return llm.with_gemini(
            model=settings.GEMINI_MODEL,
            api_key=settings.GEMINI_API_KEY,
        )
    except Exception as e:
        logger.warning(f"Could not configure Gemini LLM: {e}")
        logger.info("Falling back to LiveKit Inference default")
        return None


if LIVEKIT_AVAILABLE:
    class EmergencyDispatchAgent(Agent):
        """
        LiveKit Agent for Emergency Dispatch Coordination.

        This agent handles voice conversations and can invoke custom tools
        to fetch external data and trigger emergency alerts.

        Uses:
        - Gemini LLM for reasoning
        - In-memory RAG for emergency knowledge
        - Custom tools for actions
        """

        def __init__(
            self,
            chat_ctx: Optional[ChatContext] = None,
            instructions: Optional[str] = None,
        ) -> None:
            # Default instructions for the emergency dispatch agent
            default_instructions = """
            You are 'Anya', a highly trained emergency dispatch coordination agent for the 112 Emergency Response Support System in India.

            Your capabilities include:
            - Coordinating emergency response efforts through voice communication
            - Supporting multiple Indian languages (Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, English)
            - Fetching real-time data from external systems (rack status, equipment info)
            - Triggering emergency alerts when critical incidents are detected
            - Providing calm, clear guidance during emergency situations
            - Accessing emergency response knowledge through RAG

            Language Support:
            - Automatically detect the caller's language and respond in the same language
            - If language is unclear, use English as default
            - For Hindi: Use clear, simple Hindi suitable for emergency situations
            - For regional languages: If uncertain, politely ask in simple English if they can speak in Hindi or English

            When you detect an emergency situation (fire, medical emergency, accident, etc.),
            use the alert_tool to trigger the appropriate response and notify the dispatch team.

            When you need information about equipment, facilities, or resources,
            use the rack_tool to fetch the latest data.

            Always remain calm, professional, and clear in your communications.
            Speak in a gentle, reassuring tone with short, clear sentences.

            IMPORTANT: You have access to emergency response knowledge through RAG.
            This context is automatically injected to help you provide accurate information.
            Use this knowledge to guide your responses, but don't explicitly mention
            that you're using RAG - just provide the helpful information naturally.
            """

            # Initialize RAG system if enabled
            settings = get_settings()
            if settings.RAG_ENABLED:
                try:
                    rag_system.initialize()
                    if rag_system.is_available():
                        logger.info("RAG system initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize RAG: {e}")

            super().__init__(
                instructions=instructions or default_instructions,
                chat_ctx=chat_ctx or ChatContext(),
            )

            # Register custom tools
            self._tools = ExternalDataTools.get_all_tools()

        async def on_user_turn_completed(
            self,
            turn_ctx: ChatContext,
            new_message: ChatMessage,
        ) -> None:
            """
            Called when the user completes a turn (speaking).

            This is where we perform RAG lookup based on the user's query
            and inject the retrieved context into the chat history.
            """
            # Log user message for monitoring
            logger.info(f"User turn completed: {new_message.text_content[:100]}...")

            # Perform RAG lookup
            if rag_system.is_available():
                try:
                    query = new_message.text_content
                    context = await rag_system.retrieve_context(query)

                    if context:
                        # Inject RAG context into chat history
                        # This will be used by the LLM for the next response
                        turn_ctx.add_message(
                            role="assistant",
                            content=f"[EMERGENCY KNOWLEDGE BASE]: {context}\n\nUse this information to help answer the caller's question."
                        )
                        logger.debug("RAG context injected into conversation")
                except Exception as e:
                    logger.error(f"RAG lookup failed: {e}")

else:
    EmergencyDispatchAgent = None  # Not available without LiveKit
    logger.warning("LiveKit Agents SDK not available. EmergencyDispatchAgent is disabled.")
