import os
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func # For server-side default timestamps
from .database import Base, engine # Import Base and engine from our database.py

# --- Patient Model ---
class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_uuid = Column(String(36), unique=True, index=True, nullable=False) # UUIDs are 36 chars
    full_name = Column(String(255), index=True, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(50), nullable=True)
    # Add other fields like contact_info (JSON or separate table), address, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships: if a patient is deleted, their documents and sessions are also deleted
    documents = relationship("PatientDocument", back_populates="patient", cascade="all, delete-orphan", lazy="selectin")
    sessions = relationship("ConsultationSession", back_populates="patient", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Patient(patient_uuid='{self.patient_uuid}', name='{self.full_name}')>"

# --- Patient Document Model ---
class PatientDocument(Base):
    __tablename__ = "patient_documents"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False) # Ensure FK points to patients.id
    document_uuid = Column(String(36), unique=True, index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False) # Path in object storage or local filesystem
    file_type = Column(String(100), nullable=True)
    extracted_text = Column(Text, nullable=True)
    processing_status = Column(String(50), default="queued", nullable=False) # e.g., queued, processing, completed, failed
    upload_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    processing_timestamp = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    patient = relationship("Patient", back_populates="documents")

    def __repr__(self):
        return f"<PatientDocument(document_uuid='{self.document_uuid}', filename='{self.original_filename}')>"

# --- Consultation Session Model ---
class ConsultationSession(Base):
    __tablename__ = "consultation_sessions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_uuid = Column(String(36), unique=True, index=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False) # Ensure FK points to patients.id
    mode = Column(String(50), nullable=False) # 'chw_triage' or 'clinical_support'
    
    timestamp_start = Column(DateTime(timezone=True), server_default=func.now())
    # timestamp_end = Column(DateTime(timezone=True), nullable=True) # Optional
    
    audio_file_path = Column(String(512), nullable=True) # Path to stored audio (e.g., S3 URL or local path)
    transcript_text = Column(Text, nullable=True)
    manual_context_input = Column(Text, nullable=True) # For clinical mode

    extracted_info_json = Column(JSON, nullable=True) 
    retrieved_docs_summary_json = Column(JSON, nullable=True)
    final_recommendation_json = Column(JSON, nullable=True)

    patient = relationship("Patient", back_populates="sessions")

    def __repr__(self):
        return f"<ConsultationSession(session_uuid='{self.session_uuid}', mode='{self.mode}')>"


# Function to create tables (callable for initial setup or via Alembic)
def create_db_and_tables():
    print(f"Attempting to create database tables on engine: {engine.url}...")
    # In a more complex app, you might want to ensure the DB itself exists,
    # but for PostgreSQL, `create_all` typically works on an existing DB.
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables checked/created successfully (if they didn't exist).")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        print("Please ensure the database exists and the user has permissions.")
        print("DATABASE_URL used:", os.environ.get("DATABASE_URL"))


if __name__ == "__main__":
    # This allows running `python -m aidcare_pipeline.db_models` from `aidcare-backend` root
    # to create tables if your DATABASE_URL in .env is correctly set up.
    print("Running db_models.py directly to create tables...")
    create_db_and_tables()