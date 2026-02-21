# routers/auth.py
import traceback
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    specialty: str | None = None
    role: str = "doctor"  # 'super_admin' | 'org_admin' | 'hospital_admin' | 'doctor'


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _serialize_user(doctor: models.Doctor) -> dict:
    try:
        hospital = doctor.hospital
    except Exception:
        hospital = None
    try:
        ward = doctor.ward_rel
    except Exception:
        ward = None
    org = hospital.organization if hospital else None
    return {
        "doctor_id": doctor.doctor_uuid,
        "email": doctor.email,
        "name": doctor.full_name,
        "specialty": doctor.specialty or "",
        "role": doctor.role,
        "hospital_id": hospital.hospital_uuid if hospital else None,
        "hospital_name": hospital.name if hospital else None,
        "ward_id": ward.ward_uuid if ward else None,
        "ward_name": ward.name if ward else None,
        "org_id": org.org_uuid if org else None,
        "org_name": org.name if org else None,
    }


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        existing = db.query(models.Doctor).filter(models.Doctor.email == payload.email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        doctor = models.Doctor(
            doctor_uuid=str(uuid.uuid4()),
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            specialty=payload.specialty,
            role=payload.role,
            is_active=True,
        )
        db.add(doctor)
        db.commit()
        db.refresh(doctor)

        token = create_access_token(data={"sub": doctor.doctor_uuid})
        return TokenResponse(access_token=token, user=_serialize_user(doctor))
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        msg = str(e)
        if "UndefinedColumn" in msg or "does not exist" in msg.lower() or "ProgrammingError" in type(e).__name__:
            msg = "Database schema needs updating. Please contact support or run migrations."
        raise HTTPException(status_code=500, detail=msg)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    doctor = db.query(models.Doctor).filter(models.Doctor.email == payload.email).first()
    if not doctor or not verify_password(payload.password, doctor.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not doctor.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    token = create_access_token(data={"sub": doctor.doctor_uuid})
    return TokenResponse(access_token=token, user=_serialize_user(doctor))


@router.get("/me")
def get_me(current_user: models.Doctor = Depends(get_current_user)):
    return _serialize_user(current_user)
