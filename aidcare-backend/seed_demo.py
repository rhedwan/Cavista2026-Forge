#!/usr/bin/env python3
"""
Seed script — creates realistic demo data for AidCare hackathon demo.
Run: python seed_demo.py

Business model:
  Organizations (Govt ministries, NGOs, conglomerates)
    └─ Hospitals
         └─ Wards
              └─ Doctors (health workers)
              └─ Patients

Safe to re-run: drops and recreates all data.
"""
import os, uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
load_dotenv()

from aidcare_pipeline.database import SessionLocal, engine
from aidcare_pipeline import copilot_models as m
from aidcare_pipeline.auth import hash_password

# ── Create tables if they don't exist ─────────────────────────────────────────
m.create_copilot_tables()

db = SessionLocal()

# ── Clean existing data (order matters for FKs) ──────────────────────────────
print("Clearing existing data...")
for model in [
    m.FatigueSnapshot, m.HandoverReport, m.BurnoutScore,
    m.ActionItem, m.Consultation, m.Shift,
    m.Patient, m.Doctor, m.Ward, m.Hospital, m.Organization,
]:
    db.query(model).delete()
db.commit()
print("Done.\n")

# ── Helpers ───────────────────────────────────────────────────────────────────

def uid():
    return str(uuid.uuid4())

now = datetime.now(timezone.utc)
PASSWORD = "demo1234"
pw_hash = hash_password(PASSWORD)  # hash once, reuse

# =============================================================================
# ORGANIZATION 1: Lagos State Ministry of Health (Government)
# =============================================================================
print("Seeding Organization 1: Lagos State Ministry of Health...")

org1 = m.Organization(org_uuid=uid(), name="Lagos State Ministry of Health", org_type="government")
db.add(org1)
db.flush()

# ── Hospital 1A: LASUTH ──────────────────────────────────────────────────────

lasuth = m.Hospital(
    hospital_uuid=uid(), org_id=org1.id,
    name="Lagos State University Teaching Hospital (LASUTH)",
    code="LASUTH-001", location="Ikeja, Lagos",
)
db.add(lasuth)
db.flush()

# Wards under LASUTH
lasuth_emergency = m.Ward(ward_uuid=uid(), hospital_id=lasuth.id, name="Emergency Ward", ward_type="emergency", capacity=40)
lasuth_surgical  = m.Ward(ward_uuid=uid(), hospital_id=lasuth.id, name="Surgical Ward", ward_type="surgical", capacity=30)
lasuth_medical   = m.Ward(ward_uuid=uid(), hospital_id=lasuth.id, name="Medical Ward", ward_type="medical", capacity=35)
lasuth_icu       = m.Ward(ward_uuid=uid(), hospital_id=lasuth.id, name="Intensive Care Unit", ward_type="icu", capacity=12)
db.add_all([lasuth_emergency, lasuth_surgical, lasuth_medical, lasuth_icu])
db.flush()

# ── Hospital 1B: General Hospital Ikeja ──────────────────────────────────────

ghi = m.Hospital(
    hospital_uuid=uid(), org_id=org1.id,
    name="General Hospital Ikeja",
    code="GHI-001", location="Ikeja GRA, Lagos",
)
db.add(ghi)
db.flush()

ghi_emergency = m.Ward(ward_uuid=uid(), hospital_id=ghi.id, name="Emergency Ward", ward_type="emergency", capacity=25)
ghi_maternity = m.Ward(ward_uuid=uid(), hospital_id=ghi.id, name="Maternity Ward", ward_type="maternity", capacity=20)
db.add_all([ghi_emergency, ghi_maternity])
db.flush()

# =============================================================================
# ORGANIZATION 2: HealthPlus NGO (Private/NGO)
# =============================================================================
print("Seeding Organization 2: HealthPlus Foundation...")

org2 = m.Organization(org_uuid=uid(), name="HealthPlus Foundation", org_type="private")
db.add(org2)
db.flush()

# ── Hospital 2A: HealthPlus Community Clinic ─────────────────────────────────

hpcc = m.Hospital(
    hospital_uuid=uid(), org_id=org2.id,
    name="HealthPlus Community Clinic Ajegunle",
    code="HPCC-AJ-001", location="Ajegunle, Lagos",
)
db.add(hpcc)
db.flush()

hpcc_general  = m.Ward(ward_uuid=uid(), hospital_id=hpcc.id, name="General Outpatient", ward_type="outpatient", capacity=30)
hpcc_children = m.Ward(ward_uuid=uid(), hospital_id=hpcc.id, name="Children's Ward", ward_type="pediatric", capacity=20)
db.add_all([hpcc_general, hpcc_children])
db.flush()

# =============================================================================
# DOCTORS (Health Workers)
# =============================================================================
print("Seeding doctors...")

# -- Super Admin (can see all organizations) --
super_admin = m.Doctor(
    doctor_uuid=uid(), email="superadmin@aidcare.ng", password_hash=pw_hash,
    full_name="Dr. Ngozi Eze", specialty="Health Informatics",
    hospital_id=lasuth.id, ward_id=None, role="super_admin",
)

# -- LASUTH Doctors --
lasuth_admin = m.Doctor(
    doctor_uuid=uid(), email="admin@lasuth.ng", password_hash=pw_hash,
    full_name="Dr. Amara Okafor", specialty="General Medicine",
    hospital_id=lasuth.id, ward_id=lasuth_emergency.id, role="hospital_admin",
)
dr_chioma = m.Doctor(
    doctor_uuid=uid(), email="chioma@lasuth.ng", password_hash=pw_hash,
    full_name="Dr. Chioma Adebayo", specialty="Emergency Medicine",
    hospital_id=lasuth.id, ward_id=lasuth_emergency.id, role="doctor",
)
dr_yusuf = m.Doctor(
    doctor_uuid=uid(), email="yusuf@lasuth.ng", password_hash=pw_hash,
    full_name="Dr. Yusuf Ibrahim", specialty="Internal Medicine",
    hospital_id=lasuth.id, ward_id=lasuth_medical.id, role="doctor",
)
dr_sarah = m.Doctor(
    doctor_uuid=uid(), email="sarah@lasuth.ng", password_hash=pw_hash,
    full_name="Dr. Sarah Ogundimu", specialty="Surgery",
    hospital_id=lasuth.id, ward_id=lasuth_surgical.id, role="doctor",
)
dr_kemi = m.Doctor(
    doctor_uuid=uid(), email="kemi@lasuth.ng", password_hash=pw_hash,
    full_name="Dr. Kemi Afolabi", specialty="Critical Care",
    hospital_id=lasuth.id, ward_id=lasuth_icu.id, role="doctor",
)

# -- General Hospital Ikeja Doctors --
ghi_admin = m.Doctor(
    doctor_uuid=uid(), email="admin@ghi.ng", password_hash=pw_hash,
    full_name="Dr. Emeka Nwosu", specialty="Family Medicine",
    hospital_id=ghi.id, ward_id=ghi_emergency.id, role="hospital_admin",
)
dr_funke = m.Doctor(
    doctor_uuid=uid(), email="funke@ghi.ng", password_hash=pw_hash,
    full_name="Dr. Funke Adeyemi", specialty="Obstetrics & Gynaecology",
    hospital_id=ghi.id, ward_id=ghi_maternity.id, role="doctor",
)

# -- HealthPlus Clinic Doctors --
hp_admin = m.Doctor(
    doctor_uuid=uid(), email="admin@healthplus.ng", password_hash=pw_hash,
    full_name="Dr. Tayo Bakare", specialty="Community Health",
    hospital_id=hpcc.id, ward_id=hpcc_general.id, role="hospital_admin",
)
dr_mercy = m.Doctor(
    doctor_uuid=uid(), email="mercy@healthplus.ng", password_hash=pw_hash,
    full_name="Dr. Mercy Okeke", specialty="Pediatrics",
    hospital_id=hpcc.id, ward_id=hpcc_children.id, role="doctor",
)

all_doctors = [super_admin, lasuth_admin, dr_chioma, dr_yusuf, dr_sarah, dr_kemi, ghi_admin, dr_funke, hp_admin, dr_mercy]
db.add_all(all_doctors)
db.flush()

# =============================================================================
# PATIENTS
# =============================================================================
print("Seeding patients...")

# ── LASUTH Emergency Ward Patients ───────────────────────────────────────────
lasuth_e_patients_data = [
    {
        "full_name": "Tunde Bakare", "age": 45, "gender": "Male",
        "bed_number": "E-04", "status": "critical",
        "primary_diagnosis": "Hypertensive crisis post-appendectomy",
        "vitals": {"bp": "185/110", "hr": 102, "temp": 37.8, "weight": 78, "spo2": 96},
        "allergies": ["Penicillin", "Peanuts"],
        "active_medications": [
            {"name": "Labetalol IV", "dose": "20mg bolus q15min PRN"},
            {"name": "Ceftriaxone", "dose": "1g IV BD"},
            {"name": "Tramadol", "dose": "50mg IV q8h"},
        ],
        "medical_history": [
            {"condition": "Hypertension", "date": "2023-06-01", "notes": "On Lisinopril 10mg, poorly compliant"},
            {"condition": "Appendectomy", "date": "2026-02-19", "notes": "Post-op day 3, BP spike to 185/110 at 10:00 AM"},
        ],
        "attending": dr_chioma,
    },
    {
        "full_name": "Ifeoma Nnaji", "age": 32, "gender": "Female",
        "bed_number": "E-07", "status": "critical",
        "primary_diagnosis": "Acute severe asthma exacerbation",
        "vitals": {"bp": "120/80", "hr": 112, "temp": 37.0, "weight": 65, "spo2": 91},
        "allergies": ["Aspirin", "NSAIDs"],
        "active_medications": [
            {"name": "Salbutamol nebulizer", "dose": "5mg q2h"},
            {"name": "Ipratropium nebulizer", "dose": "0.5mg q4h"},
            {"name": "Hydrocortisone IV", "dose": "100mg q6h"},
            {"name": "Magnesium sulphate IV", "dose": "2g single dose"},
        ],
        "medical_history": [
            {"condition": "Asthma (chronic severe)", "date": "2018-03-15", "notes": "Multiple ICU admissions, on Seretide 250"},
            {"condition": "Previous ICU admission", "date": "2025-09-20", "notes": "Intubated for 48 hours, triggered by harmattan dust"},
        ],
        "attending": dr_chioma,
    },
    {
        "full_name": "Adaobi Chukwu", "age": 67, "gender": "Female",
        "bed_number": "E-11", "status": "critical",
        "primary_diagnosis": "Suspected stroke (left-sided weakness)",
        "vitals": {"bp": "190/100", "hr": 88, "temp": 36.9, "weight": 70, "spo2": 97},
        "allergies": [],
        "active_medications": [
            {"name": "Aspirin", "dose": "300mg stat"},
            {"name": "Amlodipine", "dose": "10mg daily"},
        ],
        "medical_history": [
            {"condition": "Type 2 Diabetes", "date": "2020-01-01", "notes": "On Metformin 1g BD, HbA1c 8.2%"},
            {"condition": "Hypertension", "date": "2019-06-01", "notes": "Poorly controlled"},
        ],
        "attending": dr_chioma,
    },
    {
        "full_name": "Emeka Okafor", "age": 55, "gender": "Male",
        "bed_number": "E-12", "status": "stable",
        "primary_diagnosis": "Right femur fracture — post-surgical fixation",
        "vitals": {"bp": "130/85", "hr": 72, "temp": 36.8, "weight": 82, "spo2": 99},
        "allergies": [],
        "active_medications": [
            {"name": "Paracetamol", "dose": "1g TDS"},
            {"name": "Enoxaparin", "dose": "40mg SC daily (DVT prophylaxis)"},
            {"name": "Lisinopril", "dose": "10mg daily"},
        ],
        "medical_history": [
            {"condition": "Right femur fracture (RTA)", "date": "2026-02-10", "notes": "Surgical fixation day 12, mobilizing with frame"},
            {"condition": "Hypertension", "date": "2021-05-01", "notes": "Well controlled on Lisinopril"},
        ],
        "attending": dr_chioma,
    },
    {
        "full_name": "Fatima Yusuf", "age": 28, "gender": "Female",
        "bed_number": "E-15", "status": "stable",
        "primary_diagnosis": "Severe malaria with anaemia",
        "vitals": {"bp": "110/70", "hr": 92, "temp": 38.5, "weight": 58, "spo2": 98},
        "allergies": [],
        "active_medications": [
            {"name": "Artesunate IV", "dose": "2.4mg/kg at 0, 12, 24h"},
            {"name": "Folic acid", "dose": "5mg daily"},
        ],
        "medical_history": [
            {"condition": "Recurrent malaria", "date": "2025-08-15", "notes": "3rd episode this year, Hb dropped to 7.2g/dL"},
            {"condition": "Sickle cell trait (AS)", "date": "2020-01-01", "notes": "Confirmed genotype"},
        ],
        "attending": dr_chioma,
    },
    {
        "full_name": "Adebayo Oluwaseun", "age": 40, "gender": "Male",
        "bed_number": None, "status": "discharged",
        "primary_diagnosis": "Typhoid fever — resolved",
        "vitals": {"bp": "120/75", "hr": 70, "temp": 36.6, "weight": 75, "spo2": 99},
        "allergies": [],
        "active_medications": [],
        "medical_history": [
            {"condition": "Typhoid fever", "date": "2026-02-12", "notes": "Completed 14-day Ciprofloxacin course, Widal titre normalised"},
        ],
        "attending": dr_chioma,
    },
]

# ── LASUTH Medical Ward Patients ─────────────────────────────────────────────
lasuth_m_patients_data = [
    {
        "full_name": "Chinedu Obi", "age": 52, "gender": "Male",
        "bed_number": "M-03", "status": "stable",
        "primary_diagnosis": "Uncontrolled Type 2 Diabetes with peripheral neuropathy",
        "vitals": {"bp": "140/90", "hr": 80, "temp": 36.7, "weight": 95, "spo2": 98},
        "allergies": ["Sulfonamides"],
        "active_medications": [
            {"name": "Metformin", "dose": "1g BD"},
            {"name": "Glimepiride", "dose": "4mg daily"},
            {"name": "Insulin glargine", "dose": "20 units nocte"},
            {"name": "Pregabalin", "dose": "75mg BD"},
        ],
        "medical_history": [
            {"condition": "Type 2 Diabetes", "date": "2018-01-01", "notes": "10-year history, HbA1c 10.1%, started insulin this admission"},
            {"condition": "Diabetic neuropathy", "date": "2025-06-01", "notes": "Bilateral feet numbness and tingling"},
        ],
        "attending": dr_yusuf, "ward": lasuth_medical,
    },
    {
        "full_name": "Mama Bisi Adewale", "age": 74, "gender": "Female",
        "bed_number": "M-08", "status": "stable",
        "primary_diagnosis": "Congestive heart failure (NYHA III)",
        "vitals": {"bp": "150/95", "hr": 96, "temp": 36.5, "weight": 68, "spo2": 93},
        "allergies": ["ACE inhibitors (cough)"],
        "active_medications": [
            {"name": "Furosemide", "dose": "40mg IV BD"},
            {"name": "Losartan", "dose": "50mg daily"},
            {"name": "Carvedilol", "dose": "6.25mg BD"},
            {"name": "Spironolactone", "dose": "25mg daily"},
        ],
        "medical_history": [
            {"condition": "Hypertensive heart disease", "date": "2020-01-01", "notes": "Echo: EF 30%, dilated LV"},
            {"condition": "Bilateral pleural effusion", "date": "2026-02-18", "notes": "Tapped 1.2L right side"},
        ],
        "attending": dr_yusuf, "ward": lasuth_medical,
    },
]

# ── LASUTH ICU Patient ───────────────────────────────────────────────────────
lasuth_icu_patients_data = [
    {
        "full_name": "Segun Ajayi", "age": 38, "gender": "Male",
        "bed_number": "ICU-02", "status": "critical",
        "primary_diagnosis": "Severe sepsis secondary to perforated duodenal ulcer",
        "vitals": {"bp": "90/60", "hr": 128, "temp": 39.2, "weight": 72, "spo2": 88},
        "allergies": ["Metronidazole"],
        "active_medications": [
            {"name": "Noradrenaline infusion", "dose": "0.1mcg/kg/min titrate to MAP>65"},
            {"name": "Meropenem", "dose": "1g IV q8h"},
            {"name": "Normal saline", "dose": "500ml bolus then 125ml/h"},
        ],
        "medical_history": [
            {"condition": "Peptic ulcer disease", "date": "2024-01-01", "notes": "H. pylori positive, incomplete treatment"},
            {"condition": "Emergency laparotomy", "date": "2026-02-21", "notes": "Graham patch repair, peritoneal washout"},
        ],
        "attending": dr_kemi, "ward": lasuth_icu,
    },
]

# ── HealthPlus Community Clinic Patients ─────────────────────────────────────
hpcc_patients_data = [
    {
        "full_name": "Blessing Okonkwo", "age": 8, "gender": "Female",
        "bed_number": "P-01", "status": "stable",
        "primary_diagnosis": "Acute watery diarrhoea with moderate dehydration",
        "vitals": {"bp": "90/60", "hr": 110, "temp": 37.8, "weight": 22, "spo2": 98},
        "allergies": [],
        "active_medications": [
            {"name": "ORS", "dose": "100ml after each stool"},
            {"name": "Zinc sulphate", "dose": "20mg daily x10 days"},
        ],
        "medical_history": [
            {"condition": "Diarrhoeal disease", "date": "2026-02-21", "notes": "3-day history, no blood in stool, drinking well"},
        ],
        "attending": dr_mercy, "ward": hpcc_children,
    },
    {
        "full_name": "Musa Ibrahim", "age": 4, "gender": "Male",
        "bed_number": "P-03", "status": "critical",
        "primary_diagnosis": "Severe pneumonia",
        "vitals": {"bp": "80/50", "hr": 140, "temp": 39.5, "weight": 14, "spo2": 89},
        "allergies": [],
        "active_medications": [
            {"name": "Ampicillin IV", "dose": "50mg/kg q6h"},
            {"name": "Gentamicin IV", "dose": "7.5mg/kg daily"},
            {"name": "Oxygen", "dose": "2L/min via nasal prongs"},
        ],
        "medical_history": [
            {"condition": "Recurrent chest infections", "date": "2025-11-01", "notes": "3rd pneumonia episode, consider HIV screening"},
            {"condition": "Malnutrition (moderate)", "date": "2025-06-01", "notes": "Weight-for-age Z-score -2.5"},
        ],
        "attending": dr_mercy, "ward": hpcc_children,
    },
    {
        "full_name": "Amina Bello", "age": 35, "gender": "Female",
        "bed_number": "G-05", "status": "stable",
        "primary_diagnosis": "Uncomplicated malaria",
        "vitals": {"bp": "110/70", "hr": 88, "temp": 38.8, "weight": 62, "spo2": 99},
        "allergies": [],
        "active_medications": [
            {"name": "Coartem (Artemether-Lumefantrine)", "dose": "80/480mg BD x3 days"},
            {"name": "Paracetamol", "dose": "1g TDS"},
        ],
        "medical_history": [
            {"condition": "Malaria", "date": "2026-02-21", "notes": "Positive RDT, no danger signs, Day 1 of ACT"},
        ],
        "attending": hp_admin, "ward": hpcc_general,
    },
]

# ── Create all patients ──────────────────────────────────────────────────────
all_patient_objects = []

# LASUTH Emergency Ward patients
for p in lasuth_e_patients_data:
    attending = p.pop("attending")
    ward = p.pop("ward", lasuth_emergency)
    patient = m.Patient(
        patient_uuid=uid(), ward_id=ward.id, attending_doctor_id=attending.id,
        admission_date=now - timedelta(days=3),
        **p,
    )
    db.add(patient)
    db.flush()
    all_patient_objects.append((patient, attending, ward))

# LASUTH Medical Ward patients
for p in lasuth_m_patients_data:
    attending = p.pop("attending")
    ward = p.pop("ward")
    patient = m.Patient(
        patient_uuid=uid(), ward_id=ward.id, attending_doctor_id=attending.id,
        admission_date=now - timedelta(days=5),
        **p,
    )
    db.add(patient)
    db.flush()
    all_patient_objects.append((patient, attending, ward))

# LASUTH ICU patients
for p in lasuth_icu_patients_data:
    attending = p.pop("attending")
    ward = p.pop("ward")
    patient = m.Patient(
        patient_uuid=uid(), ward_id=ward.id, attending_doctor_id=attending.id,
        admission_date=now - timedelta(days=1),
        **p,
    )
    db.add(patient)
    db.flush()
    all_patient_objects.append((patient, attending, ward))

# HealthPlus patients
for p in hpcc_patients_data:
    attending = p.pop("attending")
    ward = p.pop("ward")
    patient = m.Patient(
        patient_uuid=uid(), ward_id=ward.id, attending_doctor_id=attending.id,
        admission_date=now - timedelta(days=2),
        **p,
    )
    db.add(patient)
    db.flush()
    all_patient_objects.append((patient, attending, ward))

db.flush()

# =============================================================================
# SHIFTS + CONSULTATIONS + BURNOUT
# =============================================================================
print("Seeding shifts, consultations, and burnout data...")

# ── LASUTH Emergency — Dr. Chioma (active shift, heavy load) ─────────────────
shift_chioma = m.Shift(
    shift_uuid=uid(), doctor_id=dr_chioma.id, ward_id=lasuth_emergency.id,
    shift_start=now - timedelta(hours=8), is_active=True,
)
db.add(shift_chioma)
db.flush()

# Create consultations for all emergency patients
for pat, attending, ward in all_patient_objects:
    if attending.id == dr_chioma.id:
        consult = m.Consultation(
            consultation_uuid=uid(), doctor_id=dr_chioma.id, shift_id=shift_chioma.id,
            patient_id=pat.id, patient_ref=pat.full_name,
            transcript_text=(
                f"Doctor: Good morning {pat.full_name}, I'm Dr. Chioma. How are you feeling today? "
                f"Patient: Doctor, {pat.primary_diagnosis.lower()} is still bothering me. "
                f"Doctor: Let me examine you. Your vitals show BP {(pat.vitals or {}).get('bp', 'N/A')}, "
                f"heart rate {(pat.vitals or {}).get('hr', 'N/A')}, SpO2 {(pat.vitals or {}).get('spo2', 'N/A')}%. "
                f"I'll adjust your medications accordingly."
            ),
            pidgin_detected=False,
            soap_subjective=f"Patient {pat.full_name}, {pat.age}y {pat.gender}, complains of symptoms related to {pat.primary_diagnosis}. Reports feeling {'unwell with worsening symptoms' if pat.status == 'critical' else 'better overall, mild residual discomfort'}.",
            soap_objective=f"Vitals: BP {(pat.vitals or {}).get('bp', 'N/A')}, HR {(pat.vitals or {}).get('hr', 'N/A')}, Temp {(pat.vitals or {}).get('temp', 'N/A')}°C, SpO2 {(pat.vitals or {}).get('spo2', 'N/A')}%. {'Alert but distressed.' if pat.status == 'critical' else 'Alert, comfortable, mobilizing.'} Allergies: {', '.join(pat.allergies) if pat.allergies else 'NKDA'}.",
            soap_assessment=f"{pat.primary_diagnosis}. {'Condition critical — requires close monitoring and possible escalation.' if pat.status == 'critical' else 'Condition stable — improving on current management.'}",
            soap_plan=f"Continue current medications ({', '.join(m_item['name'] for m_item in (pat.active_medications or [])[:2])}). {'Monitor vitals q1h. Consider ICU transfer if deterioration.' if pat.status == 'critical' else 'Monitor vitals q4h. Plan discharge review in 24-48h.'}",
            patient_summary=f"{pat.full_name} ({pat.age}{pat.gender[0]}): {pat.primary_diagnosis}. Currently {pat.status}.",
            complexity_score=5 if pat.status == "critical" else 2,
            flags=(["Urgent review needed", "Hemodynamic instability"] if pat.status == "critical" else []),
            medication_changes=([
                {"action": "started", "drug": (pat.active_medications or [{}])[0].get("name", ""), "dose": (pat.active_medications or [{}])[0].get("dose", ""), "reason": f"Acute management of {pat.primary_diagnosis}"}
            ] if pat.status == "critical" else []),
            language="en",
        )
        db.add(consult)
db.flush()

# ── LASUTH Medical — Dr. Yusuf (active shift, moderate load) ─────────────────
shift_yusuf = m.Shift(
    shift_uuid=uid(), doctor_id=dr_yusuf.id, ward_id=lasuth_medical.id,
    shift_start=now - timedelta(hours=6), is_active=True,
)
db.add(shift_yusuf)
db.flush()

for pat, attending, ward in all_patient_objects:
    if attending.id == dr_yusuf.id:
        consult = m.Consultation(
            consultation_uuid=uid(), doctor_id=dr_yusuf.id, shift_id=shift_yusuf.id,
            patient_id=pat.id, patient_ref=pat.full_name,
            transcript_text=f"Consultation with {pat.full_name} regarding {pat.primary_diagnosis}.",
            soap_subjective=f"Patient reports ongoing symptoms of {pat.primary_diagnosis}.",
            soap_objective=f"Vitals: BP {(pat.vitals or {}).get('bp', 'N/A')}, HR {(pat.vitals or {}).get('hr', 'N/A')}.",
            soap_assessment=f"Working diagnosis: {pat.primary_diagnosis}.",
            soap_plan="Continue current management. Review labs.",
            patient_summary=f"{pat.full_name}: {pat.primary_diagnosis}. Currently {pat.status}.",
            complexity_score=3,
            language="en",
        )
        db.add(consult)
db.flush()

# ── HealthPlus — Dr. Mercy (active shift, pediatric ward) ───────────────────
shift_mercy = m.Shift(
    shift_uuid=uid(), doctor_id=dr_mercy.id, ward_id=hpcc_children.id,
    shift_start=now - timedelta(hours=4), is_active=True,
)
db.add(shift_mercy)
db.flush()

for pat, attending, ward in all_patient_objects:
    if attending.id == dr_mercy.id:
        consult = m.Consultation(
            consultation_uuid=uid(), doctor_id=dr_mercy.id, shift_id=shift_mercy.id,
            patient_id=pat.id, patient_ref=pat.full_name,
            transcript_text=f"Pediatric consultation for {pat.full_name}, age {pat.age}. {pat.primary_diagnosis}.",
            soap_subjective=f"Mother reports child has had symptoms for several days. {pat.primary_diagnosis}.",
            soap_objective=f"Weight: {(pat.vitals or {}).get('weight', 'N/A')}kg, Temp: {(pat.vitals or {}).get('temp', 'N/A')}°C, SpO2: {(pat.vitals or {}).get('spo2', 'N/A')}%.",
            soap_assessment=f"{pat.primary_diagnosis}. {'Danger signs present — close monitoring required.' if pat.status == 'critical' else 'No danger signs.'}",
            soap_plan=f"Continue treatment. {'Reassess q2h for danger signs.' if pat.status == 'critical' else 'Review in 24h.'}",
            patient_summary=f"{pat.full_name} ({pat.age}y): {pat.primary_diagnosis}.",
            complexity_score=4 if pat.status == "critical" else 2,
            flags=(["Danger signs", "Consider referral"] if pat.status == "critical" else []),
            language="en",
        )
        db.add(consult)
db.flush()

# =============================================================================
# BURNOUT SCORES + FATIGUE SNAPSHOTS
# =============================================================================
print("Seeding burnout and fatigue data...")

burnout_data = [
    # (doctor, shift, cls, status, patients_seen, hours, avg_complexity)
    (dr_chioma, shift_chioma, 82, "red", 6, 8.0, 4.2),
    (dr_yusuf, shift_yusuf, 48, "amber", 2, 6.0, 3.0),
    (dr_mercy, shift_mercy, 35, "green", 2, 4.0, 3.0),
    (dr_sarah, None, 28, "green", 1, 3.0, 2.5),
    (dr_kemi, None, 65, "amber", 1, 10.0, 5.0),
]

for doc, shift, cls, status, pts, hrs, avg_c in burnout_data:
    burnout = m.BurnoutScore(
        score_uuid=uid(), doctor_id=doc.id,
        shift_id=shift.id if shift else None,
        cognitive_load_score=cls, status=status,
        volume_score=min(40, pts * 8),
        complexity_score_component=min(30, int(avg_c * 6)),
        duration_score=min(20, int(hrs * 2)),
        consecutive_shift_score=0,
        patients_seen=pts, hours_active=hrs, avg_complexity=avg_c,
    )
    db.add(burnout)

    # Fatigue snapshots (hourly progression)
    total_hours = int(hrs)
    ward_id = shift.ward_id if shift else doc.ward_id
    for h in range(total_hours):
        progress_ratio = (h + 1) / total_hours
        snap_cls = int(cls * progress_ratio * 0.85 + 10)  # gradual rise
        snap = m.FatigueSnapshot(
            doctor_id=doc.id, ward_id=ward_id,
            cognitive_load_score=min(100, snap_cls),
            patients_seen=max(1, int(pts * progress_ratio)),
            hours_active=float(h + 1),
            recorded_at=now - timedelta(hours=total_hours - h),
        )
        db.add(snap)

db.flush()

# =============================================================================
# ACTION ITEMS
# =============================================================================
print("Seeding action items...")

# Find specific patients for action items
tunde = next(p for p, a, w in all_patient_objects if p.full_name == "Tunde Bakare")
ifeoma = next(p for p, a, w in all_patient_objects if p.full_name == "Ifeoma Nnaji")
adaobi = next(p for p, a, w in all_patient_objects if p.full_name == "Adaobi Chukwu")
segun = next(p for p, a, w in all_patient_objects if p.full_name == "Segun Ajayi")
musa = next(p for p, a, w in all_patient_objects if p.full_name == "Musa Ibrahim")

action_items = [
    # Emergency - Tunde (hypertensive crisis)
    m.ActionItem(item_uuid=uid(), patient_id=tunde.id, created_by_doctor_id=dr_chioma.id,
                 description="Recheck BP every 15 minutes. Target: <160/100 within 2 hours", priority="high",
                 due_time=now + timedelta(hours=1)),
    m.ActionItem(item_uuid=uid(), patient_id=tunde.id, created_by_doctor_id=dr_chioma.id,
                 description="Order urgent renal function panel and troponin", priority="high",
                 due_time=now + timedelta(hours=2)),
    m.ActionItem(item_uuid=uid(), patient_id=tunde.id, created_by_doctor_id=dr_chioma.id,
                 description="Review fluid balance chart — strict I/O monitoring", priority="normal",
                 due_time=now + timedelta(hours=4)),

    # Emergency - Ifeoma (asthma)
    m.ActionItem(item_uuid=uid(), patient_id=ifeoma.id, created_by_doctor_id=dr_chioma.id,
                 description="Repeat peak flow measurement after next nebulizer", priority="high",
                 due_time=now + timedelta(hours=1)),
    m.ActionItem(item_uuid=uid(), patient_id=ifeoma.id, created_by_doctor_id=dr_chioma.id,
                 description="Assess for ICU transfer if SpO2 drops below 90%", priority="high",
                 due_time=now + timedelta(hours=2)),

    # Emergency - Adaobi (stroke)
    m.ActionItem(item_uuid=uid(), patient_id=adaobi.id, created_by_doctor_id=dr_chioma.id,
                 description="Urgent CT brain scan — rule out haemorrhagic stroke", priority="high",
                 due_time=now + timedelta(minutes=30)),
    m.ActionItem(item_uuid=uid(), patient_id=adaobi.id, created_by_doctor_id=dr_chioma.id,
                 description="Neurology consult ASAP", priority="high",
                 due_time=now + timedelta(hours=1)),

    # ICU - Segun (sepsis)
    m.ActionItem(item_uuid=uid(), patient_id=segun.id, created_by_doctor_id=dr_kemi.id,
                 description="Blood cultures x2 from different sites", priority="high",
                 due_time=now + timedelta(minutes=15)),
    m.ActionItem(item_uuid=uid(), patient_id=segun.id, created_by_doctor_id=dr_kemi.id,
                 description="Titrate noradrenaline to MAP > 65mmHg", priority="high",
                 due_time=now + timedelta(hours=1)),

    # Pediatric - Musa (pneumonia)
    m.ActionItem(item_uuid=uid(), patient_id=musa.id, created_by_doctor_id=dr_mercy.id,
                 description="Reassess respiratory rate and chest indrawing q2h", priority="high",
                 due_time=now + timedelta(hours=2)),
    m.ActionItem(item_uuid=uid(), patient_id=musa.id, created_by_doctor_id=dr_mercy.id,
                 description="Request HIV screening (consent from mother)", priority="normal",
                 due_time=now + timedelta(hours=6)),
]
db.add_all(action_items)

# =============================================================================
# COMMIT ALL DATA
# =============================================================================
db.commit()
db.close()

# Count from all input data lists (patient objects are detached after commit)
all_statuses = (
    [p["status"] for p in lasuth_e_patients_data]
    + [p["status"] for p in lasuth_m_patients_data]
    + [p["status"] for p in lasuth_icu_patients_data]
    + [p["status"] for p in hpcc_patients_data]
)
total_patients = len(all_statuses)
critical_count = all_statuses.count("critical")
stable_count = all_statuses.count("stable")
discharged_count = all_statuses.count("discharged")

print("\n" + "=" * 70)
print("  AIDCARE DEMO DATA SEEDED SUCCESSFULLY")
print("=" * 70)
print()
print("  ORGANIZATIONS:")
print("    1. Lagos State Ministry of Health (Government)")
print("       ├─ LASUTH (4 wards: Emergency, Surgical, Medical, ICU)")
print("       └─ General Hospital Ikeja (2 wards: Emergency, Maternity)")
print("    2. HealthPlus Foundation (NGO)")
print("       └─ HealthPlus Community Clinic (2 wards: Outpatient, Pediatric)")
print()
print("  ┌──────────────────────────────────────────────────────────────┐")
print("  │  LOGIN CREDENTIALS (password for all: demo1234)              │")
print("  ├──────────────────────────────────────────────────────────────┤")
print("  │  SUPER ADMIN:                                                │")
print("  │    superadmin@aidcare.ng    Dr. Ngozi Eze                    │")
print("  │                                                              │")
print("  │  LASUTH:                                                     │")
print("  │    admin@lasuth.ng          Dr. Amara Okafor  (Hospital Admin)│")
print("  │    chioma@lasuth.ng         Dr. Chioma Adebayo (Emergency)   │")
print("  │    yusuf@lasuth.ng          Dr. Yusuf Ibrahim  (Medical)     │")
print("  │    sarah@lasuth.ng          Dr. Sarah Ogundimu (Surgical)    │")
print("  │    kemi@lasuth.ng           Dr. Kemi Afolabi   (ICU)         │")
print("  │                                                              │")
print("  │  GENERAL HOSPITAL IKEJA:                                     │")
print("  │    admin@ghi.ng             Dr. Emeka Nwosu   (Hospital Admin)│")
print("  │    funke@ghi.ng             Dr. Funke Adeyemi (Maternity)    │")
print("  │                                                              │")
print("  │  HEALTHPLUS CLINIC:                                          │")
print("  │    admin@healthplus.ng      Dr. Tayo Bakare   (Clinic Admin) │")
print("  │    mercy@healthplus.ng      Dr. Mercy Okeke   (Pediatrics)   │")
print("  └──────────────────────────────────────────────────────────────┘")
print()
print(f"  Patients: {total_patients} ({critical_count} critical, {stable_count} stable, {discharged_count} discharged)")
print(f"  Active shifts: 3 (Dr. Chioma, Dr. Yusuf, Dr. Mercy)")
print(f"  Action items: {len(action_items)}")
print(f"  Burnout scores: {len(burnout_data)} doctors tracked")
print()
print("  DEMO LOGIN (recommended): chioma@lasuth.ng / demo1234")
print("  ADMIN LOGIN:              admin@lasuth.ng / demo1234")
print()
print("  Frontend: http://localhost:3000/login")
print("  Backend:  http://localhost:8000/docs")
print("=" * 70)
