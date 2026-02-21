# aidcare_pipeline/transcription.py
# Audio transcription via OpenAI Whisper API
# Replaces local whisper-base model — eliminates 30-90s CPU bottleneck
# Same function signature kept for full backward compatibility

import os

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Language code map: BCP-47 hints accepted by OpenAI Whisper API
# pcm (Nigerian Pidgin) has no dedicated Whisper model — fall back to English
_WHISPER_LANGUAGE_MAP = {
    'ha': 'ha',   # Hausa
    'yo': 'yo',   # Yoruba
    'ig': 'ig',   # Igbo
    'en': 'en',   # English
    'pcm': 'en',  # Nigerian Pidgin — Whisper uses English as closest match
}


def load_whisper_model():
    """
    No-op — kept for backward compatibility with main.py startup sequence.
    OpenAI Whisper API has no local model to load.
    """
    print("Transcription: Using OpenAI Whisper API (no local model to load).")


def transcribe_audio_local(audio_file_path: str, language: str = None) -> str:
    """
    Transcribe audio using the OpenAI Whisper API.

    Args:
        audio_file_path: Path to the audio file (mp3, wav, webm, m4a, etc.)
        language: Optional BCP-47 language code hint (e.g., 'ha', 'yo', 'ig').
                  Passed to Whisper API for improved accuracy.

    Returns:
        Transcribed text string

    Raises:
        ValueError: If OPENAI_API_KEY is not set
        FileNotFoundError: If the audio file does not exist
        openai.OpenAIError: If the API call fails
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    # Resolve Whisper language code
    whisper_language = None
    if language:
        whisper_language = _WHISPER_LANGUAGE_MAP.get(language, 'en')

    print(f"Transcribing via OpenAI Whisper API: {audio_file_path} "
          f"(language hint: {whisper_language or 'auto-detect'})...")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        with open(audio_file_path, "rb") as audio_file:
            kwargs = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "text",
            }
            if whisper_language:
                kwargs["language"] = whisper_language

            transcript = client.audio.transcriptions.create(**kwargs)

        # When response_format="text", the API returns a plain string
        transcript_text = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
        print(f"Transcription successful ({len(transcript_text)} chars).")
        return transcript_text

    except Exception as e:
        print(f"Error during OpenAI Whisper transcription for {audio_file_path}: {e}")
        raise
