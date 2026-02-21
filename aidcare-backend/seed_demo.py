#!/usr/bin/env python3
"""
Seed script — creates demo org, hospital, ward, doctors, patients.
Run: python seed_demo.py
"""
import os, uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

from aidcare_pipeline.database import SessionLocal, engine
from aidcare_pipeline import copilot_models as m
from aidcare_pipeline.auth import hash_password

m.create_copilot_tables()

db = SessionLocal()

# ── Helpers ───────────────────────────────────────────────────────────────────

def uid():
    return str(uuid.uuid4())

now = datetime.now(timezone.utc)

# ── Organization ──────────────────────────────────────────────────────────────

org = m.Organization(org_uuid=uid(), name="Lagos State Ministry of Health", org_type="government")
db.add(org)
db.flush()

# ── Hospital ──────────────────────────────────────────────────────────────────

hospital = m.Hospital(
    hospital_uuid=uid(), org_id=org.id,
    name="Lagos State University Teaching Hospital",
    code="LASUTH-EW-001", location="Ikeja, Lagos",
)
db.add(hospital)
db.flush()

# ── Wards ─────────────────────────────────────────────────────────────────────

emergency = m.Ward(ward_uuid=uid(), hospital_id=hospital.id, name="Emergency Ward", ward_type="emergency", capacity=40)
surgical = m.Ward(ward_uuid=uid(), hospital_id=hospital.id, name="Surgical Ward", ward_type="surgical", capacity=30)
db.add_all([emergency, surgical])
db.flush()

# ── Doctors ───────────────────────────────────────────────────────────────────

PASSWORD = "demo1234"

admin = m.Doctor(
    doctor_uuid=uid(), email="admin@lasuth.ng", password_hash=hash_password(PASSWORD),
    full_name="Dr. Amara Okafor", specialty="General Medicine",
    hospital_id=hospital.id, ward_id=emergency.id, role="hospital_admin",
)
doctor1 = m.Doctor(
    doctor_uuid=uid(), email="chioma@lasuth.ng", password_hash=hash_password(PASSWORD),
    full_name="Dr. Chioma Adebayo", specialty="Senior Registrar",
    hospital_id=hospital.id, ward_id=emergency.id, role="doctor",
)
doctor2 = m.Doctor(
    doctor_uuid=uid(), email="yusuf@lasuth.ng", password_hash=hash_password(PASSWORD),
    full_name="Dr. Yusuf Ibrahim", specialty="Junior Resident",
    hospital_id=hospital.id, ward_id=emergency.id, role="doctor",
)
doctor3 = m.Doctor(
    doctor_uuid=uid(), email="sarah@lasuth.ng", password_hash=hash_password(PASSWORD),
    full_name="Dr. Sarah Connor", specialty="Consultant",
    hospital_id=hospital.id, ward_id=surgical.id, role="doctor",
)
db.add_all([admin, doctor1, doctor2, doctor3])
db.flush()

# ── Patients ──────────────────────────────────────────────────────────────────

patients_data = [
    {
        "full_name": "Tunde Bakare", "age": 45, "gender": "Male",
        "bed_number": "4", "status": "critical",
        "primary_diagnosis": "Post-Appendectomy with complications",
        "vitals": {"bp": "160/95", "hr": 88, "temp": 37.2, "weight": 78},
        "allergies": ["Penicillin", "Peanuts"],
        "active_medications": [{"name": "Labetalol IV", "dose": "20mg bolus"}, {"name": "Ceftriaxone", "dose": "1g IV daily"}],
        "medical_history": [{"condition": "Appendectomy", "date": "2026-02-19", "notes": "Post-op day 2, BP spike at 10:00 AM"}],
        "attending": doctor1,
    },
    {
        "full_name": "Ifeoma Nnaji", "age": 32, "gender": "Female",
        "bed_number": "7", "status": "critical",
        "primary_diagnosis": "Severe Asthma - Monitoring",
        "vitals": {"bp": "120/80", "hr": 92, "temp": 37.0, "weight": 65},
        "allergies": ["Aspirin"],
        "active_medications": [{"name": "Salbutamol nebulizer", "dose": "5mg q4h"}],
        "medical_history": [{"condition": "Asthma", "date": "2024-01-15", "notes": "Chronic, multiple ER visits"}],
        "attending": doctor2,
    },
    {
        "full_name": "Emeka Okafor", "age": 55, "gender": "Male",
        "bed_number": "12", "status": "stable",
        "primary_diagnosis": "Fracture - Recovery",
        "vitals": {"bp": "130/85", "hr": 72, "temp": 36.8, "weight": 82},
        "allergies": [],
        "active_medications": [{"name": "Paracetamol", "dose": "1g TDS"}, {"name": "Lisinopril", "dose": "10mg Daily"}],
        "medical_history": [{"condition": "Right femur fracture", "date": "2026-02-10", "notes": "Surgical fixation done, healing well"}],
        "attending": doctor1,
    },
    {
        "full_name": "Fatima Yusuf", "age": 28, "gender": "Female",
        "bed_number": "15", "status": "stable",
        "primary_diagnosis": "Malaria - Observation",
        "vitals": {"bp": "110/70", "hr": 78, "temp": 38.5, "weight": 58},
        "allergies": ["Peanuts"],
        "active_medications": [{"name": "Coartem", "dose": "80/480mg BD x3 days"}],
        "medical_history": [{"condition": "Malaria Treatment", "date": "2026-02-19", "notes": "Day 2 of treatment"}],
        "attending": doctor2,
    },
    {
        "full_name": "Adebayo Oluwaseun", "age": 40, "gender": "Male",
        "bed_number": None, "status": "discharged",
        "primary_diagnosis": "Typhoid - Resolved",
        "vitals": {"bp": "120/75", "hr": 70, "temp": 36.6, "weight": 75},
        "allergies": [],
        "active_medications": [],
        "medical_history": [{"condition": "Typhoid fever", "date": "2026-02-12", "notes": "Completed treatment, fit for discharge"}],
        "attending": doctor1,
    },
]

patient_objects = []
for p in patients_data:
    attending = p.pop("attending")
    patient = m.Patient(
        patient_uuid=uid(), ward_id=emergency.id, attending_doctor_id=attending.id,
        admission_date=now - timedelta(days=3),
        **p,
    )
    db.add(patient)
    db.flush()
    patient_objects.append(patient)

# ── Shifts + Consultations + Burnout (for doctor1 and doctor2) ────────────────

for doc in [doctor1, doctor2]:
    shift = m.Shift(
        shift_uuid=uid(), doctor_id=doc.id, ward_id=emergency.id,
        shift_start=now - timedelta(hours=6), is_active=True,
    )
    db.add(shift)
    db.flush()

    # Create consultations for the patients this doctor attends
    doc_patients = [po for po, pd in zip(patient_objects, patients_data) if po.attending_doctor_id == doc.id]
    for i, pat in enumerate(doc_patients):
        consult = m.Consultation(
            consultation_uuid=uid(), doctor_id=doc.id, shift_id=shift.id,
            patient_id=pat.id, patient_ref=pat.full_name,
            transcript_text=f"Consultation with {pat.full_name} regarding {pat.primary_diagnosis}.",
            pidgin_detected=(i % 2 == 1),
            soap_subjective=f"Patient reports symptoms related to {pat.primary_diagnosis}.",
            soap_objective=f"Vitals: BP {(pat.vitals or {}).get('bp', 'N/A')}, HR {(pat.vitals or {}).get('hr', 'N/A')}.",
            soap_assessment=f"Working diagnosis: {pat.primary_diagnosis}. Condition is {'critical' if pat.status == 'critical' else 'stable and improving'}.",
            soap_plan="Continue current treatment. Monitor vitals q4h. Review labs in AM.",
            patient_summary=f"{pat.full_name}: {pat.primary_diagnosis}. Currently {pat.status}.",
            complexity_score=4 if pat.status == "critical" else 2,
            flags=["Urgent review needed", "BP spike"] if pat.status == "critical" else [],
            medication_changes=[
                {"action": "started", "drug": "Labetalol IV", "dose": "20mg bolus", "reason": "Hypertensive episode"}
            ] if pat.status == "critical" else [],
            language="en",
        )
        db.add(consult)
    db.flush()

    # Burnout scores
    cls_val = 78 if doc == doctor1 else 52
    status_val = "red" if cls_val >= 70 else "amber"
    burnout = m.BurnoutScore(
        score_uuid=uid(), doctor_id=doc.id, shift_id=shift.id,
        cognitive_load_score=cls_val, status=status_val,
        volume_score=32, complexity_score_component=18,
        duration_score=12, consecutive_shift_score=0,
        patients_seen=len(doc_patients), hours_active=6.0,
        avg_complexity=3.5,
    )
    db.add(burnout)

    # Fatigue snapshots (hourly for last 6h) for forecast chart
    for h in range(6):
        snap = m.FatigueSnapshot(
            doctor_id=doc.id, ward_id=emergency.id,
            cognitive_load_score=max(20, cls_val - (6 - h) * 8),
            patients_seen=h + 1, hours_active=float(h + 1),
            recorded_at=now - timedelta(hours=6 - h),
        )
        db.add(snap)

# Burnout for doctor3 (low load, surgical ward)
burnout3 = m.BurnoutScore(
    score_uuid=uid(), doctor_id=doctor3.id, shift_id=None,
    cognitive_load_score=24, status="green",
    volume_score=8, complexity_score_component=6,
    duration_score=4, consecutive_shift_score=0,
    patients_seen=2, hours_active=3.0, avg_complexity=2.0,
)
db.add(burnout3)

# ── Action Items ──────────────────────────────────────────────────────────────

action_items = [
    m.ActionItem(
        item_uuid=uid(), patient_id=patient_objects[0].id,
        created_by_doctor_id=doctor1.id,
        description="Check vitals & BP hourly",
        priority="high",
        due_time=now + timedelta(hours=2),
    ),
    m.ActionItem(
        item_uuid=uid(), patient_id=patient_objects[0].id,
        created_by_doctor_id=doctor1.id,
        description="Order renal function panel (bloods)",
        priority="normal",
        due_time=now + timedelta(hours=4),
    ),
    m.ActionItem(
        item_uuid=uid(), patient_id=patient_objects[0].id,
        created_by_doctor_id=doctor1.id,
        description="Review fluid balance chart",
        priority="normal",
    ),
    m.ActionItem(
        item_uuid=uid(), patient_id=patient_objects[1].id,
        created_by_doctor_id=doctor2.id,
        description="Repeat peak flow measurement",
        priority="high",
        due_time=now + timedelta(hours=1),
    ),
]
db.add_all(action_items)

# ── Commit everything ─────────────────────────────────────────────────────────

db.commit()
db.close()

print("\n" + "=" * 60)
print("  DEMO DATA SEEDED SUCCESSFULLY")
print("=" * 60)
print()
print("  Organization: Lagos State Ministry of Health")
print(f"  Hospital:     Lagos State University Teaching Hospital")
print(f"  Wards:        Emergency Ward, Surgical Ward")
print()
print("  ┌─────────────────────────────────────────────────────┐")
print("  │  LOGIN CREDENTIALS (password for all: demo1234)     │")
print("  ├─────────────────────────────────────────────────────┤")
print("  │  admin@lasuth.ng     Dr. Amara Okafor   (Admin)    │")
print("  │  chioma@lasuth.ng    Dr. Chioma Adebayo (Doctor)   │")
print("  │  yusuf@lasuth.ng     Dr. Yusuf Ibrahim  (Doctor)   │")
print("  │  sarah@lasuth.ng     Dr. Sarah Connor   (Doctor)   │")
print("  └─────────────────────────────────────────────────────┘")
print()
print(f"  Patients: {len(patient_objects)} (3 critical, 2 stable, 1 discharged)")
print(f"  Active shifts: 2 (Dr. Chioma, Dr. Yusuf)")
print(f"  Action items: {len(action_items)}")
print()
print("  Frontend: http://localhost:3000/login")
print("  Backend:  http://localhost:8000/docs")
print("=" * 60)
