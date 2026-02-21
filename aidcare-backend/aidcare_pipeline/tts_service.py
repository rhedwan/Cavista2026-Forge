# aidcare_pipeline/tts_service.py
# TTS service for Nigerian language audio generation
# - Yoruba: YarnGPT (yarngpt.ai) — native Nigerian voices
# - All other languages: ElevenLabs eleven_multilingual_v2

import httpx
import os
from typing import Optional

# ── ElevenLabs ────────────────────────────────────────────────────────────────
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = "eleven_multilingual_v2"

LANGUAGE_VOICE_IDS: dict[str, str] = {
    'en':  os.getenv("ELEVENLABS_VOICE_EN",  "EXAVITQu4vr4xnSDxMaL"), # Bella — English
    'ha':  os.getenv("ELEVENLABS_VOICE_HA",  "TBvIh5TNCMX6pQNIcWV8"), # Hausa voice
    'ig':  os.getenv("ELEVENLABS_VOICE_IG",  "kMy0Co9mV2JmuSM9VcRQ"), # Igbo voice
    'pcm': os.getenv("ELEVENLABS_VOICE_PCM", "8P18CIVcRlwP98FOjZDm"), # Naija Pidgin voice
}

# ── YarnGPT (Yoruba) ──────────────────────────────────────────────────────────
YARNGPT_API_URL = "https://yarngpt.ai/api/v1/tts"
YARNGPT_VOICE_YO = os.getenv("YARNGPT_VOICE_YO", "Wura")  # Wura — Yoruba, young & sweet

MAX_CHARS = 2000  # YarnGPT limit; ElevenLabs is more lenient but we use the lower cap


async def generate_speech(
    text: str,
    language: str,
    voice_id: Optional[str] = None
) -> bytes:
    """
    Generate speech audio bytes for the given text and language.
    Yoruba ('yo') is routed to YarnGPT; all other languages use ElevenLabs.

    Returns:
        Raw audio bytes (audio/mpeg)
    """
    if language == 'yo':
        return await _yarngpt_generate(text, voice_id or YARNGPT_VOICE_YO)
    return await _elevenlabs_generate(text, language, voice_id)


async def _yarngpt_generate(text: str, voice: str) -> bytes:
    """Call YarnGPT TTS and return raw audio bytes (streamed)."""
    api_key = os.environ.get("YARNGPT_API_KEY")
    if not api_key:
        raise ValueError("YARNGPT_API_KEY environment variable is not set")

    truncated_text = _truncate_at_sentence(text, MAX_CHARS)

    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "text": truncated_text,
        "voice": voice,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", YARNGPT_API_URL, headers=headers, json=payload) as response:
            if not response.is_success:
                error_body = await response.aread()
                raise ValueError(
                    f"YarnGPT API error {response.status_code}: {error_body.decode(errors='replace')}"
                )

            chunks = []
            async for chunk in response.aiter_bytes(chunk_size=8192):
                chunks.append(chunk)
            return b"".join(chunks)


async def _elevenlabs_generate(
    text: str,
    language: str,
    voice_id: Optional[str] = None
) -> bytes:
    """Call ElevenLabs TTS and return raw audio bytes."""
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY environment variable is not set")

    effective_voice_id = voice_id or LANGUAGE_VOICE_IDS.get(language, LANGUAGE_VOICE_IDS['en'])
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
            "stability": 0.70,
            "similarity_boost": 0.75,
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
