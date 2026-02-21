# aidcare_pipeline/clinical_support_generation.py
import google.generativeai as genai
import json
import os
import time

GEMINI_MODEL_CLINICAL_SUPPORT = os.getenv("GEMINI_MODEL_CLINICAL_SUPPORT", "gemini-3-pro-preview")
# GOOGLE_API_KEY is expected to be loaded by main.py and genai configured there,
# but functions should ideally be self-contained or clearly state assumptions.
# For this setup, main.py will handle genai.configure().

_MODERN_GEMINI_PREFIXES = ("gemini-1.5", "gemini-2", "gemini-3")

def generate_clinical_support_details(
    extracted_clinical_info: dict, 
    retrieved_knowledge_entries: list,
    manual_context_supplement: str = "",
    patient_historical_document_texts: list = None # NEW: List of strings from patient's past docs
) -> dict:
    """
    Generates structured clinical support details based on extracted patient info, 
    manual context, RAG results, and historical patient document texts.
    Assumes genai.configure(api_key=...) has been called by the main application.
    """
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        print("ERROR (clinical_support_generation): GOOGLE_API_KEY not found in environment.")
        return {"error": "Configuration error: Missing Google API Key for clinical support generation."}
    # If genai is not configured globally by main.py on startup, configure it here.
    # However, it's better to configure once in main.py.
    # try:
    #     genai.configure(api_key=GOOGLE_API_KEY)
    # except Exception as e:
    #     return {"error": f"Gemini API key configuration error in clinical_support_generation: {e}"}


    model = genai.GenerativeModel(GEMINI_MODEL_CLINICAL_SUPPORT)

    # --- Prepare context from extracted_clinical_info ---
    patient_context_str = "Patient's Current Presentation & Information (from live consultation transcript):\n"
    if extracted_clinical_info.get('presenting_symptoms'):
        patient_context_str += f"- Presenting Symptoms: {', '.join(extracted_clinical_info['presenting_symptoms'])}\n"
    else:
        patient_context_str += "- Presenting Symptoms: None explicitly extracted from transcript.\n"
    
    if extracted_clinical_info.get('symptom_details'):
        patient_context_str += "- Symptom Details (from transcript):\n"
        for symptom, detail in extracted_clinical_info.get('symptom_details', {}).items():
            patient_context_str += f"  - {symptom}: {detail}\n"
    if extracted_clinical_info.get('relevant_medical_history'):
        patient_context_str += f"- Relevant Medical History (from transcript): {', '.join(extracted_clinical_info['relevant_medical_history'])}\n"
    if extracted_clinical_info.get('allergies_mentioned'):
        patient_context_str += f"- Known Allergies (from transcript): {', '.join(extracted_clinical_info['allergies_mentioned'])}\n"
    # You can add more from extracted_clinical_info here, like family history, social, exam findings etc.
    # Example:
    # if extracted_clinical_info.get('key_examination_findings_verbalized'):
    #     patient_context_str += f"- Key Examination Findings (from transcript): {', '.join(extracted_clinical_info['key_examination_findings_verbalized'])}\n"


    if manual_context_supplement and manual_context_supplement.strip():
        patient_context_str += f"\nAdditional Manually Entered Context by Doctor:\n{manual_context_supplement.strip()}\n"
    
    if patient_historical_document_texts: # This is a list of strings (extracted text from past docs)
        patient_context_str += "\nRelevant Excerpts from Patient's Past Uploaded Documents:\n"
        for i, doc_text in enumerate(patient_historical_document_texts):
            doc_text_str = str(doc_text) if doc_text is not None else "No text available for this document."
            patient_context_str += f"--- Document Excerpt {i+1} ---\n{doc_text_str[:500]}...\n" # Show a snippet

    # --- Prepare context from retrieved_knowledge_entries (textbooks, guidelines) ---
    knowledge_context_str = "\nRetrieved Relevant Knowledge Base Information (from general medical literature/guidelines):\n"
    if not retrieved_knowledge_entries:
        knowledge_context_str += "No specific knowledge base entries were retrieved for this presentation.\n"
    else:
        for i, entry in enumerate(retrieved_knowledge_entries[:3]): # Using top 3 relevant entries
            knowledge_context_str += f"\n--- Knowledge Entry {i+1} (Retrieval Score/Distance: {entry.get('retrieval_score (distance)', 'N/A'):.4f}) ---\n"
            knowledge_context_str += f"Source Type: {entry.get('source_type', 'N/A')}\n"
            knowledge_context_str += f"Source Name: {entry.get('source_document_name', 'N/A')}\n"
            if entry.get('source_type') == "Textbook" and entry.get('disease_info'):
                disease = entry['disease_info']
                knowledge_context_str += f"Disease: {disease.get('disease', 'N/A')}\n"
                knowledge_context_str += f"Textbook Symptoms: {', '.join(disease.get('symptoms', []))}\n"
                knowledge_context_str += f"Textbook Investigations: {', '.join(disease.get('diagnosis', {}).get('investigations', []))}\n"
                knowledge_context_str += f"Textbook Treatment (First-line): {', '.join(disease.get('treatment', {}).get('first_line', []))}\n"
                if disease.get('contextual_notes', {}).get('triage_alert'):
                    knowledge_context_str += f"Textbook Triage Alert: {disease['contextual_notes']['triage_alert']}\n"
            elif entry.get('source_type') == "Guideline":
                knowledge_context_str += f"Guideline Case: {entry.get('case', 'N/A')}\n"
                knowledge_context_str += f"Guideline Clinical Judgement: {entry.get('clinical_judgement', 'N/A')}\n"
                knowledge_context_str += f"Guideline Actions: {', '.join(entry.get('action', [])) if isinstance(entry.get('action', []), list) else entry.get('action', '')}\n"
            # Optionally include a snippet of the original chunk text for LLM context
            # if entry.get('original_text_chunk'):
            #     knowledge_context_str += f"Original Chunk Snippet: {entry.get('original_text_chunk', '')[:250]}...\n"


    system_instruction = (
        "You are an AI Clinical Decision Support assistant for medical professionals. "
        "Your role is to synthesize ALL provided patient information (current consultation, manual doctor input, past document excerpts) "
        "and relevant medical knowledge (from provided textbook snippets and guidelines) "
        "to suggest potential conditions, investigations, medication considerations, and highlight alerts. "
        "You do NOT make definitive diagnoses. Prioritize information directly present in the 'Retrieved Relevant Knowledge Base Information' when applicable. "
        "If patient allergies are mentioned (either in current consultation or past documents), strictly consider them for medication suggestions. "
        "The output must be a structured JSON object."
        "Base your reasoning and suggestions primarily on the 'Retrieved Relevant Knowledge Base Information'. "
        "If the knowledge base is sparse for a given patient symptom, state that and suggest general principles or referral if appropriate."
    )
    prompt = f"""
    {patient_context_str}
    {knowledge_context_str}

    Task:
    Based ONLY on ALL the provided patient information (current consultation, manual doctor input, past document excerpts) 
    AND the 'Retrieved Relevant Knowledge Base Information', generate clinical support suggestions.
    Structure your response as a SINGLE JSON object with the following keys:
    - "potential_conditions": (list of objects, each with "name": string, "reasoning": string concise and based on combined patient info and knowledge base, "source_ref": list of strings [e.g., "Textbook: OHCM - Anemia", "Patient Doc: Lab Report 2023-05-10", "Guideline: CHEW 2.3"])
    - "suggested_investigations": (list of objects, each with "test": string, "rationale": string, "source_ref": list of strings)
    - "medication_considerations_info": (list of objects, each with "drug_class_or_info": string, "details": string including allergy considerations or notes on cautious use from guidelines, "source_ref": list of strings). This is for informational purposes, not direct prescription.
    - "alerts_and_flags": (list of strings) Critical points, warnings, or red flags derived from the combined context (e.g., drug interaction based on current & past meds, critical symptom + history, or triage_alerts from textbooks/guidelines).
    - "differential_summary_for_doctor": (string) A concise summary synthesizing all findings and primary considerations for the doctor, highlighting the most likely paths or urgent actions based on the provided context.

    Example for "potential_conditions": [{{"name": "Iron Deficiency Anemia", "reasoning": "Fatigue and pallor from current consult, supported by low Hb in past lab report.", "source_ref": ["Textbook: OHCM - Anemia", "Patient Doc: Lab Report 2023-05-10"]}}]
    If knowledge base information is sparse for a category, provide a general suggestion (e.g., "No specific tests suggested by retrieved knowledge, consider standard workup based on symptoms.") or state that more specific info is needed.
    
    Return ONLY the JSON object. Do not include any text before or after the JSON object.
    JSON Response:
    """

    generation_config = genai.types.GenerationConfig(
        temperature=0.2, # Keep low for factual, clinical context
        max_output_tokens=2048, 
        # response_mime_type="application/json" # Strongly recommended for Gemini 1.5 models
    )

    full_prompt_to_send = prompt # User prompt for Gemini 1.5 with system instruction in model
    model_to_use = model # Default for older models

    if GEMINI_MODEL_CLINICAL_SUPPORT.startswith(_MODERN_GEMINI_PREFIXES):
        # For Gemini 1.5, enabling this helps a lot.
        # Make sure your Google AI Python SDK is up-to-date for this feature.
        # If it causes errors, comment it out and rely on prompt structure.
        # generation_config.response_mime_type="application/json"
        
        model_to_use = genai.GenerativeModel(
            GEMINI_MODEL_CLINICAL_SUPPORT,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
    else: # For older models like gemini-1.0-pro
        model_to_use = model # Use the already initialized model
        full_prompt_to_send = system_instruction + "\n\n" + prompt # Prepend system instruction to the user prompt
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            print(f"Clinical Support Gen - Attempt {attempt+1} to call Gemini model '{model_to_use.model_name}'...")
            # For debugging the full prompt:
            # if attempt == 0: print(f"Full prompt being sent to Gemini (Clinical Support):\n------\n{full_prompt_to_send}\n------")
            
            response = model_to_use.generate_content(full_prompt_to_send) # Send the user prompt part
            
            raw_json_str = ""
            # Robustly try to get text from response
            if hasattr(response, 'text') and response.text:
                 raw_json_str = response.text.strip()
            elif response.parts:
                raw_json_str = response.parts[0].text.strip()
            else:
                print(f"Clinical Support Gen - Warning: Gemini response has no text or parts (Attempt {attempt+1}). Response object: {response}")

            # Clean markdown fences (Gemini sometimes wraps JSON in them)
            if raw_json_str.startswith("```json"): raw_json_str = raw_json_str[len("```json"):]
            if raw_json_str.startswith("```"): raw_json_str = raw_json_str[len("```"):] # General markdown fence
            if raw_json_str.endswith("```"): raw_json_str = raw_json_str[:-len("```")]
            raw_json_str = raw_json_str.strip()
            
            print(f"Clinical Support Gen - Raw Gemini response snippet (Attempt {attempt+1}): {raw_json_str[:300]}...")

            if not raw_json_str:
                if attempt < max_retries - 1: 
                    print(f"Clinical Support Gen - Gemini returned empty string, retrying (Attempt {attempt+1})...")
                    time.sleep(1 * (attempt + 1)) # Exponential backoff
                    continue
                print("Clinical Support Gen - Gemini returned an empty string after retries.")
                return {"error": "Gemini returned an empty response for clinical support generation."}
            
            support_details = json.loads(raw_json_str)
            # Basic validation of expected structure
            expected_keys = ["potential_conditions", "suggested_investigations", "medication_considerations_info", "alerts_and_flags", "differential_summary_for_doctor"]
            missing_keys = [key for key in expected_keys if key not in support_details]
            if missing_keys:
                print(f"Clinical Support Gen - Warning: Response missing keys: {', '.join(missing_keys)}. Got keys: {list(support_details.keys())}")
                # You might want to fill missing keys with default empty values or retry
                for key in missing_keys:
                    support_details[key] = [] if key != "differential_summary_for_doctor" else "" # Default values
            return support_details

        except json.JSONDecodeError as e:
            print(f"Clinical Support Gen - JSONDecodeError (Attempt {attempt+1}): '{raw_json_str}'. Error: {e}")
            if attempt < max_retries - 1: time.sleep(2 * (attempt + 1)); continue
            return {"error": f"Failed to decode JSON for clinical support after retries. Last response snippet: {raw_json_str[:200]}"}
        except Exception as e:
            print(f"Clinical Support Gen - Exception (Attempt {attempt+1}): {e}")
            import traceback
            traceback.print_exc()
            if "rate limit" in str(e).lower() or "quota" in str(e).lower() or "429" in str(e).lower() or "resource has been exhausted" in str(e).lower():
                print("Rate limit, quota, or resource exhaustion error detected.")
                if attempt < max_retries - 1: time.sleep(10 * (attempt + 1)); continue 
            elif attempt < max_retries -1: time.sleep(2 * (attempt + 1)); continue
            return {"error": f"Unhandled error during clinical support generation: {str(e)}"}
            
    return {"error": "Failed clinical support generation after all retries."}