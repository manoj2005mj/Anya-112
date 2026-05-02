"""
Chat router for server2 backend.

Provides the /chat endpoint that matches the frontend's expected format.
Compatible with the existing frontend (Dashboard.tsx).
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server2.config import get_settings, normalize_gemini_model_name
from server2.logging_utils import ErrorComponent, get_logger
from server2.services.incident_enrichment import enrich_incident_response

logger = get_logger("anya.server2.routers.chat")
router = APIRouter(prefix="/chat", tags=["chat"])


class MessagePart(BaseModel):
    """A single part of a message (text content)"""
    text: str


class HistoryMessage(BaseModel):
    """A message in the conversation history"""
    role: str
    parts: List[MessagePart]


class ChatRequest(BaseModel):
    """Request model for chat endpoint matching frontend format"""
    message: str
    history: Optional[List[HistoryMessage]] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint matching frontend format"""
    text: str


@router.post("")
async def chat(request: ChatRequest):
    """
    Chat endpoint that matches the frontend's expected format.

    Frontend sends:
    {
      "message": "There's a fire at 123 Main Street",
      "history": [...]
    }

    Frontend expects response:
    {
      "text": "AI response text with optional JSON block"
    }
    """
    settings = get_settings()

    try:
        print("\n" + "="*60)
        print("[CHAT] Request received")
        print(f"[CHAT] Message: {request.message[:100]}...")
        print(f"[CHAT] Has history: {bool(request.history)}")
        print("="*60)

        logger.info(
            f"Chat request received",
            component=ErrorComponent.GEMINI_LLM,
            message_length=len(request.message),
            has_history=bool(request.history),
        )

        # Import Google GenAI client
        print("[CHAT] → Creating Gemini client...")
        from google import genai

        # Initialize client
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        print(f"[CHAT] ✓ Client created (model: {settings.GEMINI_MODEL})")

        # Build history in the correct format for Google GenAI
        # History is a list of dicts with 'role' and 'parts' keys
        print("[CHAT] → Building conversation history...")
        history = []
        if request.history:
            for msg in request.history:
                history.append({
                    "role": msg.role,
                    "parts": [{"text": msg.parts[0].text}]
                })
        print(f"[CHAT] ✓ History built with {len(history)} messages")

        SYSTEM_INSTRUCTION = """
You are 'Anya', a calm and highly reliable 112 emergency dispatch agent for India.

Rules:
- Match the caller's language. If they speak in Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, or Gujarati, reply in that same language.
- Keep responses short, calm, and action-oriented.
- In each reply: acknowledge the situation, give one immediate safety instruction, and ask exactly one follow-up question when information is missing.
- Avoid repeating questions if the information is already known from the conversation history.
- Once dispatch is confirmed, reassure the caller and stop extending the conversation unnecessarily.

Structured dashboard output:
- The React dashboard depends on structured incident metadata for the map, threat level, and active units.
- At the very end of every response, output a fenced JSON block using this exact schema:
```json
{
  "incident_location": "Extracted street, landmark, or area",
  "coordinates": [latitude, longitude],
  "disaster_type": "Fire, Medical, Accident, Crime, Infrastructure, Disaster, etc.",
  "departments_required": ["Fire", "Ambulance", "Police", "Electrical", "Disaster Response"],
  "severity": "Low, Medium, High, Critical",
  "extracted_entities": ["key", "facts", "from", "the", "incident"]
}
```
- If coordinates are uncertain, set them to null.
- If a field is unknown, use null for scalar fields and [] for array fields.
        """

        # Create chat session with proper configuration
        # For chats.create(), use the model name directly (not with models/ prefix)
        model_name = normalize_gemini_model_name(settings.GEMINI_MODEL)

        print("[CHAT] → Creating chat session...")
        print(f"[CHAT]   Model: {model_name}")
        print(f"[CHAT]   Temperature: 0.4")
        chat = client.chats.create(
            model=model_name,
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.4,
            },
            history=history if history else None,
        )
        print("[CHAT] ✓ Chat session created")

        print(f"[CHAT] → Sending message to Gemini: {request.message[:50]}...")
        response = chat.send_message(request.message)
        print(f"[CHAT] ✓ Response received ({len(response.text) if response.text else 0} chars)")

        enriched_text = await enrich_incident_response(
            response.text or "",
            request.message,
            history,
        )

        logger.info(
            f"Chat response generated successfully",
            component=ErrorComponent.GEMINI_LLM,
            response_length=len(enriched_text),
        )

        print("[CHAT] → Returning response to frontend")
        print("="*60 + "\n")
        return ChatResponse(text=enriched_text)

    except Exception as e:
        # Enhanced error logging with component identification
        print(f"[CHAT] ✗ ERROR: {str(e)}")
        print("="*60 + "\n")
        logger.error(
            f"Error in chat endpoint: {str(e)}",
            component=ErrorComponent.GEMINI_LLM,
            include_traceback=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Chat processing failed",
                "component": ErrorComponent.GEMINI_LLM.value,
                "message": str(e)
            }
        )
