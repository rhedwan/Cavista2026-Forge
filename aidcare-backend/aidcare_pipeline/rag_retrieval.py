# aidcare_pipeline/rag_retrieval.py
import json
import os
import faiss
import numpy as np # faiss returns numpy arrays for distances and indices
from sentence_transformers import SentenceTransformer
from typing import Dict, List, Any, Optional

# --- Configuration for Model Name (can be overridden by environment variable) ---
EMBEDDING_MODEL_NAME_RAG = os.getenv("EMBEDDING_MODEL_RAG", 'all-MiniLM-L6-v2')

# --- Path Definitions ---
# Determine the project root directory based on the location of this file
# This assumes rag_retrieval.py is in aidcare_pipeline/, which is in aidcare-backend/
_PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_PIPELINE_DIR) # This should resolve to your 'aidcare-backend' root

# Default paths for CHW Knowledge Base files
DEFAULT_CHW_INDEX_PATH = os.path.join(_PROJECT_ROOT, "data", "kb_chw", "chw_guidelines_index.faiss")
DEFAULT_CHW_METADATA_PATH = os.path.join(_PROJECT_ROOT, "data", "kb_chw", "chw_guidelines_metadata.json")

# Default paths for Clinical Support Knowledge Base files
DEFAULT_CLINICAL_INDEX_PATH = os.path.join(_PROJECT_ROOT, "data", "kb_clinical", "clinical_kb_index.faiss")
DEFAULT_CLINICAL_METADATA_PATH = os.path.join(_PROJECT_ROOT, "data", "kb_clinical", "clinical_kb_metadata.json")


# --- RAG Retriever Class ---
class GuidelineRetriever:
    def __init__(self, index_path: str, metadata_path: str, model_name: str = EMBEDDING_MODEL_NAME_RAG):
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index file not found at: {index_path}")
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found at: {metadata_path}")

        print(f"GuidelineRetriever: Loading FAISS index from: {index_path}")
        self.index = faiss.read_index(index_path)
        print(f"GuidelineRetriever: FAISS index loaded. Total vectors: {self.index.ntotal}")

        print(f"GuidelineRetriever: Loading metadata from: {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)
        print(f"GuidelineRetriever: Metadata loaded. Total entries: {len(self.metadata)}")

        if self.index.ntotal == 0:
            print(f"Warning: FAISS index at {index_path} is empty (0 vectors). Retrieval will not work.")
        elif self.index.ntotal != len(self.metadata):
            print(f"Warning: Mismatch! FAISS index ({self.index.ntotal} vectors) "
                  f"and metadata ({len(self.metadata)} entries) for paths: {index_path}, {metadata_path}")

        print(f"GuidelineRetriever: Loading sentence transformer model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print(f"GuidelineRetriever: Sentence transformer model '{model_name}' loaded.")

    def retrieve_relevant_guidelines(self, symptoms_list: list, top_k: int = 3) -> list:
        if not symptoms_list:
            print("GuidelineRetriever: Empty symptoms list provided. Cannot retrieve guidelines.")
            return []
        if self.index.ntotal == 0:
            print("GuidelineRetriever: FAISS index is empty. Cannot retrieve guidelines.")
            return []

        query_text = f"Patient symptoms: {', '.join(symptoms_list)}."
        # print(f"GuidelineRetriever: Constructed query for retrieval: \"{query_text}\"") # Can be verbose

        query_embedding = self.model.encode([query_text], convert_to_numpy=True)
        
        # print(f"GuidelineRetriever: Searching FAISS index for top {top_k} results...")
        distances, indices = self.index.search(query_embedding, k=min(top_k, self.index.ntotal)) # Ensure k is not > ntotal
        
        retrieved_entries = []
        if indices.size > 0:
            for i in range(indices.shape[1]): # Iterate through the number of results found for the query
                retrieved_idx = indices[0][i]
                if 0 <= retrieved_idx < len(self.metadata):
                    entry_metadata = self.metadata[retrieved_idx].copy() # Return a copy to avoid modifying cached metadata
                    entry_metadata['retrieval_score (distance)'] = float(distances[0][i])
                    retrieved_entries.append(entry_metadata)
                else:
                    print(f"GuidelineRetriever Warning: Retrieved index {retrieved_idx} is out of bounds for metadata (size {len(self.metadata)}).")
        
        # print(f"GuidelineRetriever: Retrieved {len(retrieved_entries)} guideline entries.")
        return retrieved_entries

# --- Global Instances for Singleton Pattern (loaded once per application lifecycle) ---
chw_retriever_instance: GuidelineRetriever | None = None
clinical_retriever_instance: GuidelineRetriever | None = None

def get_chw_retriever() -> GuidelineRetriever:
    global chw_retriever_instance
    if chw_retriever_instance is None:
        print("Initializing CHW GuidelineRetriever instance...")
        # Use environment variables for paths if set, otherwise use defaults
        idx_path = os.getenv("CHW_FAISS_INDEX_PATH", DEFAULT_CHW_INDEX_PATH)
        meta_path = os.getenv("CHW_METADATA_PATH", DEFAULT_CHW_METADATA_PATH)
        print(f"CHW Retriever will use index: {idx_path}, metadata: {meta_path}")
        chw_retriever_instance = GuidelineRetriever(index_path=idx_path, metadata_path=meta_path)
    return chw_retriever_instance

def get_clinical_retriever() -> GuidelineRetriever:
    global clinical_retriever_instance
    if clinical_retriever_instance is None:
        print("Initializing Clinical Support GuidelineRetriever instance...")
        idx_path = os.getenv("CLINICAL_FAISS_INDEX_PATH", DEFAULT_CLINICAL_INDEX_PATH)
        meta_path = os.getenv("CLINICAL_METADATA_PATH", DEFAULT_CLINICAL_METADATA_PATH)
        print(f"Clinical Retriever will use index: {idx_path}, metadata: {meta_path}")
        clinical_retriever_instance = GuidelineRetriever(index_path=idx_path, metadata_path=meta_path)
    return clinical_retriever_instance


# --- Hybrid Knowledge Retriever (FAISS + Valyu) ---
class HybridKnowledgeRetriever:
    """
    Intelligent hybrid retrieval combining local FAISS and Valyu AI-native search

    Strategy:
    - FAISS: Fast local guideline lookups (always used, offline-capable)
    - Valyu: Real-time research, drug info, clinical trials (selective usage)
    - Graceful degradation when Valyu unavailable
    """

    def __init__(
        self,
        faiss_retriever: GuidelineRetriever,
        valyu_searcher: Optional[Any] = None
    ):
        """
        Initialize hybrid retriever

        Args:
            faiss_retriever: Local FAISS retriever instance
            valyu_searcher: Valyu searcher instance (optional)
        """
        self.faiss_retriever = faiss_retriever
        self.valyu_searcher = valyu_searcher
        self.valyu_enabled = valyu_searcher is not None

        # Usage optimization
        self.valyu_usage_rate = float(os.getenv("VALYU_USAGE_RATE", "0.2"))  # 20% of queries
        self.query_count = 0

        print(f"HybridKnowledgeRetriever initialized (Valyu {'enabled' if self.valyu_enabled else 'disabled'})")

    def should_use_valyu(self, symptoms: List[str], mode: str = "chw") -> bool:
        """
        Determine if Valyu should be used for this query

        Logic:
        - Complex cases (3+ symptoms): Use Valyu
        - Clinical mode: Always use Valyu
        - Simple CHW cases: Random selection based on usage rate
        - Valyu unavailable: Skip

        Args:
            symptoms: List of symptoms
            mode: Triage mode ("chw" or "clinical")

        Returns:
            True if Valyu should be used
        """
        if not self.valyu_enabled:
            return False

        # Clinical mode always uses Valyu
        if mode == "clinical":
            return True

        # Complex cases (3+ symptoms) use Valyu
        if len(symptoms) >= 3:
            return True

        # For simple cases, use random selection based on usage rate
        self.query_count += 1
        use_valyu = (self.query_count % int(1 / self.valyu_usage_rate)) == 0

        return use_valyu

    def retrieve_multi_source(
        self,
        symptoms: List[str],
        mode: str = "chw",
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Retrieve knowledge from multiple sources (FAISS + Valyu)

        Args:
            symptoms: List of symptoms/conditions
            mode: Triage mode ("chw" or "clinical")
            top_k: Number of FAISS results to retrieve

        Returns:
            Dictionary with:
            - faiss_results: Local guideline results
            - valyu_results: Valyu search results (if used)
            - merged_context: Formatted context for LLM
            - knowledge_sources: Source statistics
        """
        print(f"HybridRetriever: Retrieving for symptoms={symptoms}, mode={mode}")

        # Always get FAISS results (local, fast)
        faiss_results = self.faiss_retriever.retrieve_relevant_guidelines(
            symptoms_list=symptoms,
            top_k=top_k
        )

        # Initialize response
        response = {
            "faiss_results": faiss_results,
            "valyu_results": {},
            "merged_context": "",
            "knowledge_sources": {
                "local_guidelines": len(faiss_results),
                "pubmed_research": 0,
                "drug_databases": 0,
                "clinical_trials": 0
            }
        }

        # Determine if we should use Valyu
        use_valyu = self.should_use_valyu(symptoms, mode)

        if use_valyu and self.valyu_searcher:
            print("HybridRetriever: Querying Valyu for enrichment...")

            try:
                # Search medical literature
                literature_results = self.valyu_searcher.search_medical_literature(
                    query_terms=symptoms
                )

                # Search clinical guidelines
                guideline_results = self.valyu_searcher.search_clinical_guidelines(
                    symptoms=symptoms
                )

                # For clinical mode or if drugs mentioned, search drug info
                drug_results = []
                if mode == "clinical" or any(
                    term in " ".join(symptoms).lower()
                    for term in ["drug", "medication", "medicine", "pill"]
                ):
                    drug_results = self.valyu_searcher.search_drug_information(
                        drug_names=symptoms  # Will be refined in actual usage
                    )

                # Store Valyu results
                response["valyu_results"] = {
                    "literature": literature_results,
                    "guidelines": guideline_results,
                    "drugs": drug_results
                }

                # Update source counts
                response["knowledge_sources"]["pubmed_research"] = len(literature_results)
                response["knowledge_sources"]["drug_databases"] = len(drug_results)
                response["knowledge_sources"]["clinical_trials"] = len(guideline_results)

                # Format for LLM context
                valyu_context = self.valyu_searcher.format_for_gemini(response["valyu_results"])
                response["merged_context"] = valyu_context

                print(f"HybridRetriever: Valyu enrichment added ({len(literature_results)} articles, "
                      f"{len(drug_results)} drugs, {len(guideline_results)} guidelines)")

            except Exception as e:
                print(f"HybridRetriever: Valyu query failed (graceful fallback): {e}")
                # Graceful degradation - continue with FAISS only

        else:
            print("HybridRetriever: Using FAISS only (Valyu not triggered)")

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get retrieval statistics"""
        stats = {
            "valyu_enabled": self.valyu_enabled,
            "query_count": self.query_count,
            "valyu_usage_rate": self.valyu_usage_rate
        }

        if self.valyu_searcher:
            stats["valyu_stats"] = self.valyu_searcher.get_stats()

        return stats

# --- Example Usage (for testing this module directly) ---
if __name__ == "__main__":
    print("--- Testing RAG Retrieval Module ---")
    
    # Test CHW Retriever (assuming chw KB files exist)
    print("\n--- Testing CHW Retriever ---")
    try:
        chw_retriever = get_chw_retriever()
        if chw_retriever.index.ntotal > 0:
            test_symptoms_chw = ['fever', 'cough']
            print(f"Querying CHW KB with symptoms: {test_symptoms_chw}")
            results_chw = chw_retriever.retrieve_relevant_guidelines(test_symptoms_chw, top_k=2)
            for i, res in enumerate(results_chw):
                print(f"CHW Result {i+1}: Score {res.get('retrieval_score (distance)'):.4f} - Case: {res.get('case', 'N/A')} (Source: {res.get('source_document_name')})")
        else:
            print("CHW Retriever loaded but index is empty. Cannot test query.")
    except FileNotFoundError as e:
        print(f"Could not initialize CHW Retriever (files might be missing): {e}")
        print(f"Please run 'python scripts/prepare_chw_kb.py' first.")
    except Exception as e:
        print(f"Error testing CHW Retriever: {e}")

    # Test Clinical Retriever (assuming clinical KB files exist)
    print("\n--- Testing Clinical Retriever ---")
    try:
        clinical_retriever = get_clinical_retriever()
        if clinical_retriever.index.ntotal > 0:
            test_symptoms_clinical = ['chronic fatigue', 'weight loss', 'pallor']
            print(f"Querying Clinical KB with symptoms: {test_symptoms_clinical}")
            results_clinical = clinical_retriever.retrieve_relevant_guidelines(test_symptoms_clinical, top_k=2)
            for i, res in enumerate(results_clinical):
                print(f"Clinical Result {i+1}: Score {res.get('retrieval_score (distance)'):.4f} - Disease/Case: {res.get('disease_info', {}).get('disease', res.get('case', 'N/A'))} (Source: {res.get('source_document_name')})")
        else:
            print("Clinical Retriever loaded but index is empty. Cannot test query.")
    except FileNotFoundError as e:
        print(f"Could not initialize Clinical Retriever (files might be missing): {e}")
        print(f"Please run 'python scripts/prepare_clinical_kb.py' first.")
    except Exception as e:
        print(f"Error testing Clinical Retriever: {e}")

    print("\n--- RAG Retrieval Module Test Complete ---")