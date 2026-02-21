# aidcare_pipeline/recommendation.py
# Triage recommendation generation via OpenAI GPT-4o-mini with native JSON mode
# Replaces Gemini — better JSON compliance, faster, same multilingual support
# Same function signature kept for full backward compatibility

import json
import os
import time
from .rate_limiter import cached_gemini_call, RateLimitExceeded

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_RECOMMEND = os.getenv("OPENAI_MODEL_RECOMMEND", "gpt-4o-mini")


@cached_gemini_call(ttl=3600, rate_limit_id="recommendation")
def generate_triage_recommendation(
    symptoms_list: list,
    retrieved_guideline_entries: list,
    language: str = "en"
) -> dict:
    """
    Generate a triage recommendation from symptoms and FAISS-retrieved guidelines.

    Args:
        symptoms_list: English symptom strings from extraction step
        retrieved_guideline_entries: Top-N FAISS guideline entries
        language: Target language code for response values ('en'|'ha'|'yo'|'ig'|'pcm')

    Returns:
        dict with keys: summary_of_findings, recommended_actions_for_chw,
                        urgency_level, key_guideline_references,
                        important_notes_for_chw, evidence_based_notes
    """
    if not OPENAI_API_KEY:
        return {"error": "Configuration error: Missing OPENAI_API_KEY for recommendations."}

    # ---------- Resolve language name + multilingual system instruction ----------
    lang_name = "English"
    lang_system_prefix = ""
    if language and language != "en":
        try:
            from aidcare_pipeline.multilingual import LANGUAGE_TRIAGE_SYSTEM_INSTRUCTIONS, _language_name
            lang_instruction = LANGUAGE_TRIAGE_SYSTEM_INSTRUCTIONS.get(language)
            if lang_instruction:
                lang_system_prefix = lang_instruction + "\n\n"
            lang_name = _language_name(language)
        except ImportError:
            lang_name = language

    # ---------- Build guideline context string ----------
    context_str = "Relevant Guideline Information:\n"
    if not retrieved_guideline_entries:
        context_str += (
            "No specific guideline entries were retrieved. Base recommendation on general "
            "knowledge for the given symptoms, or state that specific guidelines are needed.\n"
        )
    else:
        for i, entry in enumerate(retrieved_guideline_entries[:3]):
            context_str += f"\n--- Guideline Entry {i+1} ---\n"
            context_str += f"Source Document: {entry.get('source_document', 'N/A')}\n"
            context_str += f"Section: {entry.get('section_title', 'N/A')}\n"
            context_str += f"Subsection: {entry.get('subsection_title', 'N/A')} (Code: {entry.get('subsection_code', 'N/A')})\n"
            context_str += f"Case/Condition: {entry.get('case', 'N/A')}\n"
            context_str += f"Clinical Judgement from Guideline: {entry.get('clinical_judgement', 'N/A')}\n"
            actions = entry.get('action', [])
            if isinstance(actions, list):
                context_str += f"Recommended Actions from Guideline: {'; '.join(actions)}\n"
            else:
                context_str += f"Recommended Actions from Guideline: {actions}\n"
            notes = entry.get('notes', [])
            if notes:
                if isinstance(notes, list):
                    context_str += f"Notes from Guideline: {'; '.join(notes)}\n"
                else:
                    context_str += f"Notes from Guideline: {notes}\n"

    symptoms_str = ", ".join(symptoms_list) if symptoms_list else "No specific symptoms reported."

    # ---------- Language mandate ----------
    if language != "en":
        lang_mandate = (
            f"\n\nCRITICAL LANGUAGE INSTRUCTION: Write ALL JSON values in {lang_name}. "
            f"Keep JSON keys exactly as specified in English. "
            f"Do not use English in any JSON value."
        )
    else:
        lang_mandate = ""

    # ---------- System instruction ----------
    system_instruction = (
        lang_system_prefix
        + "You are an AI Medical Assistant for Community Health Workers (CHWs) in Nigeria, "
        "designed to provide triage recommendations. "
        "Your response MUST be strictly grounded in the provided 'Relevant Guideline Information'. "
        "If additional evidence-based context from recent medical literature is provided, "
        "you may reference it to support your recommendations. "
        "Do NOT invent information or actions not present in the guidelines or provided context. "
        "You do NOT make definitive diagnoses. You help the CHW determine appropriate next steps. "
        "The output should be clear, concise, and directly actionable for a CHW. "
        "Determine an urgency level based on the guidelines (e.g., 'Routine Care', "
        "'Refer to Clinic', 'Urgent Referral to Hospital', 'Immediate Emergency Care/Referral')."
    )

    # ---------- User prompt ----------
    prompt = f"""Patient Symptoms:
{symptoms_str}

{context_str}
Task:
Based ONLY on the patient symptoms and the provided Relevant Guideline Information (and any additional evidence-based context), generate a triage recommendation for the CHW.
Return ONLY a JSON object with these exact keys:
- "summary_of_findings": (string) Brief summary referencing the most relevant guideline entry.
- "recommended_actions_for_chw": (list of strings) Numbered step-by-step actions from the guideline.
- "urgency_level": (string) Urgency based on clinical judgement (e.g. "Routine Care", "Refer to Clinic", "Urgent Referral to Hospital", "Immediate Emergency Referral").
- "key_guideline_references": (list of strings) Source documents and codes used.
- "important_notes_for_chw": (list of strings) Critical notes for the CHW.
- "evidence_based_notes": (string) Any supporting evidence notes.
{lang_mandate}"""

    print(f"Sending recommendation request to {OPENAI_MODEL_RECOMMEND} (language: {lang_name})...")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)

            response = client.chat.completions.create(
                model=OPENAI_MODEL_RECOMMEND,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.15,
                max_tokens=1536,
                response_format={"type": "json_object"},  # Native JSON mode
            )

            raw = response.choices[0].message.content.strip()
            recommendation_json = json.loads(raw)

            # Basic validation
            expected_keys = ["summary_of_findings", "recommended_actions_for_chw",
                             "urgency_level", "key_guideline_references"]
            if not all(k in recommendation_json for k in expected_keys):
                print(f"Warning: Response missing expected keys. Got: {list(recommendation_json.keys())}")

            print(f"Recommendation generated successfully.")
            return recommendation_json

        except json.JSONDecodeError as e:
            print(f"JSON decode error in recommendation (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return {"error": f"Failed to decode JSON from recommendation model: {e}"}
        except Exception as e:
            print(f"Error during recommendation call (attempt {attempt+1}): {e}")
            if "rate_limit" in str(e).lower() or "429" in str(e):
                time.sleep(10 * (attempt + 1))
            elif attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                return {"error": f"Recommendation generation failed: {e}"}

    return {"error": "Failed to generate recommendation after all retries."}
