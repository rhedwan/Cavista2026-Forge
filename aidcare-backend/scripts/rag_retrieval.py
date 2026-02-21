import json
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# --- Configuration ---
FAISS_INDEX_PATH = "guidelines_index.faiss"
METADATA_PATH = "guidelines_metadata.json"
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # Must be the SAME model used for indexing

# --- RAG Retriever Class ---
class GuidelineRetriever:
    def __init__(self, index_path, metadata_path, model_name):
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index file not found at: {index_path}")
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found at: {metadata_path}")

        print(f"Loading FAISS index from: {index_path}")
        self.index = faiss.read_index(index_path)
        print(f"FAISS index loaded. Total vectors: {self.index.ntotal}")

        print(f"Loading metadata from: {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        print(f"Metadata loaded. Total entries: {len(self.metadata)}")

        if self.index.ntotal != len(self.metadata):
            print("Warning: Mismatch between number of vectors in FAISS index and metadata entries.")
            # This could indicate an issue during the prepare_rag_kb.py step or loading.

        print(f"Loading sentence transformer model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("Sentence transformer model loaded.")

    def retrieve_relevant_guidelines(self, symptoms_list, top_k=3):
        """
        Retrieves the top_k most relevant guideline entries based on a list of symptoms.

        Args:
            symptoms_list (list of str): A list of symptoms (e.g., ['fever', 'cough']).
            top_k (int): The number of top relevant entries to retrieve.

        Returns:
            list of dict: A list of metadata dictionaries for the retrieved entries.
        """
        if not symptoms_list:
            print("Warning: Empty symptoms list provided. Cannot retrieve guidelines.")
            return []
        if self.index.ntotal == 0:
            print("Warning: FAISS index is empty. Cannot retrieve guidelines.")
            return []

        # 1. Construct a query string from the symptoms
        query_text = f"Patient symptoms: {', '.join(symptoms_list)}."
        print(f"\nConstructed query for retrieval: \"{query_text}\"")

        # 2. Generate embedding for the query
        print("Generating query embedding...")
        query_embedding = self.model.encode([query_text], convert_to_numpy=True)

        # 3. Search the FAISS index
        print(f"Searching FAISS index for top {top_k} results...")
        # The search function returns distances and indices
        # distances: array of shape (n_queries, k)
        # indices: array of shape (n_queries, k)
        distances, indices = self.index.search(query_embedding, top_k)
        
        # 4. Compile results
        retrieved_entries = []
        if indices.size > 0: # Check if any results were found
            for i in range(min(top_k, len(indices[0]))): # Iterate up to top_k or actual results found
                retrieved_idx = indices[0][i]
                # Ensure the retrieved index is valid
                if 0 <= retrieved_idx < len(self.metadata):
                    entry_metadata = self.metadata[retrieved_idx]
                    entry_metadata['retrieval_score (distance)'] = float(distances[0][i]) # Add L2 distance
                    retrieved_entries.append(entry_metadata)
                else:
                    print(f"Warning: Retrieved index {retrieved_idx} is out of bounds for metadata.")
        
        print(f"Retrieved {len(retrieved_entries)} guideline entries.")
        return retrieved_entries

# --- Example Usage ---
if __name__ == "__main__":
    try:
        retriever = GuidelineRetriever(
            index_path=FAISS_INDEX_PATH,
            metadata_path=METADATA_PATH,
            model_name=EMBEDDING_MODEL_NAME
        )

        # Symptoms would come from Phase 3 (e.g., Gemini API output)
        test_symptoms_1 = ['headache', 'sore throat', 'weakness', 'fever', 'nasal discharge', 'cough']
        test_symptoms_2 = ['abdominal pain', 'jaundice', 'diarrhea']
        test_symptoms_3 = ['difficulty breathing', 'chest pain'] # From Gemini, correctly handled "no convulsions"
        test_symptoms_4 = ['poor feeding', 'lethargy', 'skin rash']
        test_symptoms_5 = [] # Test empty symptoms list

        symptom_sets_to_test = [
            test_symptoms_1,
            test_symptoms_2,
            test_symptoms_3,
            test_symptoms_4,
            test_symptoms_5
        ]

        for i, symptoms in enumerate(symptom_sets_to_test):
            print(f"\n--- Testing Retrieval for Symptom Set {i+1}: {symptoms} ---")
            if not symptoms:
                print("Input symptoms list is empty.")
                retrieved_data = retriever.retrieve_relevant_guidelines(symptoms, top_k=3)
                print("Result for empty symptoms:", retrieved_data)
                continue

            retrieved_guideline_entries = retriever.retrieve_relevant_guidelines(symptoms, top_k=3)

            if retrieved_guideline_entries:
                print("\nTop Retrieved Guideline Entries:")
                for rank, entry in enumerate(retrieved_guideline_entries):
                    print(f"\nRank {rank + 1} (Score/Distance: {entry.get('retrieval_score (distance)', 'N/A'):.4f}):")
                    print(f"  Source: {entry.get('source_document', 'N/A')}")
                    print(f"  Section: {entry.get('section_title', 'N/A')}")
                    print(f"  Subsection: {entry.get('subsection_title', 'N/A')} (Code: {entry.get('subsection_code', 'N/A')})")
                    print(f"  Case: {entry.get('case', 'N/A')}")
                    print(f"  Clinical Judgement (for Phase 5): {entry.get('clinical_judgement', 'N/A')}")
                    print(f"  Action (for Phase 5): {entry.get('action', [])}")
                    # print(f"  Original Text Snippet: {entry.get('original_text_chunk', '')[:150]}...") # Optional: for debugging
            else:
                print("No relevant guideline entries found for this symptom set.")
            print("-" * 40)
            
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please ensure 'prepare_rag_kb.py' was run successfully and the index/metadata files exist.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")