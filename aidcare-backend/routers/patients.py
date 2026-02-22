# routers/patients.py
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_current_user

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientCreate(BaseModel):
    full_name: str
    age: int | None = None
    gender: str | None = None
    ward_uuid: str | None = None
    bed_number: str | None = None
    primary_diagnosis: str | None = None
    status: str = "stable"
    vitals: dict | None = None
    allergies: list[str] | None = None
    active_medications: list[dict] | None = None
    medical_history: list[dict] | None = None
    triage_result: dict | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    status: str | None = None
    bed_number: str | None = None
    primary_diagnosis: str | None = None
    vitals: dict | None = None
    allergies: list[str] | None = None
    active_medications: list[dict] | None = None
    medical_history: list[dict] | None = None


class ActionItemCreate(BaseModel):
    description: str
    priority: str = "normal"
    due_time: datetime | None = None


def _to_iso(dt):
    return dt.isoformat() if dt else None


def _serialize_patient(p: models.Patient) -> dict:
    return {
        "patient_id": p.patient_uuid,
        "full_name": p.full_name,
        "age": p.age,
        "gender": p.gender,
        "bed_number": p.bed_number,
        "status": p.status,
        "primary_diagnosis": p.primary_diagnosis,
        "admission_date": _to_iso(p.admission_date),
        "discharge_date": _to_iso(p.discharge_date),
        "vitals": p.vitals,
        "allergies": p.allergies,
        "active_medications": p.active_medications,
        "medical_history": p.medical_history,
        "triage_result": p.triage_result,
        "ward_id": p.ward.ward_uuid if p.ward else None,
        "ward_name": p.ward.name if p.ward else None,
        "attending_doctor_id": p.attending_doctor.doctor_uuid if p.attending_doctor else None,
        "attending_doctor_name": p.attending_doctor.full_name if p.attending_doctor else None,
    }


def _serialize_action_item(item: models.ActionItem) -> dict:
    return {
        "item_id": item.item_uuid,
        "description": item.description,
        "priority": item.priority,
        "due_time": _to_iso(item.due_time),
        "completed": item.completed,
        "completed_at": _to_iso(item.completed_at),
        "created_at": _to_iso(item.created_at),
        "created_by": item.created_by.full_name if item.created_by else None,
    }


@router.post("/")
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    ward_id = current_user.ward_id
    if payload.ward_uuid:
        ward = db.query(models.Ward).filter(models.Ward.ward_uuid == payload.ward_uuid).first()
        if ward:
            ward_id = ward.id

    patient = models.Patient(
        patient_uuid=str(uuid.uuid4()),
        full_name=payload.full_name,
        age=payload.age,
        gender=payload.gender,
        ward_id=ward_id,
        attending_doctor_id=current_user.id,
        bed_number=payload.bed_number,
        status=payload.status,
        primary_diagnosis=payload.primary_diagnosis,
        admission_date=datetime.now(timezone.utc),
        vitals=payload.vitals,
        allergies=payload.allergies,
        active_medications=payload.active_medications,
        medical_history=payload.medical_history,
        triage_result=payload.triage_result,
    )
    if payload.triage_result and payload.triage_result.get("risk_level") == "high":
        patient.status = "critical"
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return _serialize_patient(patient)


@router.get("/")
def list_patients(
    ward_uuid: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    query = db.query(models.Patient)

    if ward_uuid:
        # Specific ward requested — filter to that ward
        ward = db.query(models.Ward).filter(models.Ward.ward_uuid == ward_uuid).first()
        if ward:
            query = query.filter(models.Patient.ward_id == ward.id)
    elif current_user.role in ("super_admin",):
        # Super admins see all patients across all organizations
        pass
    elif current_user.hospital_id:
        # All health workers under a hospital see all patients in that hospital's wards
        hospital_ward_ids = [
            w.id for w in db.query(models.Ward)
            .filter(models.Ward.hospital_id == current_user.hospital_id)
            .all()
        ]
        if hospital_ward_ids:
            query = query.filter(models.Patient.ward_id.in_(hospital_ward_ids))
        else:
            query = query.filter(models.Patient.ward_id == None)  # no wards → no patients
    elif current_user.ward_id:
        # Fallback: if no hospital assigned, show only their ward
        query = query.filter(models.Patient.ward_id == current_user.ward_id)

    if status_filter:
        query = query.filter(models.Patient.status == status_filter)

    patients = query.order_by(
        models.Patient.status.asc(),  # critical first
        models.Patient.updated_at.desc(),
    ).all()

    grouped = {"critical": [], "stable": [], "discharged": []}
    for p in patients:
        serialized = _serialize_patient(p)
        bucket = p.status if p.status in grouped else "stable"
        grouped[bucket].append(serialized)

    return {
        "total": len(patients),
        "patients": grouped,
    }


@router.get("/{patient_uuid}")
def get_patient(
    patient_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    patient = db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    consultations = (
        db.query(models.Consultation)
        .filter(models.Consultation.patient_id == patient.id)
        .order_by(models.Consultation.created_at.desc())
        .limit(10)
        .all()
    )

    action_items = (
        db.query(models.ActionItem)
        .filter(models.ActionItem.patient_id == patient.id, models.ActionItem.completed == False)
        .order_by(models.ActionItem.priority.asc(), models.ActionItem.created_at.desc())
        .all()
    )

    medication_changes = []
    for c in consultations:
        if c.medication_changes:
            for change in c.medication_changes:
                medication_changes.append({
                    **change,
                    "consultation_time": _to_iso(c.created_at),
                    "doctor_name": c.doctor.full_name if c.doctor else None,
                })

    return {
        **_serialize_patient(patient),
        "consultations": [
            {
                "consultation_id": c.consultation_uuid,
                "timestamp": _to_iso(c.created_at),
                "soap_note": {
                    "subjective": c.soap_subjective or "",
                    "objective": c.soap_objective or "",
                    "assessment": c.soap_assessment or "",
                    "plan": c.soap_plan or "",
                },
                "patient_summary": c.patient_summary or "",
                "complexity_score": c.complexity_score or 1,
                "flags": c.flags or [],
                "doctor_name": c.doctor.full_name if c.doctor else None,
            }
            for c in consultations
        ],
        "action_items": [_serialize_action_item(item) for item in action_items],
        "medication_changes": medication_changes[:20],
    }


@router.patch("/{patient_uuid}")
def update_patient(
    patient_uuid: str,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    patient = db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(patient, field, value)
    if payload.status == "discharged" and not patient.discharge_date:
        patient.discharge_date = datetime.now(timezone.utc)

    db.commit()
    db.refresh(patient)
    return _serialize_patient(patient)


# --- Action Items ---

@router.post("/{patient_uuid}/action-items")
def create_action_item(
    patient_uuid: str,
    payload: ActionItemCreate,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    patient = db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    item = models.ActionItem(
        item_uuid=str(uuid.uuid4()),
        patient_id=patient.id,
        created_by_doctor_id=current_user.id,
        description=payload.description,
        priority=payload.priority,
        due_time=payload.due_time,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_action_item(item)


@router.patch("/action-items/{item_uuid}/complete")
def complete_action_item(
    item_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    item = db.query(models.ActionItem).filter(models.ActionItem.item_uuid == item_uuid).first()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    item.completed = True
    item.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _serialize_action_item(item)


# --- AI-Summarized Patient History ---

@router.get("/{patient_uuid}/ai-summary")
def get_patient_ai_summary(
    patient_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    patient = db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    consultations = (
        db.query(models.Consultation)
        .filter(models.Consultation.patient_id == patient.id)
        .order_by(models.Consultation.created_at.desc())
        .limit(20)
        .all()
    )

    if not consultations:
        return {
            "chronic_conditions": [],
            "flagged_patterns": [],
            "summary": "No consultation history available for AI analysis.",
        }

    notes_text = "\n\n".join(
        f"Date: {_to_iso(c.created_at)}\n"
        f"Subjective: {c.soap_subjective or ''}\n"
        f"Objective: {c.soap_objective or ''}\n"
        f"Assessment: {c.soap_assessment or ''}\n"
        f"Plan: {c.soap_plan or ''}\n"
        f"Flags: {', '.join(c.flags) if c.flags else 'None'}"
        for c in consultations
    )

    patient_context = (
        f"Patient: {patient.full_name}, {patient.age}y {patient.gender}\n"
        f"Primary diagnosis: {patient.primary_diagnosis or 'N/A'}\n"
        f"Allergies: {', '.join(patient.allergies) if patient.allergies else 'None'}\n"
        f"Current medications: {', '.join(m.get('name', '') for m in (patient.active_medications or []))}\n"
    )

    try:
        import google.generativeai as genai
        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set")

        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        prompt = (
            f"{patient_context}\n"
            f"Consultation history (most recent first):\n{notes_text}\n\n"
            "Analyze this patient's consultation history and return a JSON object with:\n"
            '1. "chronic_conditions": array of objects with "condition" and "details" (string summary)\n'
            '2. "flagged_patterns": array of strings describing concerning trends or patterns\n'
            '3. "summary": a 2-3 sentence overall summary of the patient\'s clinical trajectory\n'
            "Return ONLY valid JSON, no markdown."
        )

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=800),
        )

        import json
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        return result

    except Exception as e:
        return {
            "chronic_conditions": [
                {"condition": patient.primary_diagnosis or "See records", "details": "Review full consultation history."}
            ],
            "flagged_patterns": [f.strip() for f in (consultations[0].flags or [])[:3]] if consultations else [],
            "summary": consultations[0].patient_summary if consultations else "Unable to generate AI summary.",
            "error": str(e),
        }
