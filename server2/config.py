"""
Configuration module for server2 backend.
"""

from functools import lru_cache
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for server2 backend"""

    # LiveKit Configuration
    LIVEKIT_URL: str = Field(default="wss://your-cluster.livekit.cloud")
    LIVEKIT_API_KEY: str = Field(default="")
    LIVEKIT_API_SECRET: str = Field(default="")
    LIVEKIT_ROOM_NAME: str = Field(default="emergency-room")

    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # External API Configuration
    RACK_API_BASE_URL: str = Field(default="https://api.example.com/racks")
    ALERT_WEBHOOK_URL: str = Field(default="")

    # Gemini / Google Configuration
    # Using Gemini for LLM and RAG
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-2.0-flash-exp")  # Latest Gemini model

    # RAG Configuration
    RAG_ENABLED: bool = Field(default=True)
    RAG_CHUNK_SIZE: int = Field(default=1000)
    RAG_CHUNK_OVERLAP: int = Field(default=200)
    RAG_TOP_K: int = Field(default=3)  # Number of relevant chunks to retrieve

    # Cartesia TTS Configuration (Multilingual Support)
    CARTESIA_API_KEY: str = Field(default="")
    CARTESIA_MODEL: str = Field(default="sonic-3")
    CARTESIA_VOICE: str = Field(default="794f9389-aac1-45b6-b726-9d9369183238")  # Default voice
    CARTESIA_DEFAULT_LANGUAGE: str = Field(default="en")  # Fallback language (ISO-639-1)
    CARTESIA_SUPPORTED_LANGUAGES: list[str] = Field(
        default=["en", "hi", "ta", "te", "kn", "bn", "mr"]  # English, Hindi, Tamil, Telugu, Kannada, Bengali, Marathi
    )
    CARTESIA_SPEED: float = Field(default=1.0)
    CARTESIA_VOLUME: float = Field(default=1.0)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


_settings_cache: Dict[str, Settings] = {}


@lru_cache
def get_settings() -> Settings:
    """Cached settings getter"""
    if "settings" not in _settings_cache:
        _settings_cache["settings"] = Settings()
    return _settings_cache["settings"]
