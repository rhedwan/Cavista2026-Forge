# routers/orgs.py
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aidcare_pipeline.database import get_db
from aidcare_pipeline import copilot_models as models
from aidcare_pipeline.auth import get_current_user, require_role

router = APIRouter(prefix="/orgs", tags=["organizations"])


# --- Pydantic Schemas ---

class OrgCreate(BaseModel):
    name: str
    org_type: str = "private"  # 'government' | 'private'


class HospitalCreate(BaseModel):
    name: str
    code: str | None = None
    location: str | None = None


class WardCreate(BaseModel):
    name: str
    ward_type: str | None = None
    capacity: int = 0


# --- Serializers ---

def _serialize_org(org: models.Organization) -> dict:
    return {
        "org_id": org.org_uuid,
        "name": org.name,
        "org_type": org.org_type,
        "hospitals_count": len(org.hospitals) if org.hospitals else 0,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


def _serialize_hospital(h: models.Hospital) -> dict:
    return {
        "hospital_id": h.hospital_uuid,
        "name": h.name,
        "code": h.code,
        "location": h.location,
        "org_id": h.organization.org_uuid if h.organization else None,
        "wards_count": len(h.wards) if h.wards else 0,
    }


def _serialize_ward(w: models.Ward) -> dict:
    return {
        "ward_id": w.ward_uuid,
        "name": w.name,
        "ward_type": w.ward_type,
        "capacity": w.capacity,
        "hospital_id": w.hospital.hospital_uuid if w.hospital else None,
        "doctors_count": len(w.doctors) if w.doctors else 0,
        "patients_count": len(w.patients) if w.patients else 0,
    }


# --- Organization CRUD ---

@router.post("/")
def create_org(
    payload: OrgCreate,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(require_role("super_admin")),
):
    org = models.Organization(
        org_uuid=str(uuid.uuid4()),
        name=payload.name,
        org_type=payload.org_type,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return _serialize_org(org)


@router.get("/")
def list_orgs(
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    orgs = db.query(models.Organization).all()
    return {"organizations": [_serialize_org(o) for o in orgs]}


@router.get("/{org_uuid}")
def get_org(
    org_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    org = db.query(models.Organization).filter(models.Organization.org_uuid == org_uuid).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        **_serialize_org(org),
        "hospitals": [_serialize_hospital(h) for h in org.hospitals],
    }


# --- Hospital CRUD ---

@router.post("/{org_uuid}/hospitals")
def create_hospital(
    org_uuid: str,
    payload: HospitalCreate,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(require_role("super_admin", "org_admin")),
):
    org = db.query(models.Organization).filter(models.Organization.org_uuid == org_uuid).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    hospital = models.Hospital(
        hospital_uuid=str(uuid.uuid4()),
        org_id=org.id,
        name=payload.name,
        code=payload.code,
        location=payload.location,
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return _serialize_hospital(hospital)


@router.get("/{org_uuid}/hospitals")
def list_hospitals(
    org_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    org = db.query(models.Organization).filter(models.Organization.org_uuid == org_uuid).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"hospitals": [_serialize_hospital(h) for h in org.hospitals]}


# --- Ward CRUD ---

@router.post("/hospitals/{hospital_uuid}/wards")
def create_ward(
    hospital_uuid: str,
    payload: WardCreate,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(require_role("super_admin", "org_admin", "hospital_admin")),
):
    hospital = db.query(models.Hospital).filter(models.Hospital.hospital_uuid == hospital_uuid).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    ward = models.Ward(
        ward_uuid=str(uuid.uuid4()),
        hospital_id=hospital.id,
        name=payload.name,
        ward_type=payload.ward_type,
        capacity=payload.capacity,
    )
    db.add(ward)
    db.commit()
    db.refresh(ward)
    return _serialize_ward(ward)


@router.get("/hospitals/{hospital_uuid}/wards")
def list_wards(
    hospital_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    hospital = db.query(models.Hospital).filter(models.Hospital.hospital_uuid == hospital_uuid).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"wards": [_serialize_ward(w) for w in hospital.wards]}


@router.get("/wards/{ward_uuid}")
def get_ward(
    ward_uuid: str,
    db: Session = Depends(get_db),
    current_user: models.Doctor = Depends(get_current_user),
):
    ward = db.query(models.Ward).filter(models.Ward.ward_uuid == ward_uuid).first()
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found")
    return _serialize_ward(ward)
