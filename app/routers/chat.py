from fastapi import APIRouter
from pydantic import BaseModel

from app.services.gemini import get_chat_response

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, object]] | None = None


@router.post("/")
async def chat_endpoint(request: ChatRequest):
    return await get_chat_response(request.message, request.history)
