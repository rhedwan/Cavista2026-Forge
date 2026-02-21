# aidcare_pipeline/tts_service.py
# ElevenLabs TTS service for Nigerian language audio generation
# Uses eleven_multilingual_v2 model which supports Hausa, Yoruba, Igbo

import httpx
import os
from typing import Optional

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

# Voice IDs — fill these after auditing the ElevenLabs voice library
# Navigate to elevenlabs.io/voice-library, filter by language, test & pick best voice
LANGUAGE_VOICE_IDS: dict[str, str] = {
    'en':  os.getenv("ELEVENLABS_VOICE_EN",  "EXAVITQu4vr4xnSDxMaL"), # Bella — English
    'ha':  os.getenv("ELEVENLABS_VOICE_HA",  "TBvIh5TNCMX6pQNIcWV8"), # Hausa voice
    'yo':  os.getenv("ELEVENLABS_VOICE_YO",  "9Dbo4hEvXQ5l7MXGZFQA"), # Olufunmilola — Yoruba female
    'ig':  os.getenv("ELEVENLABS_VOICE_IG",  "kMy0Co9mV2JmuSM9VcRQ"), # Igbo voice
    'pcm': os.getenv("ELEVENLABS_VOICE_PCM", "8P18CIVcRlwP98FOjZDm"), # Naija Pidgin voice
}

MAX_CHARS = 2500  # Conservative limit per ElevenLabs tier


async def generate_speech(
    text: str,
    language: str,
    voice_id: Optional[str] = None
) -> bytes:
    """
    Call ElevenLabs TTS API and return raw audio bytes (audio/mpeg).

    Args:
        text: The text to speak (will be truncated intelligently if too long)
        language: Language code — used to select the voice ID if voice_id not provided
        voice_id: Optional override for the voice ID

    Returns:
        Raw audio bytes (audio/mpeg format)

    Raises:
        ValueError: If ELEVENLABS_API_KEY is not set
        httpx.HTTPStatusError: If the ElevenLabs API returns an error
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable is not set")

    effective_voice_id = voice_id or LANGUAGE_VOICE_IDS.get(language, LANGUAGE_VOICE_IDS['en'])

    # Truncate text intelligently at a sentence boundary
    truncated_text = _truncate_at_sentence(text, MAX_CHARS)

    url = f"{ELEVENLABS_API_URL}/{effective_voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": truncated_text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.70,         # higher = steadier, less wavering (0.55 was too low)
            "similarity_boost": 0.75,  # slight reduction prevents over-processed / tinny sound
            "style": 0.0,
            "use_speaker_boost": True,
        },
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.content


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """Truncate text at a sentence boundary, staying under max_chars."""
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    # Try to find a sentence boundary (period, exclamation, question mark)
    for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        idx = truncated.rfind(sep)
        # Only truncate at sentence boundary if it's not too early (>60% of max)
        if idx > max_chars * 0.6:
            return truncated[:idx + 1].strip()

    # Fallback: truncate at last space to avoid cutting a word
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.8:
        return truncated[:last_space].strip()

    return truncated.strip()


def get_voice_id(language: str) -> str:
    """Get the configured voice ID for a language code."""
    return LANGUAGE_VOICE_IDS.get(language, LANGUAGE_VOICE_IDS['en'])
