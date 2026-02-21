# prepare_clinical_kb.py
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# --- Configuration ---
# _PROJECT_ROOT determination was duplicated, let's fix and use the one from your scripts/ dir assumption
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # This is scripts/
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR) # This is aidcare-backend/
DATA_SOURCE_DIR = os.path.join(_PROJECT_ROOT, "data", "source_documents")


# Input file paths for clinical KB
TEXTBOOK_FILE_PATHS = [
    os.path.join(DATA_SOURCE_DIR, "medical_textbook_data.json"),
    # os.path.join(DATA_SOURCE_DIR, "another_textbook.json"), # Example
]
INCLUDE_CHO_IN_CLINICAL = True 
INCLUDE_CHEW_IN_CLINICAL = True
CHO_FILEPATH = os.path.join(DATA_SOURCE_DIR, "national_standing_orders_cho.json")
CHEW_FILEPATH = os.path.join(DATA_SOURCE_DIR, "national_standing_orders_chew.json")

# *** CORRECTED OUTPUT PATHS FOR CLINICAL KB ***
OUTPUT_KB_DIR_CLINICAL = os.path.join(_PROJECT_ROOT, "data", "kb_clinical") # <--- CORRECTED
OUTPUT_INDEX_PATH = os.path.join(OUTPUT_KB_DIR_CLINICAL, "clinical_kb_index.faiss") # <--- CORRECTED
OUTPUT_METADATA_PATH = os.path.join(OUTPUT_KB_DIR_CLINICAL, "clinical_kb_metadata.json") # <--- CORRECTED

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

# --- Helper Functions (load_json_file, create_chunks_from_guideline_entry, create_chunks_from_textbook_disease) ---
# ... (These should be correct as you pasted them) ...
def load_json_file(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File not found at '{filepath}'. Cannot proceed.")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded data from '{filepath}'")
        return data
    except Exception as e:
        print(f"Error loading or processing '{filepath}': {e}")
        return None

def create_chunks_from_guideline_entry(entry, subsection, section, source_doc_name):
    case = entry.get("case", "N/A")
    history_items = entry.get("history", [])
    examination_items = entry.get("examination", [])
    history_text = ". ".join(history_items) if history_items else "No specific history listed."
    examination_text = ". ".join(examination_items) if examination_items else "No specific examination points listed."
    chunk_text = (
        f"Guideline: {source_doc_name}. Section: {section.get('title', 'N/A')}. Age group: {section.get('age_group', '')}. "
        f"Subsection: {subsection.get('title', 'N/A')} (Code: {subsection.get('code', 'N/A')}). "
        f"Case: {case}. History includes: {history_text}. Examination may involve: {examination_text}."
    )
    metadata = {
        "source_type": "Guideline", "source_document_name": source_doc_name,
        "section_title": section.get("title", "N/A"), "age_group": section.get('age_group', ""),
        "subsection_code": subsection.get("code", "N/A"), "subsection_title": subsection.get("title", "N/A"),
        "case": case, "history": history_items, "examination": examination_items,
        "clinical_judgement": entry.get("clinical_judgement", ""), "action": entry.get("action", []),
        "notes": entry.get("notes", []), "original_text_chunk": chunk_text
    }
    return chunk_text, metadata


def create_chunks_from_textbook_disease(disease_entry, textbook_name="Medical Textbook"):
    disease_name = disease_entry.get("disease", "N/A")
    description = disease_entry.get("description", "")
    symptoms_list = disease_entry.get("symptoms", [])
    symptoms_text = ", ".join(symptoms_list) if symptoms_list else "Not specified."
    triage_alert = disease_entry.get("contextual_notes", {}).get("triage_alert", "")
    category = disease_entry.get("category", "N/A")
    chunk_text = (
        f"Textbook Information ({textbook_name}). Disease: {disease_name} (Category: {category}). "
        f"Description: {description}. Key Symptoms: {symptoms_text}. "
        f"Also consider: {disease_entry.get('synonyms', [])}. "
        f"Relevant for diagnosis: Clinical findings - {', '.join(disease_entry.get('diagnosis', {}).get('clinical', []))}. "
        f"Investigations - {', '.join(disease_entry.get('diagnosis', {}).get('investigations', []))}. "
        f"Triage Alert: {triage_alert}."
    )
    metadata = {
        "source_type": "Textbook",
        "source_document_name": disease_entry.get("source", {}).get("textbook", textbook_name),
        "disease_info": disease_entry, "original_text_chunk": chunk_text
    }
    return chunk_text, metadata

# --- End Helper Functions ---

def build_clinical_knowledge_base():
    print("--- Starting Clinical Support Knowledge Base Preparation ---")
    all_chunks = []
    all_metadata = []

    # 1. Optionally Process CHO Guidelines
    if INCLUDE_CHO_IN_CLINICAL:
        # ... (rest of CHO processing logic) ...
        print(f"\nProcessing CHO Guidelines from {CHO_FILEPATH} for Clinical KB...")
        cho_data = load_json_file(CHO_FILEPATH)
        if cho_data and "sections" in cho_data:
            for section in cho_data["sections"]:
                for subsection in section.get("subsections", []):
                    for entry in subsection.get("entries", []):
                        chunk, meta = create_chunks_from_guideline_entry(entry, subsection, section, "CHO Guidelines")
                        all_chunks.append(chunk)
                        all_metadata.append(meta)
        else:
            print(f"Could not process CHO data from {CHO_FILEPATH}")


    # 2. Optionally Process CHEW Guidelines
    if INCLUDE_CHEW_IN_CLINICAL:
        # ... (rest of CHEW processing logic) ...
        print(f"\nProcessing CHEW Guidelines from {CHEW_FILEPATH} for Clinical KB...")
        chew_data = load_json_file(CHEW_FILEPATH)
        if chew_data and "sections" in chew_data:
            for section in chew_data["sections"]:
                for subsection in section.get("subsections", []):
                    for entry in subsection.get("entries", []):
                        chunk, meta = create_chunks_from_guideline_entry(entry, subsection, section, "CHEW Guidelines")
                        all_chunks.append(chunk)
                        all_metadata.append(meta)
        else:
            print(f"Could not process CHEW data from {CHEW_FILEPATH}")

    # 3. Process Medical Textbook Data
    for tb_path in TEXTBOOK_FILE_PATHS:
        # ... (rest of textbook processing logic) ...
        if os.path.exists(tb_path):
            textbook_name_from_file = os.path.splitext(os.path.basename(tb_path))[0].replace('_', ' ').title()
            print(f"\nProcessing Textbook '{textbook_name_from_file}' from {tb_path}...")
            textbook_data = load_json_file(tb_path)
            if textbook_data and isinstance(textbook_data, list):
                for disease_entry in textbook_data:
                    chunk, meta = create_chunks_from_textbook_disease(disease_entry, textbook_name=textbook_name_from_file)
                    all_chunks.append(chunk)
                    all_metadata.append(meta)
            elif textbook_data:
                print(f"Textbook data from {tb_path} is not in the expected list format.")
        else:
            print(f"Textbook file not found, skipping: {tb_path}")


    if not all_chunks: # ... (rest of the script is the same) ...
        print("No text chunks created for Clinical KB. Exiting.")
        return

    print(f"\nTotal Clinical Support text chunks created: {len(all_chunks)}")

    print(f"\nLoading sentence transformer model: {EMBEDDING_MODEL_NAME}...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print("Model loaded.")

    print("Generating Clinical KB embeddings... (This may take a while)")
    chunk_embeddings = model.encode(all_chunks, show_progress_bar=True, convert_to_numpy=True)
    
    dimension = chunk_embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(chunk_embeddings)
    print(f"Clinical KB FAISS index created. Total vectors: {index.ntotal}")

    # *** Ensure this uses OUTPUT_KB_DIR_CLINICAL if you defined it ***
    # Or just ensure OUTPUT_INDEX_PATH and OUTPUT_METADATA_PATH are correct for clinical
    output_dir = os.path.dirname(OUTPUT_INDEX_PATH) # This uses the global OUTPUT_INDEX_PATH
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory for Clinical KB: {output_dir}")
        
    print(f"\nSaving Clinical KB FAISS index to: {OUTPUT_INDEX_PATH}")
    faiss.write_index(index, OUTPUT_INDEX_PATH)
    print(f"Saving Clinical KB metadata to: {OUTPUT_METADATA_PATH}")
    with open(OUTPUT_METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2)

    print("\n--- Clinical Support Knowledge Base Preparation Complete! ---")


if __name__ == "__main__":

    # To make sure the script uses its intended output paths without relying on external changes:
    # global OUTPUT_INDEX_PATH, OUTPUT_METADATA_PATH # Allow modification of globals for this run
    OUTPUT_KB_DIR_CLINICAL = os.path.join(_PROJECT_ROOT, "data", "kb_clinical")
    OUTPUT_INDEX_PATH = os.path.join(OUTPUT_KB_DIR_CLINICAL, "clinical_kb_index.faiss")
    OUTPUT_METADATA_PATH = os.path.join(OUTPUT_KB_DIR_CLINICAL, "clinical_kb_metadata.json")

    build_clinical_knowledge_base()