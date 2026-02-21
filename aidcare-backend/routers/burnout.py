# routers/burnout.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_current_user, require_role

router = APIRouter(tags=["burnout"])


def _to_iso(dt):
    return dt.isoformat() if dt else None


# --- Doctor-facing burnout ---

@router.get("/doctor/burnout/me")
def get_my_burnout(
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    latest = (
        db.query(models.BurnoutScore)
        .filter(models.BurnoutScore.doctor_id == current_user.id)
        .order_by(models.BurnoutScore.recorded_at.desc())
        .first()
    )
    active_shift = (
        db.query(models.Shift)
        .filter(models.Shift.doctor_id == current_user.id, models.Shift.is_active == True)
        .first()
    )
    history = (
        db.query(models.BurnoutScore)
        .filter(
            models.BurnoutScore.doctor_id == current_user.id,
            models.BurnoutScore.recorded_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
        .order_by(models.BurnoutScore.recorded_at.asc())
        .all()
    )

    return {
        "doctor_id": current_user.doctor_uuid,
        "doctor_name": current_user.full_name,
        "current_shift": (
            {
                "shift_id": active_shift.shift_uuid,
                "start": _to_iso(active_shift.shift_start),
                "patients_seen": latest.patients_seen if latest else 0,
                "hours_active": latest.hours_active if latest else 0.0,
            }
            if active_shift
            else None
        ),
        "cognitive_load_score": latest.cognitive_load_score if latest else 0,
        "status": latest.status if latest else "green",
        "score_breakdown": (
            {
                "volume": latest.volume_score,
                "complexity": latest.complexity_score_component,
                "duration": latest.duration_score,
                "consecutive": latest.consecutive_shift_score,
            }
            if latest
            else {"volume": 0, "complexity": 0, "duration": 0, "consecutive": 0}
        ),
        "history_7_days": [
            {"date": _to_iso(item.recorded_at), "cls": item.cognitive_load_score, "status": item.status}
            for item in history
        ],
        "recommendation": (
            "Take short breaks and escalate complex cases early."
            if (latest and latest.status != "green")
            else "Current load is manageable."
        ),
    }


# --- Admin dashboard ---

@router.get("/admin/dashboard/")
def admin_dashboard(
    ward_uuid: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(require_role("super_admin", "org_admin", "hospital_admin", "admin")),
):
    doctor_query = db.query(models.Doctor).filter(models.Doctor.is_active == True)

    if ward_uuid:
        ward = db.query(models.Ward).filter(models.Ward.ward_uuid == ward_uuid).first()
        if ward:
            doctor_query = doctor_query.filter(models.Doctor.ward_id == ward.id)
    elif current_user.hospital_id:
        hospital = db.query(models.Hospital).filter(models.Hospital.id == current_user.hospital_id).first()
        if hospital:
            ward_ids = [w.id for w in hospital.wards]
            if ward_ids:
                doctor_query = doctor_query.filter(models.Doctor.ward_id.in_(ward_ids))

    doctors = doctor_query.all()
    cards = []
    red_zone_alerts = []
    total_patients = 0
    cls_values = []
    red_count = amber_count = green_count = 0

    for doctor in doctors:
        latest_score = (
            db.query(models.BurnoutScore)
            .filter(models.BurnoutScore.doctor_id == doctor.id)
            .order_by(models.BurnoutScore.recorded_at.desc())
            .first()
        )
        active_shift = (
            db.query(models.Shift)
            .filter(models.Shift.doctor_id == doctor.id, models.Shift.is_active == True)
            .first()
        )

        cls = latest_score.cognitive_load_score if latest_score else 0
        status = latest_score.status if latest_score else "green"
        patients_seen = latest_score.patients_seen if latest_score else 0
        hours_active = latest_score.hours_active if latest_score else 0.0
        total_patients += patients_seen
        cls_values.append(cls)

        if status == "red":
            red_count += 1
            red_zone_alerts.append({
                "doctor_id": doctor.doctor_uuid,
                "name": doctor.full_name,
                "cls": cls,
                "message": "High cognitive load. Prioritize support and redistribution.",
            })
        elif status == "amber":
            amber_count += 1
        else:
            green_count += 1

        cards.append({
            "doctor_id": doctor.doctor_uuid,
            "name": doctor.full_name,
            "specialty": doctor.specialty or "",
            "ward_name": doctor.ward_rel.name if doctor.ward_rel else "",
            "cls": cls,
            "status": status,
            "patients_seen": patients_seen,
            "hours_active": hours_active,
            "current_task": None,
            "is_on_shift": active_shift is not None,
            "shift_duration_hours": (
                round((datetime.now(timezone.utc) - active_shift.shift_start).total_seconds() / 3600, 1)
                if active_shift and active_shift.shift_start
                else 0
            ),
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "team_stats": {
            "total_active": len(doctors),
            "red_count": red_count,
            "amber_count": amber_count,
            "green_count": green_count,
            "avg_cls": round(sum(cls_values) / len(cls_values), 2) if cls_values else 0,
            "total_patients_today": total_patients,
        },
        "doctors": cards,
        "red_zone_alerts": red_zone_alerts,
    }


@router.get("/admin/doctor/{doctor_uuid}/detail")
def admin_doctor_detail(
    doctor_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(require_role("super_admin", "org_admin", "hospital_admin", "admin")),
):
    doctor = db.query(models.Doctor).filter(models.Doctor.doctor_uuid == doctor_uuid).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    latest = (
        db.query(models.BurnoutScore)
        .filter(models.BurnoutScore.doctor_id == doctor.id)
        .order_by(models.BurnoutScore.recorded_at.desc())
        .first()
    )
    history = (
        db.query(models.BurnoutScore)
        .filter(
            models.BurnoutScore.doctor_id == doctor.id,
            models.BurnoutScore.recorded_at >= datetime.now(timezone.utc) - timedelta(days=7),
        )
        .order_by(models.BurnoutScore.recorded_at.asc())
        .all()
    )
    active_shift = (
        db.query(models.Shift)
        .filter(models.Shift.doctor_id == doctor.id, models.Shift.is_active == True)
        .first()
    )

    return {
        "doctor": {
            "doctor_id": doctor.doctor_uuid,
            "name": doctor.full_name,
            "specialty": doctor.specialty or "",
            "ward_name": doctor.ward_rel.name if doctor.ward_rel else "",
            "role": doctor.role,
        },
        "current_shift": (
            {
                "shift_id": active_shift.shift_uuid,
                "started_at": _to_iso(active_shift.shift_start),
                "ward_name": active_shift.ward_rel.name if active_shift.ward_rel else None,
                "is_active": active_shift.is_active,
            }
            if active_shift
            else None
        ),
        "latest_burnout": (
            {
                "recorded_at": _to_iso(latest.recorded_at),
                "cls": latest.cognitive_load_score,
                "status": latest.status,
                "patients_seen": latest.patients_seen,
                "hours_active": latest.hours_active,
            }
            if latest
            else None
        ),
        "burnout_history": [
            {"recorded_at": _to_iso(item.recorded_at), "cls": item.cognitive_load_score, "status": item.status}
            for item in history
        ],
        "intervention_suggestion": (
            "Recommend immediate rotation or relief. Doctor is in the red zone."
            if (latest and latest.status == "red")
            else (
                "Monitor closely. Approaching cognitive fatigue threshold."
                if (latest and latest.status == "amber")
                else "No intervention needed at this time."
            )
        ),
    }


# --- Unit/Ward-level burnout aggregation ---

@router.get("/units/{ward_uuid}/stats")
def get_ward_stats(
    ward_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    ward = db.query(models.Ward).filter(models.Ward.ward_uuid == ward_uuid).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")

    doctors = db.query(models.Doctor).filter(models.Doctor.ward_id == ward.id, models.Doctor.is_active == True).all()

    active_doctors = 0
    total_cls = 0
    total_patients = 0
    doctor_count = len(doctors)

    for doc in doctors:
        active_shift = (
            db.query(models.Shift)
            .filter(models.Shift.doctor_id == doc.id, models.Shift.is_active == True)
            .first()
        )
        if active_shift:
            active_doctors += 1

        latest = (
            db.query(models.BurnoutScore)
            .filter(models.BurnoutScore.doctor_id == doc.id)
            .order_by(models.BurnoutScore.recorded_at.desc())
            .first()
        )
        if latest:
            total_cls += latest.cognitive_load_score
            total_patients += latest.patients_seen or 0

    avg_fatigue = round(total_cls / doctor_count, 1) if doctor_count else 0
    patient_count = db.query(models.Patient).filter(
        models.Patient.ward_id == ward.id,
        models.Patient.status != "discharged",
    ).count()
    capacity_pct = round((patient_count / ward.capacity) * 100, 1) if ward.capacity else 0

    # Fatigue forecast: simple linear projection from recent snapshots
    cutoff_12h = datetime.now(timezone.utc) - timedelta(hours=12)
    snapshots = (
        db.query(models.FatigueSnapshot)
        .filter(models.FatigueSnapshot.ward_id == ward.id, models.FatigueSnapshot.recorded_at >= cutoff_12h)
        .order_by(models.FatigueSnapshot.recorded_at.asc())
        .all()
    )

    forecast_points = []
    for snap in snapshots:
        forecast_points.append({
            "time": _to_iso(snap.recorded_at),
            "cls": snap.cognitive_load_score,
        })

    # Predict when critical threshold (80) will be reached
    predicted_critical_time = None
    if len(forecast_points) >= 2:
        first = forecast_points[0]["cls"]
        last = forecast_points[-1]["cls"]
        time_span_hours = (snapshots[-1].recorded_at - snapshots[0].recorded_at).total_seconds() / 3600
        if time_span_hours > 0 and last > first:
            rate_per_hour = (last - first) / time_span_hours
            hours_to_80 = max(0, (80 - last) / rate_per_hour) if rate_per_hour > 0 else None
            if hours_to_80 is not None:
                predicted_critical_time = (datetime.now(timezone.utc) + timedelta(hours=hours_to_80)).isoformat()

    # Clerking volume (consultations per hour in current ward today)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_consults = (
        db.query(models.Consultation)
        .join(models.Shift, models.Consultation.shift_id == models.Shift.id)
        .filter(models.Shift.ward_id == ward.id, models.Consultation.created_at >= today_start)
        .count()
    )
    hours_today = max(1, (datetime.now(timezone.utc) - today_start).total_seconds() / 3600)
    clerking_volume_per_hour = round(today_consults / hours_today, 1)

    # Average complexity today
    avg_complexity_today = (
        db.query(sa_func.avg(models.Consultation.complexity_score))
        .join(models.Shift, models.Consultation.shift_id == models.Shift.id)
        .filter(models.Shift.ward_id == ward.id, models.Consultation.created_at >= today_start)
        .scalar()
    )

    return {
        "ward_id": ward.ward_uuid,
        "ward_name": ward.name,
        "hospital_name": ward.hospital.name if ward.hospital else None,
        "hospital_code": ward.hospital.code if ward.hospital else None,
        "capacity_percent": capacity_pct,
        "patient_count": patient_count,
        "ward_capacity": ward.capacity,
        "avg_fatigue_score": avg_fatigue,
        "active_doctors": active_doctors,
        "total_doctors": doctor_count,
        "predicted_critical_time": predicted_critical_time,
        "fatigue_forecast": forecast_points,
        "clerking_volume_per_hour": clerking_volume_per_hour,
        "avg_case_complexity": round(float(avg_complexity_today or 0), 1),
        "unit_status": (
            "critical" if avg_fatigue >= 70
            else "warning" if avg_fatigue >= 40
            else "optimal"
        ),
    }


# --- Resource Allocation Engine ---

@router.get("/admin/allocation")
def get_allocation_data(
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(require_role("super_admin", "org_admin", "hospital_admin", "admin")),
):
    """Cross-ward fatigue aggregation with AI transfer recommendations."""
    hospital_id = current_user.hospital_id
    if not hospital_id:
        raise HTTPException(status_code=400, detail="No hospital assigned")

    hospital = db.query(models.Hospital).filter(models.Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    wards = db.query(models.Ward).filter(models.Ward.hospital_id == hospital.id).all()

    overburdened = []
    stable = []

    for ward in wards:
        doctors = db.query(models.Doctor).filter(
            models.Doctor.ward_id == ward.id, models.Doctor.is_active == True
        ).all()
        if not doctors:
            continue

        total_cls = 0
        total_patients = 0
        doc_count = len(doctors)

        for doc in doctors:
            latest = (
                db.query(models.BurnoutScore)
                .filter(models.BurnoutScore.doctor_id == doc.id)
                .order_by(models.BurnoutScore.recorded_at.desc())
                .first()
            )
            if latest:
                total_cls += latest.cognitive_load_score
                total_patients += latest.patients_seen or 0

        avg_fatigue = round(total_cls / doc_count, 1) if doc_count else 0
        patient_count = db.query(models.Patient).filter(
            models.Patient.ward_id == ward.id, models.Patient.status != "discharged"
        ).count()
        pat_doc_ratio = f"{patient_count}:{doc_count}" if doc_count else "N/A"

        ward_data = {
            "ward_id": ward.ward_uuid,
            "ward_name": ward.name,
            "ward_type": ward.ward_type,
            "hospital_name": hospital.name,
            "fatigue_index": avg_fatigue,
            "patient_count": patient_count,
            "doctor_count": doc_count,
            "pat_doc_ratio": pat_doc_ratio,
            "capacity": ward.capacity or 0,
            "utilization": round((patient_count / ward.capacity) * 100) if ward.capacity else 0,
            "status": "critical" if avg_fatigue >= 85 else "warning" if avg_fatigue >= 70 else "stable",
        }

        if avg_fatigue >= 70:
            overburdened.append(ward_data)
        else:
            stable.append(ward_data)

    overburdened.sort(key=lambda x: x["fatigue_index"], reverse=True)
    stable.sort(key=lambda x: x["fatigue_index"])

    recommendations = []
    for ob in overburdened:
        for st in stable:
            if st["doctor_count"] > 1 and st["fatigue_index"] < 50:
                projected_fatigue = max(0, ob["fatigue_index"] - 15)
                recommendations.append({
                    "id": f"REALLOC-{hash((ob['ward_id'], st['ward_id'])) % 10000:04d}",
                    "source_ward": st["ward_name"],
                    "source_hospital": st["hospital_name"],
                    "source_fatigue": st["fatigue_index"],
                    "source_available_staff": st["doctor_count"],
                    "target_ward": ob["ward_name"],
                    "target_hospital": ob["hospital_name"],
                    "target_fatigue": ob["fatigue_index"],
                    "projected_fatigue_after": projected_fatigue,
                    "projected_ratio_after": f"{max(1, ob['patient_count'] - 2)}:{ob['doctor_count'] + 1}",
                    "fatigue_reduction": f"-{round(ob['fatigue_index'] - projected_fatigue)}%",
                    "priority": "top" if ob["fatigue_index"] >= 85 else "normal",
                })
                break

    return {
        "hospital_name": hospital.name,
        "overburdened_units": overburdened,
        "stable_units": stable,
        "recommendations": recommendations,
        "overburdened_count": len(overburdened),
        "stable_count": len(stable),
    }
