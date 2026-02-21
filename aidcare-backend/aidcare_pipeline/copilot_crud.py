# aidcare_pipeline/copilot_crud.py
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from . import copilot_models as models


# ---------------------------------------------------------------------------
# Doctor CRUD
# ---------------------------------------------------------------------------

def create_doctor(
    db: Session,
    doctor_uuid: str,
    full_name: str,
    specialty: str,
    ward: str,
    hospital: str = "",
    role: str = "doctor",
) -> models.Doctor:
    db_doctor = models.Doctor(
        doctor_uuid=doctor_uuid,
        full_name=full_name,
        specialty=specialty,
        ward=ward,
        hospital=hospital,
        role=role,
        is_active=True,
    )
    db.add(db_doctor)
    db.commit()
    db.refresh(db_doctor)
    return db_doctor


def get_doctor_by_uuid(db: Session, doctor_uuid: str) -> models.Doctor | None:
    return (
        db.query(models.Doctor)
        .filter(models.Doctor.doctor_uuid == doctor_uuid)
        .first()
    )


def get_all_doctors(db: Session) -> list[models.Doctor]:
    return db.query(models.Doctor).filter(models.Doctor.is_active == True).all()


# ---------------------------------------------------------------------------
# Shift CRUD
# ---------------------------------------------------------------------------

def start_shift(
    db: Session,
    shift_uuid: str,
    doctor_id_int: int,
    ward: str,
) -> models.Shift:
    # Close any previously active shift for this doctor (safety guard)
    active = (
        db.query(models.Shift)
        .filter(
            models.Shift.doctor_id == doctor_id_int,
            models.Shift.is_active == True,
        )
        .first()
    )
    if active:
        active.is_active = False
        active.shift_end = datetime.now(timezone.utc)
        db.commit()

    db_shift = models.Shift(
        shift_uuid=shift_uuid,
        doctor_id=doctor_id_int,
        ward=ward,
        is_active=True,
        handover_generated=False,
    )
    db.add(db_shift)
    db.commit()
    db.refresh(db_shift)
    return db_shift


def end_shift(db: Session, shift_uuid: str) -> models.Shift | None:
    db_shift = (
        db.query(models.Shift)
        .filter(models.Shift.shift_uuid == shift_uuid)
        .first()
    )
    if db_shift:
        db_shift.is_active = False
        db_shift.shift_end = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_shift)
    return db_shift


def get_active_shift(db: Session, doctor_id_int: int) -> models.Shift | None:
    return (
        db.query(models.Shift)
        .filter(
            models.Shift.doctor_id == doctor_id_int,
            models.Shift.is_active == True,
        )
        .first()
    )


def get_shift_by_uuid(db: Session, shift_uuid: str) -> models.Shift | None:
    return (
        db.query(models.Shift)
        .filter(models.Shift.shift_uuid == shift_uuid)
        .first()
    )


# ---------------------------------------------------------------------------
# Consultation CRUD
# ---------------------------------------------------------------------------

def create_consultation(
    db: Session,
    consultation_uuid: str,
    doctor_id_int: int,
    shift_id_int: int,
    patient_ref: str,
    transcript_text: str,
    soap_note_dict: dict,
    patient_summary: str,
    complexity_score: int,
    flags: list,
    language: str,
) -> models.Consultation:
    soap = soap_note_dict.get("soap_note", {})
    db_consultation = models.Consultation(
        consultation_uuid=consultation_uuid,
        doctor_id=doctor_id_int,
        shift_id=shift_id_int,
        patient_ref=patient_ref,
        transcript_text=transcript_text,
        soap_subjective=soap.get("subjective", ""),
        soap_objective=soap.get("objective", ""),
        soap_assessment=soap.get("assessment", ""),
        soap_plan=soap.get("plan", ""),
        patient_summary=patient_summary,
        complexity_score=complexity_score,
        flags=flags,
        language=language,
    )
    db.add(db_consultation)
    db.commit()
    db.refresh(db_consultation)
    return db_consultation


def get_shift_consultations(db: Session, shift_id_int: int) -> list[models.Consultation]:
    return (
        db.query(models.Consultation)
        .filter(models.Consultation.shift_id == shift_id_int)
        .order_by(models.Consultation.created_at.asc())
        .all()
    )


def get_all_today_consultations_for_doctor(
    db: Session, doctor_id_int: int
) -> list[models.Consultation]:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(models.Consultation)
        .filter(
            models.Consultation.doctor_id == doctor_id_int,
            models.Consultation.created_at >= today_start,
        )
        .order_by(models.Consultation.created_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# BurnoutScore CRUD
# ---------------------------------------------------------------------------

def save_burnout_score(
    db: Session,
    score_uuid: str,
    doctor_id_int: int,
    shift_id_int: int | None,
    cls: int,
    status: str,
    breakdown_dict: dict,
    patients_seen: int,
    hours_active: float,
    avg_complexity: float,
) -> models.BurnoutScore:
    db_score = models.BurnoutScore(
        score_uuid=score_uuid,
        doctor_id=doctor_id_int,
        shift_id=shift_id_int,
        cognitive_load_score=cls,
        status=status,
        volume_score=breakdown_dict.get("volume", 0),
        complexity_score_component=breakdown_dict.get("complexity", 0),
        duration_score=breakdown_dict.get("duration", 0),
        consecutive_shift_score=breakdown_dict.get("consecutive", 0),
        patients_seen=patients_seen,
        hours_active=hours_active,
        avg_complexity=avg_complexity,
    )
    db.add(db_score)
    db.commit()
    db.refresh(db_score)
    return db_score


def get_latest_burnout_score(db: Session, doctor_id_int: int) -> models.BurnoutScore | None:
    return (
        db.query(models.BurnoutScore)
        .filter(models.BurnoutScore.doctor_id == doctor_id_int)
        .order_by(models.BurnoutScore.recorded_at.desc())
        .first()
    )


def get_burnout_history(
    db: Session, doctor_id_int: int, days: int = 7
) -> list[models.BurnoutScore]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return (
        db.query(models.BurnoutScore)
        .filter(
            models.BurnoutScore.doctor_id == doctor_id_int,
            models.BurnoutScore.recorded_at >= cutoff,
        )
        .order_by(models.BurnoutScore.recorded_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# HandoverReport CRUD
# ---------------------------------------------------------------------------

def save_handover_report(
    db: Session,
    report_uuid: str,
    doctor_id_int: int,
    shift_id_int: int,
    report_json: dict,
    plain_text: str,
) -> models.HandoverReport:
    db_report = models.HandoverReport(
        report_uuid=report_uuid,
        doctor_id=doctor_id_int,
        shift_id=shift_id_int,
        report_json=report_json,
        plain_text=plain_text,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    # Mark shift as handover_generated
    shift = db.query(models.Shift).filter(models.Shift.id == shift_id_int).first()
    if shift:
        shift.handover_generated = True
        db.commit()

    return db_report


# ---------------------------------------------------------------------------
# Admin / Multi-doctor queries
# ---------------------------------------------------------------------------

def get_all_active_doctors_with_burnout(
    db: Session,
) -> list[tuple[models.Doctor, models.BurnoutScore | None]]:
    """
    Returns a list of (Doctor, latest BurnoutScore | None) tuples for all
    active doctors.
    """
    doctors = get_all_doctors(db)
    result = []
    for doctor in doctors:
        latest_score = get_latest_burnout_score(db, doctor.id)
        result.append((doctor, latest_score))
    return result
