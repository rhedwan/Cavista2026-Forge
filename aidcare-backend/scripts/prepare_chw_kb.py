# prepare_chw_kb.py
import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# --- Configuration ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR) # aidcare-backend
DATA_SOURCE_DIR = os.path.join(_PROJECT_ROOT, "data", "source_documents")

CHO_FILEPATH = os.path.join(DATA_SOURCE_DIR, "national_standing_orders_cho.json")
CHEW_FILEPATH = os.path.join(DATA_SOURCE_DIR, "national_standing_orders_chew.json")

OUTPUT_KB_DIR = os.path.join(_PROJECT_ROOT, "data", "kb_chw") # This is correct for CHW
OUTPUT_INDEX_PATH = os.path.join(OUTPUT_KB_DIR, "chw_guidelines_index.faiss") # Correct
OUTPUT_METADATA_PATH = os.path.join(OUTPUT_KB_DIR, "chw_guidelines_metadata.json")

EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

# --- Helper Functions ---
def load_json_file(filepath):
    # ... (same as before) ...
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
    # ... (same as create_chunks_from_cho_chew_entry from previous script) ...
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
        "section_title": section.get("title", "N/A"), "age_group": section.get("age_group", ""),
        "subsection_code": subsection.get("code", "N/A"), "subsection_title": subsection.get("title", "N/A"),
        "case": case, "history": history_items, "examination": examination_items,
        "clinical_judgement": entry.get("clinical_judgement", ""), "action": entry.get("action", []),
        "notes": entry.get("notes", []), "original_text_chunk": chunk_text
    }
    return chunk_text, metadata
# --- End Helper Functions ---

def build_chw_knowledge_base():
    print("--- Starting CHW Knowledge Base Preparation ---")
    all_chunks = []
    all_metadata = []

    # 1. Process CHO Guidelines
    print(f"\nProcessing CHO Guidelines from {CHO_FILEPATH}...")
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

    # 2. Process CHEW Guidelines
    print(f"\nProcessing CHEW Guidelines from {CHEW_FILEPATH}...")
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

    if not all_chunks:
        print("No text chunks created for CHW KB. Exiting.")
        return

    print(f"\nTotal CHW text chunks created: {len(all_chunks)}")

    # 3. Load Model, Generate Embeddings, Create Index
    print(f"\nLoading sentence transformer model: {EMBEDDING_MODEL_NAME}...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print("Model loaded.")

    print("Generating CHW embeddings... (This may take a while)")
    chunk_embeddings = model.encode(all_chunks, show_progress_bar=True, convert_to_numpy=True)
    
    dimension = chunk_embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(chunk_embeddings)
    print(f"CHW FAISS index created. Total vectors: {index.ntotal}")

    # 4. Save output files
    output_dir = os.path.dirname(OUTPUT_INDEX_PATH)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory for CHW KB: {output_dir}")

    print(f"\nSaving CHW FAISS index to: {OUTPUT_INDEX_PATH}")
    faiss.write_index(index, OUTPUT_INDEX_PATH)
    print(f"Saving CHW metadata to: {OUTPUT_METADATA_PATH}")
    with open(OUTPUT_METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2)

    print("\n--- CHW Knowledge Base Preparation Complete! ---")

if __name__ == "__main__":
    build_chw_knowledge_base()