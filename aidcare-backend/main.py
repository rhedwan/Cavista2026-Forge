# main.py
import os
from dotenv import load_dotenv
load_dotenv()  # Must be called BEFORE any pipeline imports that read os.environ at module level

import asyncio
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import shutil
import time
import json
import uuid

# --- AI pipeline modules ---
from aidcare_pipeline.transcription import transcribe_audio_local, load_whisper_model
from aidcare_pipeline.symptom_extraction import extract_symptoms_with_gemini 
from aidcare_pipeline.clinical_info_extraction import extract_detailed_clinical_information 
from aidcare_pipeline.clinical_support_generation import generate_clinical_support_details
from aidcare_pipeline.document_processing import process_uploaded_document_task 

from aidcare_pipeline.rag_retrieval import (
    get_chw_retriever,
    get_clinical_retriever,
    GuidelineRetriever,
)
from aidcare_pipeline.recommendation import generate_triage_recommendation
from aidcare_pipeline.rate_limiter import get_rate_limit_stats, clear_cache, RateLimitExceeded
from aidcare_pipeline.multilingual import generate_multilingual_response
from aidcare_pipeline.tts_service import generate_speech, get_voice_id
# For Clinical Mode - Step 2 (You'll create this function/module later)
# from aidcare_pipeline.clinical_support_generation import generate_clinical_support_details_with_gemini
from pydantic import BaseModel
from fastapi.responses import Response

from aidcare_pipeline import crud, db_models 
from aidcare_pipeline.database import get_db, engine 
from sqlalchemy.orm import Session

# --- Pydantic Model for Text Input ---
class TranscriptInput(BaseModel):
    transcript_text: str

class ConversationContinueInput(BaseModel):
    conversation_history: str
    latest_message: str

# --- Naija (multilingual) Pydantic models ---
class NaijaConversationInput(BaseModel):
    conversation_history: str
    latest_message: str
    language: str = 'en'  # 'en' | 'ha' | 'yo' | 'ig' | 'pcm'

class NaijaTextInput(BaseModel):
    transcript_text: str
    language: str = 'en'

class TTSRequest(BaseModel):
    text: str
    voice_id: str = ''
    language: str = 'en'

class PatientCreate(BaseModel):
    full_name: str | None = None
    # add other fields for patient creation

class PatientResponse(BaseModel):
    patient_uuid: str
    full_name: str | None
    # ... other fields to return ...
    class Config:
        orm_mode = True
        
# --- Environment Variable Checks & Setup ---
if not os.environ.get("GOOGLE_API_KEY"):
    print("CRITICAL WARNING: GOOGLE_API_KEY environment variable is not set. (checked .env and system env). Gemini calls will fail.")
else:
    print("GOOGLE_API_KEY loaded successfully.")

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOADED_PATIENT_DOCS_DIR = os.path.join(_PROJECT_ROOT, "patient_documents_storage")
os.makedirs(UPLOADED_PATIENT_DOCS_DIR, exist_ok=True)

# --- FastAPI App Initialization & State ---
app = FastAPI(title="AidCare AI Assistant API")
app_state = {} # To store loaded models/retrievers

# --- Lifespan Events for Model Loading ---
@app.on_event("startup")
async def startup_event():
    print("FastAPI app starting up...")
    
    print("Initializing Whisper model...")
    load_whisper_model() # This loads the model into its module's global scope
    
    print("Initializing CHW Guideline Retriever...")
    try:
        app_state["chw_retriever"] = get_chw_retriever()
        if app_state["chw_retriever"] and app_state["chw_retriever"].index.ntotal > 0:
            print(f"CHW Retriever loaded. Index has {app_state['chw_retriever'].index.ntotal} vectors.")
        else:
            print("ERROR: CHW Retriever FAILED to load or index is empty.")
    except Exception as e:
        print(f"CRITICAL ERROR initializing CHW Retriever: {e}")
        # Consider if the app should fail to start if a retriever doesn't load
        # For now, it will continue, but endpoints using it will fail.

    print("Initializing Clinical Support Guideline Retriever...")
    try:
        app_state["clinical_retriever"] = get_clinical_retriever()
        if app_state["clinical_retriever"] and app_state["clinical_retriever"].index.ntotal > 0:
            print(f"Clinical Retriever loaded. Index has {app_state['clinical_retriever'].index.ntotal} vectors.")
        else:
            print("ERROR: Clinical Retriever FAILED to load or index is empty.")
    except Exception as e:
        print(f"CRITICAL ERROR initializing Clinical Retriever: {e}")

    print("FastAPI app startup complete (check logs for retriever status).")

@app.on_event("shutdown")
async def shutdown_event():
    print("FastAPI app shutting down.")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:3001",
        "https://triage.theaidcare.com",      # Production custom domain
        "https://lang.theaidcare.com",        # Naija language demo subdomain
        "https://aidcare-lang.vercel.app",    # Vercel production deployment
    ],
    allow_origin_regex="https://.*\\.vercel\\.app",  # All Vercel preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependencies for Retrievers ---
def get_chw_retriever_dependency() -> GuidelineRetriever:
    retriever = app_state.get("chw_retriever")
    if not retriever:
        print("Error in dependency: CHW Retriever not available in app_state.")
        raise HTTPException(status_code=503, detail="CHW Triage knowledge base not available. Please try again later.")
    return retriever

def get_clinical_retriever_dependency() -> GuidelineRetriever:
    retriever = app_state.get("clinical_retriever")
    if not retriever:
        print("Error in dependency: Clinical Retriever not available in app_state.")
        raise HTTPException(status_code=503, detail="Clinical Support knowledge base not available. Please try again later.")
    return retriever

# --- API Endpoints ---
@app.post("/patients/", response_model=PatientResponse) # Example
def create_new_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    # Check if patient with similar details exists if necessary
    db_patient = crud.create_patient(db=db, full_name=patient.full_name)
    return db_patient

# --- TRANSCRIPTION ONLY ---
@app.post("/transcribe/audio/")
async def transcribe_audio_endpoint(audio_file: UploadFile = File(...)):
    unique_suffix = f"{int(time.time() * 1000)}_transcribe_only_{audio_file.filename}"
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_suffix)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        print(f"Transcription Endpoint - Audio file saved to {file_path}")

        print("Transcription Endpoint - Starting Transcription...")
        transcript = transcribe_audio_local(file_path) # Using your existing function
        
        if transcript is None: # transcribe_audio_local might return None on error or empty string
            raise HTTPException(status_code=500, detail="Transcription failed or produced no output.")
        
        print(f"Transcription Endpoint - Transcription Complete. Length: {len(transcript)}")
        
        return {"transcript": transcript}

    except FileNotFoundError as e:
        print(f"Transcription Endpoint - File not found error: {e}")
        raise HTTPException(status_code=404, detail=f"Required audio file processing error: {e}")
    except Exception as e:
        print(f"Transcription Endpoint - Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal server error occurred during transcription: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Transcription Endpoint - Temporary audio file {file_path} removed.")
            except Exception as e_rem:
                print(f"Transcription Endpoint - Error removing temporary file {file_path}: {e_rem}")
       
# --- PROCESSING PRE-TRANSCRIBED TEXT (CHW Mode) ---
@app.post("/triage/process_text/")
async def process_text_for_triage(
    transcript_input: TranscriptInput, # Use the Pydantic model for request body
    retriever: GuidelineRetriever = Depends(get_chw_retriever_dependency) # Use CHW retriever
):
    transcript = transcript_input.transcript_text
    print(f"Received text for CHW Triage: {transcript[:200]}...") # Log received transcript

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    try:
        # Phase 2 is skipped as we have the transcript

        # --- Phase 3: Symptom Extraction (Gemini API) ---
        print("CHW Text Mode - Starting Phase 3: Symptom Extraction...")
        symptoms = extract_symptoms_with_gemini(transcript)
        if "error" in symptoms if isinstance(symptoms, dict) else False:
            raise HTTPException(status_code=500, detail=f"CHW Text Mode: Symptom extraction failed: {symptoms.get('error')}")
        print(f"CHW Text Mode - Phase 3 Complete. Extracted Symptoms: {symptoms}")

        # --- Phase 4: Knowledge Retrieval (FAISS) ---
        print("CHW Text Mode - Starting Phase 4: Knowledge Retrieval...")
        retrieved_docs = retriever.retrieve_relevant_guidelines(symptoms, top_k=3)
        knowledge_sources = {"local_guidelines": len(retrieved_docs)}
        print(f"CHW Text Mode - Phase 4 Complete. Retrieved {len(retrieved_docs)} guideline documents.")

        # --- Phase 5: Triage Recommendation ---
        print("CHW Text Mode - Starting Phase 5: Recommendation Generation...")
        recommendation = generate_triage_recommendation(
            symptoms,
            retrieved_docs,
        )
        if not recommendation or ("error" in recommendation if isinstance(recommendation, dict) else False):
            error_detail = recommendation.get("error") if isinstance(recommendation, dict) else "Unknown error"
            raise HTTPException(status_code=500, detail=f"CHW Text Mode: Failed to generate recommendation: {error_detail}")
        print("CHW Text Mode - Phase 5 Complete. Recommendation generated.")

        # Build response with Valyu enrichment
        response = {
            "mode": "chw_triage_text_input",
            "input_transcript": transcript,
            "extracted_symptoms": symptoms,
            "retrieved_guidelines_summary": [
                {
                    "source": d.get("source_document_name"),
                    "code": d.get("subsection_code"),
                    "case": d.get("case"),
                    "score": d.get("retrieval_score (distance)")
                }
                for d in retrieved_docs
            ],
            "knowledge_sources": knowledge_sources,
            "triage_recommendation": recommendation
        }

        return response
    except ValueError as e: # For API key issues from Gemini calls etc.
        print(f"Value error in CHW Text Mode: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise e # Re-raise FastAPI's own HTTP exceptions
    except Exception as e:
        print(f"Unhandled error processing text for CHW triage: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

# --- CONTINUE CONVERSATION ENDPOINT (Multi-turn conversation) ---
@app.post("/triage/continue_conversation/")
async def continue_triage_conversation(conversation_input: ConversationContinueInput):
    """
    Endpoint for multi-turn conversation during symptom gathering.
    Uses Gemini to generate follow-up questions based on conversation history.
    """
    conversation_history = conversation_input.conversation_history
    latest_message = conversation_input.latest_message

    if not latest_message or not latest_message.strip():
        raise HTTPException(status_code=400, detail="Latest message cannot be empty.")

    try:
        import google.generativeai as genai

        # Configure Gemini
        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment")

        genai.configure(api_key=GOOGLE_API_KEY)

        # Detect urgency keywords in the conversation
        urgent_keywords = [
            "chest pain", "heart attack", "can't breathe", "difficulty breathing",
            "severe pain", "bleeding heavily", "unconscious", "seizure",
            "stroke", "paralysis", "severe headache", "confusion",
            "severe allergic", "anaphylaxis", "swelling throat", "blue lips"
        ]

        full_conversation = (conversation_history + " " + latest_message).lower()
        is_urgent = any(keyword in full_conversation for keyword in urgent_keywords)

        # Count exchanges (how many back-and-forths)
        exchange_count = conversation_history.count("PATIENT:")

        print("\n" + "="*60)
        print("CONVERSATION CONTINUATION REQUEST")
        print("="*60)
        print(f"Latest Message: {latest_message}")
        print(f"Exchange Count: {exchange_count}")
        print(f"Is Urgent: {is_urgent}")
        print(f"Full Conversation:\n{conversation_history}")
        print("="*60 + "\n")

        # System instruction for conversation
        system_instruction = (
            "You are a medical triage assistant gathering symptom information.\n"
            "\n"
            "ABSOLUTELY NEVER DO THESE:\n"
            "❌ Ask 'Are there any other symptoms?' more than once\n"
            "❌ Ask 'When did it start?' if they already mentioned timing\n"
            "❌ Ask 'How severe is it?' if they already described severity\n"
            "❌ Repeat ANY question\n"
            "\n"
            "YOUR PROCESS:\n"
            "1. Read what the patient has already told you\n"
            "2. Identify ONE piece of missing critical information\n"
            "3. Ask about that ONE thing ONLY\n"
            "4. If you have enough info → tell them to complete assessment\n"
        )

        if is_urgent and exchange_count >= 1:
            # For urgent cases, move to assessment quickly after 1-2 exchanges
            prompt = f"""EMERGENCY SITUATION - REVIEW AND DECIDE

Previous conversation:
{conversation_history}

Latest patient message:
{latest_message}

COUNT OF EXCHANGES SO FAR: {exchange_count}

TASK: Read the conversation above. Write down what you know:
- Main symptom: ___
- Location: ___
- Started when: ___
- Severity: ___
- Other symptoms: ___

DECISION TIME:
A) If you know the main symptom + at least 2 other important details, respond EXACTLY:
"This requires immediate medical attention. Completing your assessment now. [COMPLETE_ASSESSMENT]"

B) If you're missing something CRITICAL (like "is this happening RIGHT NOW?"), ask that ONE question ONLY.

C) NEVER EVER ask "Are there any other symptoms?" if they already told you multiple symptoms.

Your response (A or B only):"""
        else:
            prompt = f"""Previous conversation:
{conversation_history}

Latest patient message:
{latest_message}

STEP 1 - WHAT DO YOU ALREADY KNOW? Write it down:
Main symptoms mentioned: ___
When it started: ___
How severe: ___
Other symptoms: ___

STEP 2 - WHAT'S MISSING?
Look at what you wrote above. What's the ONE most important thing you don't know yet?

STEP 3 - ASK YOUR QUESTION
Ask about that ONE missing thing ONLY.

CRITICAL RULES:
❌ NEVER ask "Are there any other symptoms?" if they already mentioned multiple symptoms
❌ NEVER ask "when did it start" if they said "yesterday" or "30 minutes ago" or any time reference
❌ NEVER ask the same question twice
❌ If they've answered {exchange_count} times already, you probably have enough info. Say: "Thank you. I have enough details now. Please click 'Complete Assessment' to see your results."

Your next question (ONE question only):"""

        # Use Gemini 2.0 Flash with system instruction support
        model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            system_instruction=system_instruction
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.85,
                max_output_tokens=300,
                top_p=0.95
            )
        )

        ai_response = response.text.strip() if response.text else "Can you tell me more about what you're experiencing?"

        # Check if AI wants to complete assessment
        should_complete = "[COMPLETE_ASSESSMENT]" in ai_response or \
                         "completing your assessment now" in ai_response.lower() or \
                         "complete assessment" in ai_response.lower()

        # Remove the marker from response
        ai_response = ai_response.replace("[COMPLETE_ASSESSMENT]", "").strip()

        print("\n" + "="*60)
        print("AI RESPONSE")
        print("="*60)
        print(f"Response: {ai_response}")
        print(f"Should Auto-Complete: {should_complete}")
        print("="*60 + "\n")

        return {
            "response": ai_response,
            "conversation_complete": should_complete,
            "should_auto_complete": should_complete  # Frontend can use this to auto-trigger
        }

    except ValueError as e:
        print(f"Value error in conversation continuation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unhandled error in conversation continuation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")

@app.post("/triage/process_audio/") # For CHW Mode
async def process_audio_for_triage(
    audio_file: UploadFile = File(...),
    retriever: GuidelineRetriever = Depends(get_chw_retriever_dependency) # Use CHW retriever
):
    unique_suffix = f"{int(time.time() * 1000)}_{audio_file.filename}"
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_suffix)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        print(f"Audio file saved to {file_path}")

        print("CHW Mode - Starting Phase 2: Transcription...")
        transcript = transcribe_audio_local(file_path)
        if not transcript:
            raise HTTPException(status_code=500, detail="CHW Mode: Transcription failed or returned empty.")
        print(f"CHW Mode - Phase 2 Complete. Transcript: {transcript[:100]}...")

        print("CHW Mode - Starting Phase 3: Symptom Extraction...")
        symptoms = extract_symptoms_with_gemini(transcript) # Using the CHW-focused symptom extraction
        if "error" in symptoms if isinstance(symptoms, dict) else False:
            raise HTTPException(status_code=500, detail=f"CHW Mode: Symptom extraction failed: {symptoms.get('error')}")
        print(f"CHW Mode - Phase 3 Complete. Extracted Symptoms: {symptoms}")

        print("CHW Mode - Starting Phase 4: Knowledge Retrieval...")
        retrieved_docs = retriever.retrieve_relevant_guidelines(symptoms, top_k=3)
        knowledge_sources = {"local_guidelines": len(retrieved_docs)}
        print(f"CHW Mode - Phase 4 Complete. Retrieved {len(retrieved_docs)} guideline documents.")

        print("CHW Mode - Starting Phase 5: Recommendation Generation...")
        recommendation = generate_triage_recommendation(
            symptoms,
            retrieved_docs,
        )
        if not recommendation or ("error" in recommendation if isinstance(recommendation, dict) else False):
            error_detail = recommendation.get("error") if isinstance(recommendation, dict) else "Unknown error"
            raise HTTPException(status_code=500, detail=f"CHW Mode: Failed to generate recommendation: {error_detail}")
        print("CHW Mode - Phase 5 Complete. Recommendation generated.")

        # Build response with Valyu enrichment
        response = {
            "mode": "chw_triage",
            "transcript": transcript,
            "extracted_symptoms": symptoms,
            "retrieved_guidelines_summary": [
                {
                    "source": d.get("source_document_name"),
                    "code": d.get("subsection_code"),
                    "case": d.get("case"),
                    "score": d.get("retrieval_score (distance)")
                }
                for d in retrieved_docs
            ],
            "knowledge_sources": knowledge_sources,
            "triage_recommendation": recommendation
        }

        return response
    except FileNotFoundError as e:
        print(f"File not found error: {e}")
        raise HTTPException(status_code=404, detail=f"Required file not found: {e}")
    except ValueError as e: 
        print(f"Value error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise e 
    except Exception as e:
        print(f"Unhandled error processing audio for CHW triage: {e}")
        import traceback
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Temporary audio file {file_path} removed.")
            except Exception as e_rem:
                print(f"Error removing temporary file {file_path}: {e_rem}")


# Clinical Support Endpoint
# --- Clinical Support Endpoint (MODIFIED - No patient_uuid in path initially) ---
@app.post("/clinical_support/process_consultation/") # <--- REMOVED {patient_uuid} from path
async def process_consultation_for_clinical_support(
    # patient_uuid: str, # Removed from path parameters for now
    audio_file: UploadFile = File(...),
    manual_context: str = Form(""), 
    # db: Session = Depends(get_db), # We can make DB operations optional for now
    retriever: GuidelineRetriever = Depends(get_clinical_retriever_dependency)
):
    # session_uuid_str = str(uuid.uuid4()) # Still useful for logging/tracking this specific call
    
    unique_audio_suffix = f"{int(time.time() * 1000)}_consult_{audio_file.filename}"
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_audio_suffix)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        print(f"Clinical Support - Audio file saved: {file_path}")

        # Phase 2: Transcription
        print("Clinical Support - Phase 2: Transcription...")
        transcript = transcribe_audio_local(file_path)
        if not transcript:
            raise HTTPException(status_code=500, detail="Clinical Support: Transcription failed or returned empty.")
        print(f"Clinical Support - Phase 2 Complete. Transcript snippet: {transcript[:100]}...")
        
        print(f"Clinical Support - Manual Context Provided: '{manual_context if manual_context.strip() else 'None'}'")

        # --- DB Operations (Make them conditional or skip for now if no patient_uuid) ---
        # if db and patient_uuid_from_somewhere: # If you decide to pass patient_uuid via form data later
        #     db_patient = crud.get_patient_by_uuid(db, patient_uuid=patient_uuid_from_somewhere)
        #     if not db_patient:
        #         print(f"Warning: Patient UUID {patient_uuid_from_somewhere} not found, proceeding without patient context for this session.")
        #     else:
        #         db_session = crud.create_consultation_session(
        #             db=db, patient_id=db_patient.id, mode="clinical_support",
        #             transcript=transcript, 
        #             manual_context_input=manual_context,
        #             session_uuid=session_uuid_str
        #         )
        # else:
        #     print("Clinical Support: No patient UUID or DB session, session will not be saved to DB.")
        # For now, we skip saving the session to DB if no patient_uuid is involved in the request path.
        # ------------------------------------------------------------------------------------
        
        # Clinical Phase 3: Rich Information Extraction
        print("Clinical Support - Clinical Phase 3: Detailed Information Extraction...")
        extracted_info = extract_detailed_clinical_information(transcript)
        if isinstance(extracted_info, dict) and "error" in extracted_info:
             raise HTTPException(status_code=500, detail=f"Clinical Support: Detailed info extraction error: {extracted_info.get('error')}")
        print(f"Clinical Support - Clinical Phase 3 Complete.")

        query_terms_for_rag = extracted_info.get("presenting_symptoms", [])
        if manual_context and manual_context.strip():
            manual_context_keywords = [term for term in manual_context.lower().split() if len(term) > 2] 
            query_terms_for_rag = list(set(query_terms_for_rag + manual_context_keywords))
        
        print("Clinical Support - Phase 4: Knowledge Retrieval...")
        retrieved_docs = []
        if query_terms_for_rag:
            retrieved_docs = retriever.retrieve_relevant_guidelines(query_terms_for_rag, top_k=5)
        print(f"Clinical Support - Phase 4 Complete. Retrieved {len(retrieved_docs)} documents.")

        # patient_historical_document_texts will be empty as we don't have a patient_uuid here
        patient_historical_document_texts = [] 

        print("Clinical Support - Clinical Phase 5: Support Details Generation...")
        support_details = generate_clinical_support_details(
            extracted_clinical_info=extracted_info, 
            retrieved_knowledge_entries=retrieved_docs,
            manual_context_supplement=manual_context,
            patient_historical_document_texts=patient_historical_document_texts # Will be empty for now
        )
        if isinstance(support_details, dict) and "error" in support_details:
            raise HTTPException(status_code=500, detail=f"Clinical Support: Failed to generate support details: {support_details.get('error')}")
        print("Clinical Support - Clinical Phase 5 Complete.")

        # --- DB Update (Conditional or skip for now) ---
        # if db_session: # Only if a session was created
        #     crud.update_consultation_session_results(
        #         db=db, session_uuid=db_session.session_uuid, 
        #         extracted_info=extracted_info, 
        #         retrieved_docs=[{"source_type": d.get("source_type"), ...} for d in retrieved_docs],
        #         final_recommendation=support_details
        #     )
        # ---------------------------------------------

        return {
            "mode": "clinical_support_no_patient_id", # Indicate it's a generic session
            "transcript": transcript,
            "extracted_clinical_info": extracted_info,
            "manual_context_provided": manual_context,
            "retrieved_documents_summary": [
                {"source_type": d.get("source_type"), "source_name": d.get("source_document_name"),
                 "retrieved_content_hint": d.get("disease_info", {}).get("disease") or d.get("case") or "Guideline Entry",
                 "score": d.get("retrieval_score (distance)")} for d in retrieved_docs
            ],
            "clinical_support_details": support_details
        }
    # ... (Keep your existing FileNotFoundError, ValueError, HTTPException, Exception, and finally blocks) ...
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error in clinical support: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception as e_rem: print(f"Error removing temp file {file_path}: {e_rem}")
            
@app.post("/clinical_support/process_consultation/{patient_uuid}/")
async def process_consultation_for_clinical_support(
    patient_uuid: str = str,
    audio_file: UploadFile = File(...),
    manual_context: str = Form(""), 
    db: Session = Depends(get_db),
    retriever: GuidelineRetriever = Depends(get_clinical_retriever_dependency) # Uses clinical_retriever
):
    # Get/Verify Patient
    db_patient = crud.get_patient_by_uuid(db, patient_uuid=patient_uuid)
    if not db_patient:
        raise HTTPException(status_code=404, detail=f"Patient with UUID {patient_uuid} not found.")
    
    session_uuid_str = str(uuid.uuid4())
    
    unique_suffix = f"{int(time.time() * 1000)}_consult_{audio_file.filename}" 
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_suffix)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        print(f"Clinical Support - Audio file saved: {file_path}")

        # Phase 2: Transcription
        print("Clinical Support - Phase 2: Transcription...")
        transcript = transcribe_audio_local(file_path)
        if not transcript: # Check if transcription returned None or empty
            raise HTTPException(status_code=500, detail="Clinical Support: Transcription failed or returned empty.")
        print(f"Clinical Support - Phase 2 Complete. Transcript snippet: {transcript[:100]}...")
        
        print(f"Clinical Support - Manual Context Provided: '{manual_context if manual_context.strip() else 'None'}'")

        db_session = crud.create_consultation_session(
        db=db, patient_id=db_patient.id, mode="clinical_support",
        transcript=transcript, 
        manual_context_input=manual_context, # <--- SAVE IT
        session_uuid=session_uuid_str
    )
        
        # Clinical Phase 3: Rich Information Extraction
        print("Clinical Support - Clinical Phase 3: Detailed Information Extraction...")
        extracted_info = extract_detailed_clinical_information(transcript) # From clinical_info_extraction.py
        if isinstance(extracted_info, dict) and "error" in extracted_info: # Check for error structure
             raise HTTPException(status_code=500, detail=f"Clinical Support: Detailed info extraction error: {extracted_info.get('error')}")
        print(f"Clinical Support - Clinical Phase 3 Complete.") # Log actual extracted_info for debugging if needed

        # Formulate query terms for RAG from extracted info
        query_terms_for_rag = extracted_info.get("presenting_symptoms", [])
        # Optionally add other key terms:
        # query_terms_for_rag.extend(extracted_info.get("key_examination_findings_verbalized", []))
        # query_terms_for_rag = list(set(query_terms_for_rag)) # Remove duplicates

        # If manual_context is provided, consider adding its keywords to the RAG query
        if manual_context and manual_context.strip():
            # Simple split; more advanced NLP could be used for keyword extraction from manual_context
            manual_context_keywords = [term for term in manual_context.lower().split() if len(term) > 2] 
            query_terms_for_rag = list(set(query_terms_for_rag + manual_context_keywords))
        
        # Phase 4: RAG Retrieval (using clinical retriever)
        print(f"Clinical Support - Phase 4: Knowledge Retrieval with query terms: {query_terms_for_rag}...")
        retrieved_docs = []
        if query_terms_for_rag: # Only query if there are terms
            retrieved_docs = retriever.retrieve_relevant_guidelines(query_terms_for_rag, top_k=5) # Use more docs for clinical
        print(f"Clinical Support - Phase 4 Complete. Retrieved {len(retrieved_docs)} documents.")

        # TODO: Fetch relevant patient_historical_document_texts for the *actual* patient_id.
        # This requires patient_id to be part of the request and database integration.
        # For now, we'll pass an empty list as a placeholder.
        patient_historical_document_texts_placeholder = [] 
        # Example of what it might look like later:
        # patient_id_from_request = "some_patient_id_passed_in_request_body_or_path"
        # patient_historical_document_texts = db_get_patient_document_texts(patient_id_from_request, limit=3)

        # Clinical Phase 5: Clinical Support Details Generation
        print("Clinical Support - Clinical Phase 5: Support Details Generation...")
        support_details = generate_clinical_support_details( # From clinical_support_generation.py
            extracted_clinical_info=extracted_info, 
            retrieved_knowledge_entries=retrieved_docs,
            manual_context_supplement=manual_context,
            patient_historical_document_texts=patient_historical_document_texts_placeholder # Pass placeholder
        )
        
        if isinstance(support_details, dict) and "error" in support_details:
            raise HTTPException(status_code=500, detail=f"Clinical Support: Failed to generate support details: {support_details.get('error')}")
        print("Clinical Support - Clinical Phase 5 Complete.")

        return {
            "mode": "clinical_support",
            "transcript": transcript,
            "extracted_clinical_info": extracted_info,
            "manual_context_provided": manual_context,
            "retrieved_documents_summary": [
                {"source_type": d.get("source_type"), "source_name": d.get("source_document_name"),
                 "retrieved_content_hint": d.get("disease_info", {}).get("disease") or d.get("case") or "Guideline Entry",
                 "score": d.get("retrieval_score (distance)")} for d in retrieved_docs
            ],
            "clinical_support_details": support_details
        }
    except FileNotFoundError as e: raise HTTPException(status_code=404, detail=f"File processing error: {e}")
    except ValueError as e: raise HTTPException(status_code=400, detail=str(e)) # For things like API key issues
    except HTTPException: raise # Re-raise FastAPI's own HTTP exceptions
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error in clinical support: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception as e_rem: print(f"Error removing temp file {file_path}: {e_rem}")
       
# --- Patient Document Upload Endpoint ---         
@app.post("/patients/{patient_uuid}/upload_document/")
async def upload_patient_document(
    patient_uuid: str, 
    background_tasks: BackgroundTasks, # Use BackgroundTasks for non-blocking operations
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    db_patient = crud.get_patient_by_uuid(db, patient_uuid=patient_uuid)
    if not db_patient:
        raise HTTPException(status_code=404, detail=f"Patient with UUID {patient_uuid} not found.")

    original_filename = file.filename
    safe_filename_base = "".join(c if c.isalnum() or c in ['.', '_'] else '_' for c in original_filename)
    doc_db_uuid_str = str(uuid.uuid4())
    
    # Create a patient-specific subdirectory if it doesn't exist
    patient_specific_docs_dir = os.path.join(UPLOADED_PATIENT_DOCS_DIR, db_patient.patient_uuid)
    os.makedirs(patient_specific_docs_dir, exist_ok=True)
    
    # Filename for storage on disk might include its own UUID or just be the safe name within patient folder
    storage_filename_on_disk = f"{int(time.time())}_{safe_filename_base}" 
    file_path_on_server = os.path.join(patient_specific_docs_dir, storage_filename_on_disk)

    try:
        with open(file_path_on_server, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Create PatientDocument record in DB
        db_document = crud.create_patient_document(
            db=db, 
            patient_id=db_patient.id, 
            document_uuid=doc_db_uuid_str, # Pass the generated UUID for the document record
            original_filename=original_filename,
            storage_path=file_path_on_server, # Store the actual disk path (or S3 key later)
            file_type=file.content_type
        )
        db.commit() # Commit the new document record
        
        print(f"Document for patient {db_patient.patient_uuid} saved to {file_path_on_server} (DB Doc UUID: {db_document.document_uuid})")

        # Schedule background processing
        background_tasks.add_task(
            process_uploaded_document_task, # From aidcare_pipeline.document_processing
            patient_uuid, 
            file_path_on_server, 
            original_filename, 
            file.content_type
        )
        return {
            "message": "File uploaded successfully and is queued for processing.",
            "patient_id": patient_uuid, 
            "filename_on_server": file_path_on_server, # The name it's saved as on server
            "original_filename": original_filename, 
            "content_type": file.content_type
        }
    except Exception as e:
        # Attempt to clean up partially saved file if error occurs during save
        if os.path.exists(file_path_on_server):
            try: os.remove(file_path_on_server)
            except Exception as e_del: print(f"Error cleaning up file {file_path_on_server} after upload error: {e_del}")
        
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload or queue file: {str(e)}")
    finally:
        await file.close()
                        
@app.get("/")
async def read_root():
    return {"message": "Welcome to AidCare API. Use /docs for API documentation and health check."}

@app.get("/health")
async def health_check():
    chw_ret_status = "Not initialized"
    clin_ret_status = "Not initialized"
    if "chw_retriever" in app_state and app_state["chw_retriever"] and app_state["chw_retriever"].index.ntotal > 0:
        chw_ret_status = f"Initialized ({app_state['chw_retriever'].index.ntotal} vectors)"
    if "clinical_retriever" in app_state and app_state["clinical_retriever"] and app_state["clinical_retriever"].index.ntotal > 0:
        clin_ret_status = f"Initialized ({app_state['clinical_retriever'].index.ntotal} vectors)"

    # Get rate limit stats
    rate_limit_stats = get_rate_limit_stats("global")

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "whisper_model": "Loaded via transcription.py on first call or startup",
            "chw_retriever": chw_ret_status,
            "clinical_retriever": clin_ret_status,
            "gemini_api_connectivity": "Dependent_on_key_and_network"
        },
        "rate_limiting": rate_limit_stats
    }

@app.post("/admin/clear_cache")
async def admin_clear_cache():
    """Admin endpoint to clear Gemini response cache"""
    cleared = clear_cache()
    return {"message": f"Cache cleared successfully", "entries_cleared": cleared}

@app.get("/admin/stats")
async def admin_stats():
    """Admin endpoint to view rate limiting and cache statistics"""
    return {
        "rate_limit_stats": get_rate_limit_stats("global"),
        "timestamp": time.time()
    }


# ===========================================================================
# NAIJA MULTILINGUAL ENDPOINTS
# UNDP Nigeria IC × Timbuktu Initiative — International Mother Language Day
# ===========================================================================

@app.post("/naija/continue_conversation/")
async def naija_continue_conversation(conversation_input: NaijaConversationInput):
    """
    Multi-turn conversation endpoint for Nigerian local languages.
    Supports: English, Hausa, Yorùbá, Igbo, Nigerian Pidgin.
    """
    if not conversation_input.latest_message or not conversation_input.latest_message.strip():
        raise HTTPException(status_code=400, detail="Latest message cannot be empty.")

    try:
        result = generate_multilingual_response(
            conversation_history=conversation_input.conversation_history,
            latest_message=conversation_input.latest_message,
            language=conversation_input.language,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Multilingual conversation error: {str(e)}")


@app.post("/naija/process_text/")
async def naija_process_text(
    transcript_input: NaijaTextInput,
    retriever: GuidelineRetriever = Depends(get_chw_retriever_dependency),
):
    """
    Full triage pipeline for multilingual text input.
    Symptoms extracted in English (for FAISS), recommendation generated in target language.
    """
    transcript = transcript_input.transcript_text
    language = transcript_input.language

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript text cannot be empty.")

    try:
        # Symptom extraction — Gemini handles multilingual input, always returns English JSON
        print(f"Naija Text Mode [{language}] - Symptom Extraction...")
        symptoms = extract_symptoms_with_gemini(transcript)
        if isinstance(symptoms, dict) and "error" in symptoms:
            raise HTTPException(status_code=500, detail=f"Symptom extraction failed: {symptoms.get('error')}")
        print(f"Naija Text Mode [{language}] - Extracted symptoms: {symptoms}")

        # Knowledge retrieval (FAISS — English index)
        print(f"Naija Text Mode [{language}] - Knowledge Retrieval...")
        retrieved_docs = retriever.retrieve_relevant_guidelines(symptoms, top_k=3)
        print(f"Naija Text Mode [{language}] - Retrieved {len(retrieved_docs)} guideline docs.")

        # Recommendation generation — output in target language
        print(f"Naija Text Mode [{language}] - Generating recommendation in {language}...")
        recommendation = generate_triage_recommendation(
            symptoms,
            retrieved_docs,
            language=language,
        )
        if not recommendation or (isinstance(recommendation, dict) and "error" in recommendation):
            error_detail = recommendation.get("error") if isinstance(recommendation, dict) else "Unknown error"
            raise HTTPException(status_code=500, detail=f"Recommendation failed: {error_detail}")

        return {
            "mode": f"naija_triage_{language}",
            "language": language,
            "input_transcript": transcript,
            "extracted_symptoms": symptoms,
            "triage_recommendation": recommendation,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Naija triage error: {str(e)}")


@app.post("/naija/process_audio/")
async def naija_process_audio(
    audio_file: UploadFile = File(...),
    language: str = Form("en"),
    retriever: GuidelineRetriever = Depends(get_chw_retriever_dependency),
):
    """
    Audio triage pipeline for Nigerian local languages.
    Whisper is given a language hint for better accuracy.
    """
    unique_suffix = f"{int(time.time() * 1000)}_naija_{audio_file.filename}"
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_suffix)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        print(f"Naija Audio Mode [{language}] - Transcribing with language hint...")
        transcript = transcribe_audio_local(file_path, language=language if language != 'pcm' else None)
        if not transcript:
            raise HTTPException(status_code=500, detail="Transcription failed or returned empty.")
        print(f"Naija Audio Mode [{language}] - Transcript: {transcript[:100]}...")

        # Delegate to the text pipeline
        text_input = NaijaTextInput(transcript_text=transcript, language=language)
        return await naija_process_text(transcript_input=text_input, retriever=retriever)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Naija audio processing error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


@app.post("/tts/generate/")
async def tts_generate(tts_request: TTSRequest):
    """
    ElevenLabs TTS proxy endpoint. Keeps the API key server-side.
    Returns raw audio/mpeg binary.
    """
    if not os.environ.get("ELEVENLABS_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="TTS service is not configured. Please set ELEVENLABS_API_KEY."
        )

    if not tts_request.text or not tts_request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        # Use provided voice_id or look up by language
        effective_voice_id = tts_request.voice_id if tts_request.voice_id else get_voice_id(tts_request.language)

        audio_bytes = await generate_speech(
            text=tts_request.text,
            language=tts_request.language,
            voice_id=effective_voice_id,
        )

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-store",
                "Content-Disposition": "inline",
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Return 503 so frontend can gracefully fall back (show text only)
        raise HTTPException(status_code=503, detail=f"TTS generation failed: {str(e)}")