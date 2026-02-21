import google.generativeai as genai
import json
import os
import time

# --- Configuration ---
# GOOGLE_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # Set as env variable or uncomment
# if "GOOGLE_API_KEY" not in os.environ and not GOOGLE_API_KEY:
#     print("Error: GOOGLE_API_KEY not set.")
#     exit()

GEMINI_MODEL_NAME = "gemini-3-flash-preview"  # Free-tier Gemini 3 model (preview)

# --- Recommendation Generation Function ---
def generate_triage_recommendation(symptoms_list, retrieved_guideline_entries, api_key_to_use):
    """
    Generates a triage recommendation using Gemini, based on symptoms and retrieved guidelines.
    """
    try:
        genai.configure(api_key=api_key_to_use)
    except Exception as e:
        print(f"Error configuring Gemini API key: {e}. Ensure the key is valid.")
        return None

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)

    # 1. Prepare the context from retrieved guidelines for the prompt
    context_str = "Relevant Guideline Information:\n"
    if not retrieved_guideline_entries:
        context_str += "No specific guideline entries were retrieved. Base recommendation on general knowledge for the given symptoms, if possible, or state that specific guidelines are needed.\n"
    else:
        for i, entry in enumerate(retrieved_guideline_entries[:3]): # Use top 3 (or configurable)
            context_str += f"\n--- Guideline Entry {i+1} ---\n"
            context_str += f"Source: {entry.get('source_document', 'N/A')}\n"
            context_str += f"Section: {entry.get('section_title', 'N/A')} - {entry.get('subsection_title', 'N/A')} (Code: {entry.get('subsection_code', 'N/A')})\n"
            context_str += f"Case/Condition: {entry.get('case', 'N/A')}\n"
            context_str += f"Clinical Judgement: {entry.get('clinical_judgement', 'N/A')}\n"
            actions = entry.get('action', [])
            if isinstance(actions, list):
                context_str += f"Recommended Actions from Guideline: {'; '.join(actions)}\n"
            else: # Should be a list, but handle if it's a string
                context_str += f"Recommended Actions from Guideline: {actions}\n"
            # Include notes if available and relevant (especially from CHEW)
            notes = entry.get('notes', [])
            if notes:
                if isinstance(notes, list):
                    context_str += f"Notes: {'; '.join(notes)}\n"
                else:
                    context_str += f"Notes: {notes}\n"


    # 2. Construct the prompt
    symptoms_str = ", ".join(symptoms_list) if symptoms_list else "No specific symptoms reported."

    system_instruction = (
        "You are an AI Medical Assistant for Community Health Workers (CHWs) in Nigeria, designed to provide triage recommendations based on patient symptoms and official CHO/CHEW guidelines. "
        "Your response MUST be grounded in the provided guideline information. "
        "You do NOT make definitive diagnoses. You help the CHW determine the appropriate next steps based on the guidelines."
        "The output should be clear, concise, and directly actionable for a CHW."
        "Determine an urgency level based on the guidelines (e.g., 'Routine Care', 'Refer to Clinic', 'Urgent Referral to Hospital', 'Immediate Emergency Care/Referral')."
    )

    prompt = f"""
    Patient Symptoms:
    {symptoms_str}

    {context_str}

    Task:
    Based ONLY on the patient symptoms and the provided relevant guideline information, generate a triage recommendation for the CHW.
    Structure your response as a JSON object with the following keys:
    - "summary_of_findings": (string) A brief summary of the situation and potential concerns, referencing the guidelines if possible.
    - "recommended_actions_for_chw": (list of strings) Specific, numbered, step-by-step actions the CHW should take, derived primarily from the 'Recommended Actions from Guideline' in the provided context. Prioritize the most relevant guideline entry if multiple are provided.
    - "urgency_level": (string) The determined level of urgency (e.g., "Routine Care", "Monitor at Home", "Refer to Clinic for Assessment", "Urgent Referral to Higher Facility/Hospital", "Immediate Emergency Referral").
    - "key_guideline_references": (list of strings) List the 'Subsection Code' and 'Case' of the primary guideline(s) used for this recommendation (e.g., ["Code: 2.3, Case: Child with fever"]).
    - "important_notes_for_chw": (list of strings, optional) Any critical 'Notes' from the guidelines or other crucial brief reminders for the CHW.

    Example for "recommended_actions_for_chw": ["1. Measure temperature.", "2. If fever > 38.5C, give paracetamol.", "3. Advise on fluid intake."]
    Example for "urgency_level": "Refer to Clinic for Assessment"
    Example for "key_guideline_references": ["Code: 2.3, Case: Child with fever"]

    If the provided guidelines are insufficient or contradictory for the given symptoms, state that and recommend general caution or referral.
    If no symptoms were reported and guidelines suggest routine care, reflect that.

    JSON Response:
    """

    generation_config = genai.types.GenerationConfig(
        temperature=0.2, # Factual and deterministic
        max_output_tokens=1024, # Allow for a more detailed JSON
        # response_mime_type="application/json" # Highly recommended for Gemini 1.5 Flash
    )
    
    if GEMINI_MODEL_NAME.startswith('gemini-1.5'):
        model_instance = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        # If using response_mime_type="application/json" with Gemini 1.5 Flash,
        # set it in generation_config. The response will then be a dict.
        # For now, parsing text, assuming model might not always strictly give JSON with mime_type.
    else: # For gemini-1.0-pro
        model_instance = model
        prompt = system_instruction + "\n\n" + prompt # Prepend system instruction

    print(f"Sending request to Gemini model '{GEMINI_MODEL_NAME}' for recommendation...")
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = model_instance.generate_content(prompt) # Pass generation_config if not on model_instance

            if not response.parts:
                print("Warning: Gemini response has no parts. Raw response:", response)
                if hasattr(response, 'text') and response.text:
                    raw_json_str = response.text.strip()
                else:
                    print("Error: No content found in Gemini response.")
                    if attempt < max_retries - 1: time.sleep(2**attempt); continue
                    return None
            else:
                raw_json_str = response.parts[0].text.strip()

            # Clean markdown fences
            if raw_json_str.startswith("```json"):
                raw_json_str = raw_json_str[len("```json"):]
            if raw_json_str.startswith("```"):
                raw_json_str = raw_json_str[len("```"):]
            if raw_json_str.endswith("```"):
                raw_json_str = raw_json_str[:-len("```")]
            raw_json_str = raw_json_str.strip()
            
            print(f"Raw Gemini response content for recommendation: {raw_json_str}")

            if not raw_json_str:
                print("Warning: Gemini returned an empty string for recommendation.")
                return None
                
            recommendation_json = json.loads(raw_json_str)
            return recommendation_json

        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from Gemini recommendation response: '{raw_json_str}'")
            if attempt < max_retries - 1: time.sleep(2**attempt); continue
            return None
        except Exception as e:
            print(f"An error occurred during Gemini recommendation call: {e}")
            if "rate limit" in str(e).lower() or "quota" in str(e).lower():
                if attempt < max_retries - 1: time.sleep(5 * (attempt+1)); continue
            elif attempt < max_retries -1: time.sleep(2**attempt); continue
            return None
    return None


# --- Main Execution (Example) ---
if __name__ == "__main__":
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("WARNING: GOOGLE_API_KEY environment variable not found.")
        # api_key = "YOUR_MANUAL_TEST_API_KEY" # For local testing only
        if not api_key:
            print("Exiting: API key is required.")
            exit()

    # These would come from previous phases:
    # Phase 3 Output (Symptoms)
    symptoms_from_phase3 = ['difficulty breathing', 'chest pain']
    
    # Phase 4 Output (Retrieved Guideline Entries - mock data for example)
    # In a real pipeline, this comes from GuidelineRetriever.retrieve_relevant_guidelines()
    mock_retrieved_entries = [
        { # Example entry 1 (simulating what RAG retriever would provide)
            "source_document": "CHEW Guidelines",
            "section_title": "ADULT HEALTH CONDITIONS",
            "subsection_title": "DIFFICULTY IN BREATHING",
            "subsection_code": "5.4",
            "case": "Shortness of breath",
            "clinical_judgement": "Possible asthma, COPD or heart failure",
            "action": ["Administer bronchodilator", "Refer severe cases immediately"],
            "notes": ["Oxygen saturation check is important if available."]
        },
        { # Example entry 2
            "source_document": "CHEW Guidelines",
            "section_title": "ADULT HEALTH CONDITIONS",
            "subsection_title": "CHEST PAIN",
            "subsection_code": "5.8",
            "case": "Chest discomfort",
            "clinical_judgement": "Possible angina, reflux, or musculoskeletal",
            "action": ["Administer aspirin if suspected cardiac", "Refer immediately for evaluation"],
            "notes": []
        }
    ]
    
    mock_retrieved_entries_no_symptoms = [
        {
            "source_document": "CHEW Guidelines",
            "section_title": "CHILDHOOD CONDITIONS",
            "subsection_title": "HEALTHY CHILD",
            "subsection_code": "2.2",
            "case": "Well Child Visit",
            "clinical_judgement": "No complaints, normal development",
            "action": ["Reassure caregiver", "Encourage continued breastfeeding or proper diet", "Schedule routine follow-up"],
            "notes": ["Review growth chart."]
        }
    ]

    test_cases = [
        {"symptoms": symptoms_from_phase3, "retrieved_docs": mock_retrieved_entries, "description": "Difficulty Breathing & Chest Pain"},
        {"symptoms": ['fever', 'rash'], "retrieved_docs": [ # Mocking a retrieval for fever/rash
            {
                "source_document": "CHEW Guidelines", "section_title": "CHILDHOOD CONDITIONS",
                "subsection_title": "FEVER", "subsection_code": "2.3", "case": "Child with fever",
                "clinical_judgement": "Suspected infection or malaria",
                "action": ["Treat presumptive malaria if endemic area", "Refer if fever persists > 3 days or danger signs present"],
                "notes": ["Check for rash."]
            },
            {
                "source_document": "CHEW Guidelines", "section_title": "ADULT HEALTH CONDITIONS",
                "subsection_title": "SKIN DISORDERS", "subsection_code": "5.13", "case": "Rash or lesions",
                "clinical_judgement": "Infectious or allergic dermatitis",
                "action": ["Apply topical treatments", "Refer if extensive"],
                "notes": []
            }
        ], "description": "Fever and Rash"},
        {"symptoms": [], "retrieved_docs": mock_retrieved_entries_no_symptoms, "description": "No Symptoms Reported (Routine Checkup)"}
    ]

    for i, test_case in enumerate(test_cases):
        print(f"\n--- Generating Recommendation for Test Case {i+1}: {test_case['description']} ---")
        print(f"Input Symptoms: {test_case['symptoms']}")
        # print(f"Retrieved Guideline Entries (summary):")
        # for entry in test_case['retrieved_docs']:
        # print(f"  - {entry['subsection_code']}: {entry['case']}")
        
        recommendation = generate_triage_recommendation(
            test_case['symptoms'],
            test_case['retrieved_docs'],
            api_key
        )

        if recommendation:
            print("\n--- Generated Triage Recommendation ---")
            print(json.dumps(recommendation, indent=2))
        else:
            print("\nFailed to generate recommendation for this test case.")
        print("-" * 40)
        time.sleep(1) # Avoid hitting API rate limits too quickly

    # Real pipeline would look like:
    # symptoms = extract_symptoms_with_gemini(transcript, api_key)
    # if symptoms:
    #    retrieved_docs = retriever.retrieve_relevant_guidelines(symptoms, top_k=3)
    #    if retrieved_docs:
    #        final_recommendation = generate_triage_recommendation(symptoms, retrieved_docs, api_key)
    #        # Then display final_recommendation in the UI (Phase 6)
    #    else:
    #        # Handle case where no guidelines were retrieved (e.g., provide general advice or ask for more info)
    # else:
    #    # Handle case where no symptoms were extracted