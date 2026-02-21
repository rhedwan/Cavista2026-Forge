# aidcare_pipeline/copilot_models.py
import os
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON,
    Float, Boolean, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base, engine


# ---------------------------------------------------------------------------
# Multi-Tenant Hierarchy: Organization → Hospital → Ward
# ---------------------------------------------------------------------------

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    org_uuid = Column(String(36), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    org_type = Column(String(50), nullable=False, default="private")  # 'government' | 'private'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hospitals = relationship("Hospital", back_populates="organization", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Organization(org_uuid='{self.org_uuid}', name='{self.name}', type='{self.org_type}')>"


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hospital_uuid = Column(String(36), unique=True, index=True, nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=True)  # e.g. LASUTH-EW-001
    location = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="hospitals")
    wards = relationship("Ward", back_populates="hospital", cascade="all, delete-orphan", lazy="selectin")
    doctors = relationship("Doctor", back_populates="hospital", lazy="selectin")

    def __repr__(self):
        return f"<Hospital(hospital_uuid='{self.hospital_uuid}', name='{self.name}')>"


class Ward(Base):
    __tablename__ = "wards"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ward_uuid = Column(String(36), unique=True, index=True, nullable=False)
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    ward_type = Column(String(100), nullable=True)  # 'emergency' | 'surgical' | 'medical' | 'icu' | ...
    capacity = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hospital = relationship("Hospital", back_populates="wards")
    doctors = relationship("Doctor", back_populates="ward_rel", lazy="selectin")
    patients = relationship("Patient", back_populates="ward", lazy="selectin")

    def __repr__(self):
        return f"<Ward(ward_uuid='{self.ward_uuid}', name='{self.name}', type='{self.ward_type}')>"


# ---------------------------------------------------------------------------
# Doctor (User) Model — now linked to org hierarchy with auth fields
# ---------------------------------------------------------------------------

class Doctor(Base):
    __tablename__ = "copilot_doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doctor_uuid = Column(String(36), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    specialty = Column(String(255), nullable=True)

    # Multi-tenant FKs
    hospital_id = Column(Integer, ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True)

    # 'super_admin' | 'org_admin' | 'hospital_admin' | 'doctor'
    role = Column(String(50), nullable=False, default="doctor")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    hospital = relationship("Hospital", back_populates="doctors")
    ward_rel = relationship("Ward", back_populates="doctors")
    shifts = relationship("Shift", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    consultations = relationship("Consultation", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    burnout_scores = relationship("BurnoutScore", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    handover_reports = relationship("HandoverReport", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    fatigue_snapshots = relationship("FatigueSnapshot", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Doctor(doctor_uuid='{self.doctor_uuid}', name='{self.full_name}', role='{self.role}')>"


# ---------------------------------------------------------------------------
# Patient Model — linked to ward with clinical status
# ---------------------------------------------------------------------------

class Patient(Base):
    __tablename__ = "copilot_patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_uuid = Column(String(36), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)

    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True)
    attending_doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="SET NULL"), nullable=True)

    bed_number = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="stable")  # 'critical' | 'stable' | 'discharged'
    admission_date = Column(DateTime(timezone=True), nullable=True)
    discharge_date = Column(DateTime(timezone=True), nullable=True)
    primary_diagnosis = Column(Text, nullable=True)

    # Clinical data stored as JSON for flexibility
    vitals = Column(JSON, nullable=True)          # {"bp": "130/85", "hr": 82, "temp": 38.5, "weight": 78}
    allergies = Column(JSON, nullable=True)        # ["Penicillin", "Peanuts"]
    active_medications = Column(JSON, nullable=True)  # [{"name": "Lisinopril", "dose": "10mg Daily"}]
    medical_history = Column(JSON, nullable=True)  # [{"condition": "Malaria", "date": "...", "notes": "..."}]
    triage_result = Column(JSON, nullable=True)    # saved from triage page: {risk_level, urgency, symptoms, ...}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    ward = relationship("Ward", back_populates="patients")
    attending_doctor = relationship("Doctor", foreign_keys=[attending_doctor_id])
    consultations = relationship("Consultation", back_populates="patient", cascade="all, delete-orphan", lazy="selectin")
    action_items = relationship("ActionItem", back_populates="patient", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Patient(patient_uuid='{self.patient_uuid}', name='{self.full_name}', status='{self.status}')>"


# ---------------------------------------------------------------------------
# Shift Model
# ---------------------------------------------------------------------------

class Shift(Base):
    __tablename__ = "copilot_shifts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    shift_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True)
    shift_start = Column(DateTime(timezone=True), server_default=func.now())
    shift_end = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    handover_generated = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="shifts")
    ward_rel = relationship("Ward")
    consultations = relationship("Consultation", back_populates="shift", cascade="all, delete-orphan", lazy="selectin")
    burnout_scores = relationship("BurnoutScore", back_populates="shift", cascade="all, delete-orphan", lazy="selectin")
    handover_reports = relationship("HandoverReport", back_populates="shift", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Shift(shift_uuid='{self.shift_uuid}', doctor_id={self.doctor_id}, is_active={self.is_active})>"


# ---------------------------------------------------------------------------
# Consultation Model — now links to patient
# ---------------------------------------------------------------------------

class Consultation(Base):
    __tablename__ = "copilot_consultations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    consultation_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(Integer, ForeignKey("copilot_shifts.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("copilot_patients.id", ondelete="SET NULL"), nullable=True)

    patient_ref = Column(String(255), nullable=True)
    transcript = Column(JSON, nullable=True)  # full transcript as structured JSON [{role, content, timestamp}]
    transcript_text = Column(Text, nullable=True)
    pidgin_detected = Column(Boolean, nullable=False, default=False)

    soap_subjective = Column(Text, nullable=True)
    soap_objective = Column(Text, nullable=True)
    soap_assessment = Column(Text, nullable=True)
    soap_plan = Column(Text, nullable=True)
    patient_summary = Column(Text, nullable=True)
    complexity_score = Column(Integer, nullable=True, default=1)  # 1-5
    flags = Column(JSON, nullable=True)
    medication_changes = Column(JSON, nullable=True)  # [{"action":"started"|"stopped"|"continued", "drug":"...", ...}]
    language = Column(String(10), nullable=True, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="consultations")
    shift = relationship("Shift", back_populates="consultations")
    patient = relationship("Patient", back_populates="consultations")

    def __repr__(self):
        return f"<Consultation(consultation_uuid='{self.consultation_uuid}', patient_ref='{self.patient_ref}', complexity={self.complexity_score})>"


# ---------------------------------------------------------------------------
# ActionItem Model — tasks for next shift
# ---------------------------------------------------------------------------

class ActionItem(Base):
    __tablename__ = "copilot_action_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    item_uuid = Column(String(36), unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("copilot_patients.id", ondelete="CASCADE"), nullable=False)
    consultation_id = Column(Integer, ForeignKey("copilot_consultations.id", ondelete="SET NULL"), nullable=True)
    created_by_doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="SET NULL"), nullable=True)

    description = Column(Text, nullable=False)
    priority = Column(String(20), nullable=False, default="normal")  # 'high' | 'normal' | 'low'
    due_time = Column(DateTime(timezone=True), nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="action_items")
    consultation = relationship("Consultation")
    created_by = relationship("Doctor")

    def __repr__(self):
        return f"<ActionItem(item_uuid='{self.item_uuid}', priority='{self.priority}', completed={self.completed})>"


# ---------------------------------------------------------------------------
# BurnoutScore Model
# ---------------------------------------------------------------------------

class BurnoutScore(Base):
    __tablename__ = "copilot_burnout_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    score_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(Integer, ForeignKey("copilot_shifts.id", ondelete="SET NULL"), nullable=True)
    cognitive_load_score = Column(Integer, nullable=False, default=0)  # 0-100
    status = Column(String(10), nullable=False, default="green")  # 'green' | 'amber' | 'red'
    volume_score = Column(Integer, nullable=True, default=0)
    complexity_score_component = Column(Integer, nullable=True, default=0)
    duration_score = Column(Integer, nullable=True, default=0)
    consecutive_shift_score = Column(Integer, nullable=True, default=0)
    patients_seen = Column(Integer, nullable=True, default=0)
    hours_active = Column(Float, nullable=True, default=0.0)
    avg_complexity = Column(Float, nullable=True, default=0.0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="burnout_scores")
    shift = relationship("Shift", back_populates="burnout_scores")

    def __repr__(self):
        return f"<BurnoutScore(score_uuid='{self.score_uuid}', cls={self.cognitive_load_score}, status='{self.status}')>"


# ---------------------------------------------------------------------------
# FatigueSnapshot — time-series data for fatigue forecast charts
# ---------------------------------------------------------------------------

class FatigueSnapshot(Base):
    __tablename__ = "copilot_fatigue_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True)
    cognitive_load_score = Column(Integer, nullable=False, default=0)
    patients_seen = Column(Integer, nullable=True, default=0)
    hours_active = Column(Float, nullable=True, default=0.0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="fatigue_snapshots")
    ward_rel = relationship("Ward")

    def __repr__(self):
        return f"<FatigueSnapshot(doctor_id={self.doctor_id}, cls={self.cognitive_load_score})>"


# ---------------------------------------------------------------------------
# HandoverReport Model — now supports ward-level handovers
# ---------------------------------------------------------------------------

class HandoverReport(Base):
    __tablename__ = "copilot_handover_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    report_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(Integer, ForeignKey("copilot_shifts.id", ondelete="CASCADE"), nullable=False)
    ward_id = Column(Integer, ForeignKey("wards.id", ondelete="SET NULL"), nullable=True)
    report_json = Column(JSON, nullable=True)
    plain_text = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="handover_reports")
    shift = relationship("Shift", back_populates="handover_reports")
    ward_rel = relationship("Ward")

    def __repr__(self):
        return f"<HandoverReport(report_uuid='{self.report_uuid}', doctor_id={self.doctor_id})>"


# ---------------------------------------------------------------------------
# Table Creation
# ---------------------------------------------------------------------------

def create_copilot_tables():
    """Creates all copilot tables. Safe to call multiple times."""
    print(f"Attempting to create copilot tables on engine: {engine.url}...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Copilot tables checked/created successfully.")
    except Exception as e:
        print(f"Error creating copilot tables: {e}")
        print("Please ensure the database exists and the user has permissions.")
        print("DATABASE_URL used:", os.environ.get("DATABASE_URL"))


if __name__ == "__main__":
    print("Running copilot_models.py directly to create tables...")
    create_copilot_tables()
