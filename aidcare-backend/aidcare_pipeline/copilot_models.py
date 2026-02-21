# aidcare_pipeline/copilot_models.py
import os
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, JSON,
    Float, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base, engine


# --- Doctor Model ---
class Doctor(Base):
    __tablename__ = "copilot_doctors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    doctor_uuid = Column(String(36), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    specialty = Column(String(255), nullable=True)
    ward = Column(String(255), nullable=True)
    hospital = Column(String(255), nullable=True, default="")
    role = Column(String(50), nullable=False, default="doctor")  # 'doctor' | 'admin'
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    shifts = relationship("Shift", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    consultations = relationship("Consultation", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    burnout_scores = relationship("BurnoutScore", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")
    handover_reports = relationship("HandoverReport", back_populates="doctor", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Doctor(doctor_uuid='{self.doctor_uuid}', name='{self.full_name}', role='{self.role}')>"


# --- Shift Model ---
class Shift(Base):
    __tablename__ = "copilot_shifts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    shift_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    ward = Column(String(255), nullable=True)
    shift_start = Column(DateTime(timezone=True), server_default=func.now())
    shift_end = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    handover_generated = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    doctor = relationship("Doctor", back_populates="shifts")
    consultations = relationship("Consultation", back_populates="shift", cascade="all, delete-orphan", lazy="selectin")
    burnout_scores = relationship("BurnoutScore", back_populates="shift", cascade="all, delete-orphan", lazy="selectin")
    handover_reports = relationship("HandoverReport", back_populates="shift", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Shift(shift_uuid='{self.shift_uuid}', doctor_id={self.doctor_id}, is_active={self.is_active})>"


# --- Consultation Model ---
class Consultation(Base):
    __tablename__ = "copilot_consultations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    consultation_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(Integer, ForeignKey("copilot_shifts.id", ondelete="CASCADE"), nullable=False)
    patient_ref = Column(String(255), nullable=True)  # e.g. "Bed 4A" or anonymised ref
    transcript_text = Column(Text, nullable=True)
    soap_subjective = Column(Text, nullable=True)
    soap_objective = Column(Text, nullable=True)
    soap_assessment = Column(Text, nullable=True)
    soap_plan = Column(Text, nullable=True)
    patient_summary = Column(Text, nullable=True)
    complexity_score = Column(Integer, nullable=True, default=1)  # 1-5
    flags = Column(JSON, nullable=True)  # list of strings e.g. ["Urgent referral", "Allergy mentioned"]
    language = Column(String(10), nullable=True, default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    doctor = relationship("Doctor", back_populates="consultations")
    shift = relationship("Shift", back_populates="consultations")

    def __repr__(self):
        return f"<Consultation(consultation_uuid='{self.consultation_uuid}', patient_ref='{self.patient_ref}', complexity={self.complexity_score})>"


# --- BurnoutScore Model ---
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

    # Relationships
    doctor = relationship("Doctor", back_populates="burnout_scores")
    shift = relationship("Shift", back_populates="burnout_scores")

    def __repr__(self):
        return f"<BurnoutScore(score_uuid='{self.score_uuid}', doctor_id={self.doctor_id}, cls={self.cognitive_load_score}, status='{self.status}')>"


# --- HandoverReport Model ---
class HandoverReport(Base):
    __tablename__ = "copilot_handover_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    report_uuid = Column(String(36), unique=True, index=True, nullable=False)
    doctor_id = Column(Integer, ForeignKey("copilot_doctors.id", ondelete="CASCADE"), nullable=False)
    shift_id = Column(Integer, ForeignKey("copilot_shifts.id", ondelete="CASCADE"), nullable=False)
    report_json = Column(JSON, nullable=True)
    plain_text = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    doctor = relationship("Doctor", back_populates="handover_reports")
    shift = relationship("Shift", back_populates="handover_reports")

    def __repr__(self):
        return f"<HandoverReport(report_uuid='{self.report_uuid}', doctor_id={self.doctor_id})>"


# --- Table Creation ---
def create_copilot_tables():
    """
    Creates all copilot tables on the configured engine.
    Safe to call multiple times — SQLAlchemy skips existing tables.
    """
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
