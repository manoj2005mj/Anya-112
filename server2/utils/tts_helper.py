"""
TTS Helper utilities for multilingual language detection and configuration.
"""

import logging
from typing import Optional
from server2.config import get_settings

logger = logging.getLogger("anya.server2.tts_helper")

# Simple language detection patterns for Indian languages
LANGUAGE_PATTERNS = {
    "hi": ["namaste", "kya", "kaise", "hai", "ji", "ko", "se", "mein", "par", "ke", "liye", "kar", "raha", "hoon"],
    "ta": ["vanakkam", "enna", "yaru", "engae", "irukku", "panra", "mundru", "naan", "ungal", "kita"],
    "te": ["namaskaram", "emi", "elaa", "undi", "chestunnaru", "cheppandi", "nenu", "mee", "thone"],
    "kn": ["namaskara", "enu", "hesaru", "ide", "madtidaare", "heliri", "naanu", "nin", "jote"],
    "bn": ["namaskar", "ki", "kemon", "ache", "tumi", "amar", "hobe", "korchho", "karo"],
    "mr": ["namaskar", "ka", "kase", "aahe", "mi", "tar", "hoil", "kara", "hi"],
}


def detect_language_from_text(text: str) -> Optional[str]:
    """
    Detect language from input text using simple keyword matching.

    Args:
        text: Input text to analyze for language detection

    Returns:
        ISO-639-1 language code (e.g., 'en', 'hi', 'ta') or default language if unable to detect

    Example:
        >>> detect_language_from_text("Namaste, kya haal hai?")
        'hi'
        >>> detect_language_from_text("Hello, how are you?")
        'en'
    """
    settings = get_settings()
    if not text:
        return settings.CARTESIA_DEFAULT_LANGUAGE

    text_lower = text.lower()

    for lang_code, patterns in LANGUAGE_PATTERNS.items():
        if lang_code not in settings.CARTESIA_SUPPORTED_LANGUAGES:
            continue
        # Check if any pattern words appear in the text
        if any(word in text_lower.split() for word in patterns):
            logger.debug(f"Detected language: {lang_code} from text patterns")
            return lang_code

    # Return default language if no patterns matched
    logger.debug(f"No language patterns matched, using default: {settings.CARTESIA_DEFAULT_LANGUAGE}")
    return settings.CARTESIA_DEFAULT_LANGUAGE
