# aidcare_pipeline/crud.py
from sqlalchemy.orm import Session
import uuid # For generating UUIDs
from . import db_models as models # Use an alias for clarity
from datetime import datetime

# --- Patient CRUD ---
def create_patient(db: Session, full_name: str = None, dob: datetime = None, gender: str = None) -> models.Patient:
    patient_uuid = str(uuid.uuid4())
    db_patient = models.Patient(
        patient_uuid=patient_uuid, 
        full_name=full_name, 
        date_of_birth=dob, 
        gender=gender
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient

def get_patient_by_uuid(db: Session, patient_uuid: str) -> models.Patient | None:
    return db.query(models.Patient).filter(models.Patient.patient_uuid == patient_uuid).first()

def get_patients(db: Session, skip: int = 0, limit: int = 100) -> list[models.Patient]:
    return db.query(models.Patient).offset(skip).limit(limit).all()

# --- PatientDocument CRUD ---
def create_patient_document(db: Session, patient_id: int, original_filename: str, storage_path: str, file_type: str) -> models.PatientDocument:
    doc_uuid = str(uuid.uuid4())
    db_document = models.PatientDocument(
        patient_id=patient_id,
        document_uuid=doc_uuid,
        original_filename=original_filename,
        storage_path=storage_path,
        file_type=file_type,
        processing_status="queued" # Initial status
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

def get_patient_documents(db: Session, patient_id: int, limit: int = 10) -> list[models.PatientDocument]:
    return db.query(models.PatientDocument)\
             .filter(models.PatientDocument.patient_id == patient_id)\
             .order_by(models.PatientDocument.upload_timestamp.desc())\
             .limit(limit)\
             .all()

def update_document_processing_status(db: Session, document_uuid: str, status: str, extracted_text: str = None, error_msg: str = None):
    db_document = db.query(models.PatientDocument).filter(models.PatientDocument.document_uuid == document_uuid).first()
    if db_document:
        db_document.processing_status = status
        db_document.processing_timestamp = datetime.utcnow() # Use UTC for server times
        if extracted_text:
            db_document.extracted_text = extracted_text
        if error_msg:
            db_document.error_message = error_msg
        db.commit()
        db.refresh(db_document)
        return db_document
    return None


# --- ConsultationSession CRUD ---
def create_consultation_session(db: Session, patient_id: int, mode: str, audio_path: str = None, transcript: str = None, manual_context: str = None) -> models.ConsultationSession:
    session_uuid = str(uuid.uuid4())
    db_session = models.ConsultationSession(
        session_uuid=session_uuid,
        patient_id=patient_id,
        mode=mode,
        audio_file_path=audio_path, # Path where audio might be stored long-term (e.g., S3 URL)
        transcript_text=transcript,
        manual_context_input=manual_context
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def update_consultation_session_results(
    db: Session, 
    session_uuid: str, 
    extracted_info: dict = None, 
    retrieved_docs: list = None, 
    final_recommendation: dict = None
):
    db_session = db.query(models.ConsultationSession).filter(models.ConsultationSession.session_uuid == session_uuid).first()
    if db_session:
        if extracted_info:
            db_session.extracted_info_json = extracted_info
        if retrieved_docs:
            db_session.retrieved_docs_summary_json = retrieved_docs # Assuming this is a summary
        if final_recommendation:
            db_session.final_recommendation_json = final_recommendation
        db.commit()
        db.refresh(db_session)
        return db_session
    return None

def get_patient_consultation_history(db: Session, patient_id: int, limit: int = 5) -> list[models.ConsultationSession]:
    return db.query(models.ConsultationSession)\
        .filter(models.ConsultationSession.patient_id == patient_id)\
        .order_by(models.ConsultationSession.timestamp_start.desc())\
        .limit(limit)\
        .all()