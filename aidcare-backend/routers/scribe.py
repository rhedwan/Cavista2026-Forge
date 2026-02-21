# routers/scribe.py
import os
import time
import uuid
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_current_user
from aidcare_pipeline.transcription import transcribe_audio_local
from aidcare_pipeline.soap_generation import generate_soap_note

router = APIRouter(prefix="/doctor/scribe", tags=["scribe"])

TEMP_AUDIO_DIR = "temp_audio"
os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

PIDGIN_MARKERS = [
    "dey", "no be", "wetin", "wahala", "abeg", "abi", "sha", "sef",
    "na", "chop", "pikin", "wey", "dem", "e don", "e dey", "jara",
    "bodi", "belle", "shey", "e no", "sotey", "go come",
    "body dey hot me", "head dey bang", "belle dey pain me",
    "i no fit", "e come be say", "na so e start", "make i",
    "how far", "wetin happen", "e never", "i dey feel",
    "commot", "enter", "dey do me", "sharp sharp", "wahala dey",
    "i never chop", "no worry", "na true", "oya", "no vex",
]

PIDGIN_PHRASES = [
    "body just dey do me", "head dey bang me", "belle dey run me",
    "i no fit sleep", "e dey pain me", "na since yesterday",
    "i never chop medicine", "body dey hot me inside night",
    "e start from", "i just dey feel", "e come be like say",
]


def _detect_pidgin(text: str) -> bool:
    lower = text.lower()
    phrase_hits = sum(1 for p in PIDGIN_PHRASES if p in lower)
    if phrase_hits >= 1:
        return True
    word_hits = sum(1 for marker in PIDGIN_MARKERS if f" {marker} " in f" {lower} ")
    return word_hits >= 2


def _compute_cls(consultations_count: int, hours_active: float, avg_complexity: float):
    volume = min(40, consultations_count * 8)
    complexity = min(30, int(round(avg_complexity * 6)))
    duration = min(20, int(round(hours_active * 2)))
    consecutive = 0
    cls = min(100, volume + complexity + duration + consecutive)
    if cls >= 70:
        status = "red"
    elif cls >= 40:
        status = "amber"
    else:
        status = "green"
    return cls, status, {
        "volume": volume, "complexity": complexity,
        "duration": duration, "consecutive": consecutive,
    }


@router.post("/")
async def doctor_scribe(
    audio_file: UploadFile = File(...),
    patient_uuid: str = Form(""),
    patient_ref: str = Form(""),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    unique_suffix = f"{int(time.time() * 1000)}_scribe_{audio_file.filename}"
    file_path = os.path.join(TEMP_AUDIO_DIR, unique_suffix)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        transcript = transcribe_audio_local(file_path, language=language if language != "pcm" else None)
        transcript = (transcript or "").strip()
        if not transcript:
            raise HTTPException(status_code=500, detail="Transcription failed or returned empty.")

        pidgin_detected = _detect_pidgin(transcript)
        soap_result = generate_soap_note(transcript=transcript, language=language)

        soap_note = soap_result.get(
            "soap_note",
            {"subjective": "", "objective": "", "assessment": "", "plan": ""},
        )
        patient_summary = soap_result.get("patient_summary", "")
        complexity_score = max(1, min(5, int(soap_result.get("complexity_score", 1))))
        flags = soap_result.get("flags", [])
        medication_changes = soap_result.get("medication_changes", [])

        patient_id = None
        if patient_uuid:
            patient = db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()
            if patient:
                patient_id = patient.id

        shift = (
            db.query(models.Shift)
            .filter(models.Shift.doctor_id == current_user.id, models.Shift.is_active == True)
            .first()
        )

        consultation = None
        burnout_data = None
        if shift:
            consultation = models.Consultation(
                consultation_uuid=str(uuid.uuid4()),
                doctor_id=current_user.id,
                shift_id=shift.id,
                patient_id=patient_id,
                patient_ref=patient_ref or patient_uuid,
                transcript=None,
                transcript_text=transcript,
                pidgin_detected=pidgin_detected,
                soap_subjective=soap_note.get("subjective", ""),
                soap_objective=soap_note.get("objective", ""),
                soap_assessment=soap_note.get("assessment", ""),
                soap_plan=soap_note.get("plan", ""),
                patient_summary=patient_summary,
                complexity_score=complexity_score,
                flags=flags,
                medication_changes=medication_changes,
                language=language,
            )
            db.add(consultation)
            db.commit()
            db.refresh(consultation)

            all_consults = (
                db.query(models.Consultation)
                .filter(models.Consultation.shift_id == shift.id)
                .all()
            )
            avg_c = (
                sum((c.complexity_score or 1) for c in all_consults) / len(all_consults)
                if all_consults
                else 1.0
            )
            shift_start = shift.shift_start or datetime.now(timezone.utc)
            hours = max(0.0, (datetime.now(timezone.utc) - shift_start).total_seconds() / 3600.0)
            cls, status, breakdown = _compute_cls(len(all_consults), hours, avg_c)

            burnout = models.BurnoutScore(
                score_uuid=str(uuid.uuid4()),
                doctor_id=current_user.id,
                shift_id=shift.id,
                cognitive_load_score=cls,
                status=status,
                volume_score=breakdown["volume"],
                complexity_score_component=breakdown["complexity"],
                duration_score=breakdown["duration"],
                consecutive_shift_score=breakdown["consecutive"],
                patients_seen=len(all_consults),
                hours_active=hours,
                avg_complexity=avg_c,
            )
            db.add(burnout)

            snapshot = models.FatigueSnapshot(
                doctor_id=current_user.id,
                ward_id=shift.ward_id,
                cognitive_load_score=cls,
                patients_seen=len(all_consults),
                hours_active=hours,
            )
            db.add(snapshot)
            db.commit()

            burnout_data = {"cls": cls, "status": status}

        return {
            "consultation_id": consultation.consultation_uuid if consultation else None,
            "patient_ref": patient_ref or patient_uuid,
            "transcript": transcript,
            "pidgin_detected": pidgin_detected,
            "soap_note": soap_note,
            "patient_summary": patient_summary,
            "complexity_score": complexity_score,
            "flags": flags,
            "medication_changes": medication_changes,
            "burnout_score": burnout_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scribe processing failed: {str(e)}")
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
