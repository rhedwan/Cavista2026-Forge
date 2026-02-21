# routers/handover.py
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_current_user

router = APIRouter(prefix="/doctor/handover", tags=["handover"])


class HandoverRequest(BaseModel):
    shift_uuid: str
    ward_uuid: str | None = None
    handover_notes: str = ""


def _to_iso(dt):
    return dt.isoformat() if dt else None


@router.post("/")
def generate_handover(
    payload: HandoverRequest,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    shift = db.query(models.Shift).filter(models.Shift.shift_uuid == payload.shift_uuid).first()
    if not shift or shift.doctor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Shift not found")

    ward_id = shift.ward_id
    if payload.ward_uuid:
        ward = db.query(models.Ward).filter(models.Ward.ward_uuid == payload.ward_uuid).first()
        if ward:
            ward_id = ward.id

    if ward_id:
        consultations = (
            db.query(models.Consultation)
            .join(models.Shift, models.Consultation.shift_id == models.Shift.id)
            .filter(models.Shift.ward_id == ward_id, models.Shift.is_active == False)
            .order_by(models.Consultation.created_at.desc())
            .limit(100)
            .all()
        )
        shift_consultations = (
            db.query(models.Consultation)
            .filter(models.Consultation.shift_id == shift.id)
            .all()
        )
        consultations = list({c.id: c for c in list(consultations) + list(shift_consultations)}.values())
    else:
        consultations = (
            db.query(models.Consultation)
            .filter(models.Consultation.shift_id == shift.id)
            .order_by(models.Consultation.created_at.asc())
            .all()
        )

    critical = []
    stable = []
    discharged = []

    seen_patients = set()
    for c in consultations:
        patient_key = c.patient_id or c.patient_ref or c.consultation_uuid
        if patient_key in seen_patients:
            continue
        seen_patients.add(patient_key)

        summary = c.patient_summary or c.transcript_text or "No summary available"
        entry = {
            "patient_ref": c.patient_ref or "Unknown",
            "patient_id": c.patient.patient_uuid if c.patient else None,
            "summary": summary[:300],
            "soap_assessment": c.soap_assessment or "",
            "flags": c.flags or [],
            "medication_changes": c.medication_changes or [],
            "complexity_score": c.complexity_score or 1,
            "doctor_name": c.doctor.full_name if c.doctor else None,
            "timestamp": _to_iso(c.created_at),
        }

        if c.patient and c.patient.status == "discharged":
            discharged.append(entry)
        elif (c.complexity_score or 1) >= 4 or (c.flags and len(c.flags) > 0):
            entry["action_required"] = "Review urgently"
            critical.append(entry)
        else:
            stable.append(entry)

    avg_complexity = (
        sum((c.complexity_score or 1) for c in consultations) / len(consultations)
        if consultations
        else 0.0
    )

    ward_obj = db.query(models.Ward).filter(models.Ward.id == ward_id).first() if ward_id else None

    report_payload = {
        "handover_id": str(uuid.uuid4()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "doctor_name": current_user.full_name,
        "ward_name": ward_obj.name if ward_obj else None,
        "shift_summary": {
            "start": _to_iso(shift.shift_start),
            "end": _to_iso(shift.shift_end),
            "patients_seen": len(seen_patients),
            "avg_complexity": round(avg_complexity, 2),
        },
        "critical_patients": critical,
        "stable_patients": stable,
        "discharged_patients": discharged,
        "handover_notes": payload.handover_notes,
    }
    report_payload["plain_text_report"] = (
        f"Handover for {current_user.full_name}. "
        f"Ward: {ward_obj.name if ward_obj else 'N/A'}. "
        f"Patients: {len(seen_patients)}. "
        f"Critical: {len(critical)}. Stable: {len(stable)}. Discharged: {len(discharged)}."
    )

    db_report = models.HandoverReport(
        report_uuid=report_payload["handover_id"],
        doctor_id=current_user.id,
        shift_id=shift.id,
        ward_id=ward_id,
        report_json=report_payload,
        plain_text=report_payload["plain_text_report"],
    )
    db.add(db_report)

    shift.handover_generated = True
    db.commit()

    return report_payload


@router.get("/consultations")
def get_shift_consultations(
    shift_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    shift = db.query(models.Shift).filter(models.Shift.shift_uuid == shift_uuid).first()
    if not shift or shift.doctor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Shift not found")

    consultations = (
        db.query(models.Consultation)
        .filter(models.Consultation.shift_id == shift.id)
        .order_by(models.Consultation.created_at.asc())
        .all()
    )
    return {
        "consultations_count": len(consultations),
        "consultations": [
            {
                "consultation_id": c.consultation_uuid,
                "patient_ref": c.patient_ref or "",
                "patient_id": c.patient.patient_uuid if c.patient else None,
                "timestamp": _to_iso(c.created_at),
                "transcript": c.transcript_text or "",
                "pidgin_detected": c.pidgin_detected,
                "soap_note": {
                    "subjective": c.soap_subjective or "",
                    "objective": c.soap_objective or "",
                    "assessment": c.soap_assessment or "",
                    "plan": c.soap_plan or "",
                },
                "patient_summary": c.patient_summary or "",
                "complexity_score": c.complexity_score or 1,
                "flags": c.flags or [],
                "medication_changes": c.medication_changes or [],
                "language": c.language or "en",
            }
            for c in consultations
        ],
    }
