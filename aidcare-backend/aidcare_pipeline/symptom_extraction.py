# aidcare_pipeline/symptom_extraction.py
# Symptom extraction via OpenAI GPT-4o-mini with native JSON mode
# Replaces Gemini — faster, native JSON output = zero parsing failures
# Same function signature kept for full backward compatibility

import json
import os
from .rate_limiter import cached_gemini_call, RateLimitExceeded

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_EXTRACTION = os.getenv("OPENAI_MODEL_EXTRACTION", "gpt-4o-mini")

_SYSTEM_INSTRUCTION = (
    "You are an expert medical information extractor for a triage system. "
    "Extract all medical symptoms from patient descriptions and return them as a JSON array. "
    "CRITICAL: Return ONLY a valid JSON object with a single key 'symptoms' containing a list of strings. "
    'Example: {"symptoms": ["fever", "cough", "headache"]}'
)


@cached_gemini_call(ttl=3600, rate_limit_id="symptom_extraction")
def extract_symptoms_with_gemini(transcript_text: str) -> list:
    """
    Extract medical symptoms from a patient transcript using GPT-4o-mini.

    Args:
        transcript_text: Raw patient description in any language

    Returns:
        List of symptom strings (always in English for FAISS compatibility)
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in environment for symptom extraction.")

    prompt = (
        f"Extract all medical symptoms from this patient description:\n\n"
        f"{transcript_text}\n\n"
        f"Return ONLY a JSON object: {{\"symptoms\": [\"symptom1\", \"symptom2\"]}}\n"
        f"If no symptoms found, return: {{\"symptoms\": []}}\n"
        f"All symptoms must be in English regardless of input language."
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=OPENAI_MODEL_EXTRACTION,
            messages=[
                {"role": "system", "content": _SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=512,
            response_format={"type": "json_object"},  # Native JSON mode — zero parsing failures
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)

        # Support both {"symptoms": [...]} and a bare list
        if isinstance(data, list):
            symptoms = data
        elif isinstance(data, dict):
            symptoms = data.get("symptoms", data.get("extracted_symptoms", []))
        else:
            symptoms = []

        cleaned = [str(s).lower().strip() for s in symptoms if str(s).strip()]
        print(f"Extracted {len(cleaned)} symptoms: {cleaned}")
        return cleaned

    except json.JSONDecodeError as e:
        print(f"JSON decode error in symptom extraction: {e}")
        return []
    except Exception as e:
        print(f"Error in GPT-4o-mini symptom extraction: {e}")
        return []
