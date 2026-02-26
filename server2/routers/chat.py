"""
Chat router for server2 backend.

Provides the /chat endpoint that matches the frontend's expected format.
Compatible with the existing frontend (Dashboard.tsx).
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server2.config import get_settings
from server2.logging_utils import ErrorComponent, get_logger

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
        You are 'Anya', a highly trained, proactive, and calm emergency dispatch agent for the 112 Emergency Response Support System in India. Your primary goal is to quickly understand the emergency, extract critical information, route the correct departments, and keep the caller calm.

You are a native Indian speaker. Speak with a clear, professional Indian English accent. You can understand and respond in multiple Indian languages (Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, etc.). CRITICAL: If the user writes or speaks in a regional language (e.g., Hindi, Tamil, Telugu), you MUST reply entirely in that same language using the native script. Only use English if the user speaks in English. Match the user's language exactly.

CONVERSATION RULES:
Tone and Pacing: Speak in a gentle, reassuring, and professional female voice. Keep your sentences short, clear, and easy to understand during a panic.

Turn Structure: In every single response, you MUST follow this exact sequence:
1. Acknowledge their statement to validate their situation (e.g., "I understand," "Help is on the way").
2. Provide an immediate, brief safety instruction.
3. Ask EXACTLY ONE clear follow-up question to gather missing information (e.g., location, injuries).

Proactive Vision: If the caller is unsure of their location or the severity of the disaster, proactively instruct them: "Please upload a photo of your surroundings or the emergency, and I will analyze it for you."

DATA EXTRACTION (NER) & ROUTING:
As you gather information, you must maintain a structured record of the emergency so the React frontend can update the live map and dashboard. Whenever you identify new information, you MUST output a JSON block at the absolute end of your response.

Format the JSON exactly like this structure:
```json
{
  "incident_location": "Extracted street or landmark",
  "coordinates": [latitude, longitude],
  "disaster_type": "Fire, Medical, Accident, Crime, Infrastructure, etc.",
  "departments_required": ["Electrical", "Fire", "Ambulance", "Police", "Disaster Response"],
  "severity": "Low, Medium, High, Critical",
  "extracted_entities": ["list", "of", "key", "details", "like", "bleeding", "live wire"]
}
```
If you can identify the city or area, please provide approximate coordinates [lat, lng] so the dashboard map can focus on the location. If you have no idea, leave it as null.
        """

        # Create chat session with proper configuration
        # For chats.create(), use the model name directly (not with models/ prefix)
        model_name = settings.GEMINI_MODEL
        if model_name.startswith("models/"):
            model_name = model_name.replace("models/", "", 1)

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

        logger.info(
            f"Chat response generated successfully",
            component=ErrorComponent.GEMINI_LLM,
            response_length=len(response.text) if response.text else 0,
        )

        print("[CHAT] → Returning response to frontend")
        print("="*60 + "\n")
        return ChatResponse(text=response.text or "")

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
