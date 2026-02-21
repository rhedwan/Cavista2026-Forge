# routers/triage.py
# Multilingual triage with dual-input: patient (any language) + staff notes (English)
import os
import time
import shutil
from threading import Lock

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_optional_user
from aidcare_pipeline.transcription import transcribe_audio_local
from aidcare_pipeline.symptom_extraction import extract_symptoms_with_gemini
from aidcare_pipeline.recommendation import generate_triage_recommendation
from aidcare_pipeline.multilingual import generate_multilingual_response, URGENT_KEYWORDS
from aidcare_pipeline.tts_service import generate_speech, get_voice_id
from aidcare_pipeline.rag_retrieval import get_chw_retriever, GuidelineRetriever

router = APIRouter(prefix="/triage", tags=["triage"])

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

_retriever_lock = Lock()
_retriever_cache: dict = {}


def _get_chw_retriever() -> GuidelineRetriever:
    if "chw" in _retriever_cache:
        return _retriever_cache["chw"]
    with _retriever_lock:
        if "chw" in _retriever_cache:
            return _retriever_cache["chw"]
        retriever = get_chw_retriever()
        _retriever_cache["chw"] = retriever
        return retriever


def _get_retriever_or_503() -> GuidelineRetriever:
    try:
        r = _get_chw_retriever()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Triage knowledge base not available: {e}")
    if r.index.ntotal == 0:
        raise HTTPException(status_code=503, detail="Triage knowledge base is empty.")
    return r


# --- Schemas ---

class ConversationInput(BaseModel):
    conversation_history: str
    patient_message: str
    staff_notes: str = ""
    language: str = "en"


class TriageTextInput(BaseModel):
    transcript_text: str
    staff_notes: str = ""
    language: str = "en"


class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    voice_id: str = ""


class SaveTriageRequest(BaseModel):
    triage_result: dict


# --- Conversation continue (dual-input) ---

@router.post("/conversation/continue")
async def continue_conversation(payload: ConversationInput):
    if not payload.patient_message or not payload.patient_message.strip():
        raise HTTPException(status_code=400, detail="Patient message cannot be empty.")

    try:
        augmented_history = payload.conversation_history
        if payload.staff_notes and payload.staff_notes.strip():
            augmented_history += (
                f"\n\n--- STAFF CLINICAL OBSERVATIONS (English, for AI context only) ---\n"
                f"The attending nurse/CHW has recorded: {payload.staff_notes.strip()}\n"
                f"Use these observations to inform your next question, but do NOT mention "
                f"them directly to the patient. Do NOT say 'according to the nurse' or "
                f"similar. Just use the clinical data to ask smarter follow-up questions.\n"
                f"---"
            )

        result = generate_multilingual_response(
            conversation_history=augmented_history,
            latest_message=payload.patient_message,
            language=payload.language,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Conversation error: {str(e)}")


# --- Full triage from text ---

@router.post("/process_text")
async def process_text(payload: TriageTextInput):
    transcript = payload.transcript_text
    language = payload.language

    if not transcript or not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")

    retriever = _get_retriever_or_503()

    try:
        full_text = transcript
        if payload.staff_notes and payload.staff_notes.strip():
            full_text += f"\n\nClinical observations by staff: {payload.staff_notes.strip()}"

        symptoms = extract_symptoms_with_gemini(full_text)
        if isinstance(symptoms, dict) and "error" in symptoms:
            raise HTTPException(status_code=500, detail=f"Symptom extraction failed: {symptoms.get('error')}")

        symptom_list = symptoms if isinstance(symptoms, list) else symptoms.get("symptoms", [])
        retrieved_docs = retriever.retrieve_relevant_guidelines(symptom_list, top_k=3)

        recommendation = generate_triage_recommendation(
            symptom_list, retrieved_docs, language=language,
        )
        if not recommendation or (isinstance(recommendation, dict) and "error" in recommendation):
            detail = recommendation.get("error") if isinstance(recommendation, dict) else "Unknown"
            raise HTTPException(status_code=500, detail=f"Recommendation failed: {detail}")

        urgency = recommendation.get("urgency_level", "")
        risk_level = _derive_risk_level(urgency)

        return {
            "language": language,
            "extracted_symptoms": symptom_list,
            "staff_notes": payload.staff_notes or "",
            "triage_recommendation": recommendation,
            "risk_level": risk_level,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Triage error: {str(e)}")


# --- Full triage from audio ---

@router.post("/process_audio")
async def process_audio(
    audio_file: UploadFile = File(...),
    language: str = Form("en"),
    staff_notes: str = Form(""),
):
    unique_suffix = f"{int(time.time() * 1000)}_triage_{audio_file.filename}"
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_suffix)

    try:
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(audio_file.file, buf)

        transcript = transcribe_audio_local(file_path, language=language if language != "pcm" else None)
        if not transcript:
            raise HTTPException(status_code=500, detail="Transcription failed or returned empty.")

        text_input = TriageTextInput(
            transcript_text=transcript,
            staff_notes=staff_notes,
            language=language,
        )
        result = await process_text(text_input)
        result["transcript"] = transcript
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Audio triage error: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


# --- TTS proxy ---

@router.post("/tts")
async def tts_proxy(payload: TTSRequest):
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    is_yoruba = payload.language == "yo"
    if is_yoruba and not os.environ.get("YARNGPT_API_KEY"):
        raise HTTPException(status_code=503, detail="Yoruba TTS not configured.")
    if not is_yoruba and not os.environ.get("ELEVENLABS_API_KEY"):
        raise HTTPException(status_code=503, detail="TTS service not configured.")

    try:
        voice = None if is_yoruba else (payload.voice_id or get_voice_id(payload.language))
        audio_bytes = await generate_speech(
            text=payload.text, language=payload.language, voice_id=voice,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=f"TTS failed: {str(e)}")


# --- Save triage result to patient record ---

@router.post("/save/{patient_uuid}")
def save_triage_to_patient(
    patient_uuid: str,
    payload: SaveTriageRequest,
    db: Session = Depends(get_db),
    current_user: models.Doctor | None = Depends(get_optional_user),
):
    patient = db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient.triage_result = payload.triage_result
    if payload.triage_result.get("risk_level") == "high":
        patient.status = "critical"
    db.commit()
    db.refresh(patient)
    return {"status": "saved", "patient_id": patient.patient_uuid}


# --- Helpers ---

def _derive_risk_level(urgency_level: str) -> str:
    text = (urgency_level or "").lower()
    if any(k in text for k in ["emergency", "immediate", "critical", "urgent referral"]):
        return "high"
    if any(k in text for k in ["urgent", "refer", "hospital", "observe closely"]):
        return "moderate"
    return "low"
