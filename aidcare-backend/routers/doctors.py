# routers/doctors.py
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_current_user

router = APIRouter(prefix="/doctor", tags=["doctors"])


class ShiftStartRequest(BaseModel):
    ward_uuid: str | None = None


class ShiftEndRequest(BaseModel):
    shift_uuid: str


def _to_iso(dt):
    return dt.isoformat() if dt else None


def _serialize_doctor(doctor: models.Doctor) -> dict:
    return {
        "doctor_id": doctor.doctor_uuid,
        "email": doctor.email,
        "name": doctor.full_name,
        "specialty": doctor.specialty or "",
        "role": doctor.role,
        "hospital_id": doctor.hospital.hospital_uuid if doctor.hospital else None,
        "hospital_name": doctor.hospital.name if doctor.hospital else None,
        "ward_id": doctor.ward_rel.ward_uuid if doctor.ward_rel else None,
        "ward_name": doctor.ward_rel.name if doctor.ward_rel else None,
    }


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
        "volume": volume,
        "complexity": complexity,
        "duration": duration,
        "consecutive": consecutive,
    }


@router.get("/list/")
def list_doctors(
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    doctors = db.query(models.Doctor).filter(models.Doctor.is_active == True).all()
    return {"doctors": [_serialize_doctor(d) for d in doctors]}


@router.get("/profile/{doctor_uuid}")
def get_doctor_profile(
    doctor_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_uuid == doctor_uuid).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return _serialize_doctor(doctor)


@router.post("/shifts/start/")
def start_shift(
    payload: ShiftStartRequest,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    active = (
        db.query(models.Shift)
        .filter(models.Shift.doctor_id == current_user.id, models.Shift.is_active == True)
        .first()
    )
    if active:
        active.is_active = False
        active.shift_end = datetime.now(timezone.utc)
        db.commit()

    ward_id = current_user.ward_id
    if payload.ward_uuid:
        ward = db.query(models.Ward).filter(models.Ward.ward_uuid == payload.ward_uuid).first()
        if ward:
            ward_id = ward.id

    shift = models.Shift(
        shift_uuid=str(uuid.uuid4()),
        doctor_id=current_user.id,
        ward_id=ward_id,
        is_active=True,
        handover_generated=False,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return {
        "shift_id": shift.shift_uuid,
        "started_at": _to_iso(shift.shift_start),
        "ward_id": shift.ward_rel.ward_uuid if shift.ward_rel else None,
    }


@router.post("/shifts/end/")
def end_shift(
    payload: ShiftEndRequest,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    shift = db.query(models.Shift).filter(models.Shift.shift_uuid == payload.shift_uuid).first()
    if not shift or shift.doctor_id != current_user.id:
        raise HTTPException(status_code=404, detail="Shift not found")

    shift.is_active = False
    shift.shift_end = datetime.now(timezone.utc)
    db.commit()
    db.refresh(shift)

    consultations = (
        db.query(models.Consultation)
        .filter(models.Consultation.shift_id == shift.id)
        .all()
    )
    avg_complexity = (
        sum((c.complexity_score or 1) for c in consultations) / len(consultations)
        if consultations
        else 1.0
    )
    shift_start = shift.shift_start or datetime.now(timezone.utc)
    shift_end = shift.shift_end or datetime.now(timezone.utc)
    hours_active = max(0.0, (shift_end - shift_start).total_seconds() / 3600.0)
    cls, status, breakdown = _compute_cls(len(consultations), hours_active, avg_complexity)

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
        patients_seen=len(consultations),
        hours_active=hours_active,
        avg_complexity=avg_complexity,
    )
    db.add(burnout)

    snapshot = models.FatigueSnapshot(
        doctor_id=current_user.id,
        ward_id=shift.ward_id,
        cognitive_load_score=cls,
        patients_seen=len(consultations),
        hours_active=hours_active,
    )
    db.add(snapshot)
    db.commit()

    return {"ended_at": _to_iso(shift.shift_end), "final_cls": cls, "status": status}


@router.get("/shifts/active")
def get_active_shift(
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    shift = (
        db.query(models.Shift)
        .filter(models.Shift.doctor_id == current_user.id, models.Shift.is_active == True)
        .first()
    )
    if not shift:
        return {"shift": None}
    return {
        "shift": {
            "shift_id": shift.shift_uuid,
            "started_at": _to_iso(shift.shift_start),
            "ward_id": shift.ward_rel.ward_uuid if shift.ward_rel else None,
            "ward_name": shift.ward_rel.name if shift.ward_rel else None,
        }
    }
