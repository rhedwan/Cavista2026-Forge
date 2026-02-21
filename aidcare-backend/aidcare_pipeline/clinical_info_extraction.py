# aidcare_pipeline/clinical_info_extraction.py
import google.generativeai as genai
import json
import os
import time

# Use a specific model name for this task if desired, or the general one
GEMINI_MODEL_CLINICAL_EXTRACT = os.getenv("GEMINI_MODEL_CLINICAL_EXTRACT", "gemini-3-pro-preview")
GOOGLE_API_KEY_CLINICAL = os.environ.get("GOOGLE_API_KEY")

_MODERN_GEMINI_PREFIXES = ("gemini-1.5", "gemini-2", "gemini-3")

def extract_detailed_clinical_information(transcript_text: str) -> dict:
    """
    Extracts detailed clinical information from a doctor-patient consultation transcript.
    """
    if not GOOGLE_API_KEY_CLINICAL:
        print("ERROR: GOOGLE_API_KEY not found for clinical information extraction.")
        return {"error": "Configuration error: Missing Google API Key."}

    try:
        genai.configure(api_key=GOOGLE_API_KEY_CLINICAL)
    except Exception as e:
        return {"error": f"Gemini API key configuration error: {e}"}
        
    model = genai.GenerativeModel(GEMINI_MODEL_CLINICAL_EXTRACT)

    system_instruction = (
        "You are an expert medical information extractor. Your task is to meticulously read the provided "
        "doctor-patient consultation transcript. Extract the following information if present: "
        "Presenting symptoms with any available details (onset, duration, severity, character), "
        "relevant patient medical history, relevant family history, key social history points (e.g., smoking, alcohol), "
        "current medications mentioned by the patient or doctor, and any key physical examination findings verbalized by the doctor."
        "Be concise but capture essential details."
    )
    prompt = f"""
    Consultation Transcript:
    ---
    {transcript_text}
    ---

    Based on the transcript above, extract the clinical information.
    Return the information as a SINGLE JSON object with the following keys (if information for a key is not found, use an empty list [] or empty string "" or null):
    - "presenting_symptoms": (list of strings) e.g., ["headache", "fatigue"]
    - "symptom_details": (object where keys are symptoms and values are string descriptions) e.g., {{"headache": "frontal, throbbing, for 3 days", "fatigue": "generalized, worse in evenings"}}
    - "relevant_medical_history": (list of strings) e.g., ["hypertension diagnosed 2 years ago", "type 2 diabetes on metformin"]
    - "relevant_family_history": (list of strings) e.g., ["mother had breast cancer"]
    - "social_history_highlights": (list of strings) e.g., ["smokes 10 cigarettes/day for 5 years", "no alcohol use"]
    - "current_medications_mentioned": (list of strings) e.g., ["metformin 500mg BID", "amlodipine 5mg OD"]
    - "key_examination_findings_verbalized": (list of strings) e.g., ["BP 150/90 mmHg", "mild bilateral pedal edema"]
    - "allergies_mentioned": (list of strings) e.g., ["penicillin (rash)"]

    If a category is not mentioned, its value should be an empty list [].
    Example for "symptom_details": If "headache" is a symptom, a detail could be "frontal, throbbing, worse with light".
    
    Return ONLY the JSON object.
    JSON Response:
    """
    generation_config = genai.types.GenerationConfig(
        temperature=0.15,
        max_output_tokens=1024, # May need adjustment based on transcript length
        # response_mime_type="application/json" # Recommended for Gemini 1.5 models
    )

    full_prompt_to_send = prompt
    if GEMINI_MODEL_CLINICAL_EXTRACT.startswith(_MODERN_GEMINI_PREFIXES):
        model_instance = genai.GenerativeModel(
            GEMINI_MODEL_CLINICAL_EXTRACT,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
    else: # For gemini-1.0-pro, etc.
        model_instance = model
        full_prompt_to_send = system_instruction + "\n\n" + prompt

    # ... (Add your robust Gemini call and JSON parsing logic here, similar to other Gemini functions) ...
    # ... (This includes retries, cleaning markdown, and parsing the JSON string) ...
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = model_instance.generate_content(full_prompt_to_send)
            raw_json_str = response.parts[0].text.strip() if response.parts else (response.text.strip() if hasattr(response, 'text') else "")
            
            if raw_json_str.startswith("```json"): raw_json_str = raw_json_str[len("```json"):]
            if raw_json_str.startswith("```"): raw_json_str = raw_json_str[len("```"):]
            if raw_json_str.endswith("```"): raw_json_str = raw_json_str[:-len("```")]
            raw_json_str = raw_json_str.strip()

            if not raw_json_str:
                if attempt < max_retries - 1: time.sleep(1); continue
                return {"error": "Gemini returned an empty string for clinical info extraction."}
            
            extracted_info = json.loads(raw_json_str)
            # Ensure all expected keys exist, defaulting to empty lists/objects if not
            default_structure = {
                "presenting_symptoms": [], "symptom_details": {}, "relevant_medical_history": [],
                "relevant_family_history": [], "social_history_highlights": [],
                "current_medications_mentioned": [], "key_examination_findings_verbalized": [],
                "allergies_mentioned": []
            }
            # Merge ensures all keys are present, preferring Gemini's output
            final_info = {**default_structure, **extracted_info}
            return final_info

        except json.JSONDecodeError as e:
            print(f"Clinical Info Extractor - JSONDecodeError (Attempt {attempt+1}): {raw_json_str} | Error: {e}")
            if attempt < max_retries - 1: time.sleep(2 * (attempt + 1)); continue
            return {"error": f"Failed to decode JSON for clinical info. Last response: {raw_json_str}"}
        except Exception as e:
            print(f"Clinical Info Extractor - Exception (Attempt {attempt+1}): {e}")
            if attempt < max_retries -1: time.sleep(2 * (attempt + 1)); continue
            return {"error": f"Unhandled error during clinical info extraction: {e}"}
            
    return {"error": "Failed clinical info extraction after all retries."}