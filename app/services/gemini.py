import logging

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger("anya.gemini")

settings = get_settings()

client = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options={"api_version": "v1beta"},
)

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

RAG CONTEXT INJECTION:
During the call, the system may inject hidden text prompts starting with "SYSTEM UPDATE:". This is real-time information retrieved from the emergency vector database. Seamlessly weave this new protocol into your next spoken response without acknowledging that you received a system update.

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

MODEL = "models/gemini-2.0-flash"


async def get_chat_response(message: str, history: list | None = None) -> dict:
    try:
        chat = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.4,
            ),
            history=list(history) if history else [],
        )
        response = chat.send_message(message)
        return {"text": response.text or ""}
    except Exception:
        logger.exception("Error in get_chat_response")
        return {"text": "I'm sorry, I'm experiencing a technical issue. Please try again.", "error": True}


async def get_image_analysis(image_path: str) -> dict:
    try:
        upload = client.files.upload(file=image_path)
        if not upload.uri:
            return {"error": "Failed to upload file"}

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_uri(file_uri=upload.uri, mime_type=upload.mime_type),
                        types.Part.from_text(
                            text=(
                                "Analyze this image for emergency assessment. "
                                "Identify any hazards, injuries, or critical details. "
                                "At the end, output a JSON block with incident_location, "
                                "disaster_type, departments_required, severity, and extracted_entities."
                            )
                        ),
                    ],
                )
            ],
        )
        return {"text": response.text or ""}
    except Exception:
        logger.exception("Error in get_image_analysis")
        return {"text": "I could not analyse the image right now. Please describe what you see.", "error": True}

