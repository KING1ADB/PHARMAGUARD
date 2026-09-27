import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user, require_roles
from ...database.models.entities import User
from ...services.onboarding.onboarding_service import onboarding_service

logger = logging.getLogger("PharmaGuard.OnboardingRouter")
router = APIRouter(prefix="/onboarding", tags=["Pilot Onboarding Workflow"])


class PharmacyRegisterRequest(BaseModel):
    organization_name: str
    license_number: str
    location: str
    contact_email: str
    address: Optional[str] = None
    phone: Optional[str] = None
    pilot_tier: Optional[str] = "STANDARD_PILOT"


class StaffSetupRequest(BaseModel):
    pharmacy_id: str
    name: str
    email: str
    password: str
    role: str = "PHARMACIST"
    phone: Optional[str] = None


class AgentActivationRequest(BaseModel):
    pharmacy_id: str
    morning_run_time: Optional[str] = "07:30"


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_pharmacy_endpoint(
    req: PharmacyRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Step 1: Register a new pilot pharmacy.
    """
    result = onboarding_service.register_pharmacy(
        organization_name=req.organization_name,
        license_number=req.license_number,
        location=req.location,
        contact_email=str(req.contact_email),
        db=db,
        address=req.address,
        phone=req.phone,
        pilot_tier=req.pilot_tier or "STANDARD_PILOT"
    )
    return result


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def setup_staff_endpoint(
    req: StaffSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Step 2: Provision a staff account with Role-Based Access Control (OWNER, PHARMACIST, ASSISTANT, AUDITOR).
    """
    result = onboarding_service.setup_staff_account(
        pharmacy_id=req.pharmacy_id,
        name=req.name,
        email=str(req.email),
        password=req.password,
        role=req.role,
        db=db,
        phone=req.phone
    )
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.post("/connect-data")
async def connect_initial_data_endpoint(
    pharmacy_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Step 3: Ingest initial inventory CSV and verify catalog completeness.
    """
    csv_bytes = await file.read()
    result = onboarding_service.connect_initial_data(
        pharmacy_id=pharmacy_id,
        csv_bytes=csv_bytes,
        filename=file.filename or "initial_inventory.csv",
        db=db
    )
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.post("/activate")
def activate_pharmacy_agent_endpoint(
    req: AgentActivationRequest,
    db: Session = Depends(get_db)
):
    """
    Step 4: Activate autonomous agent scheduling and execute the baseline intelligence cycle.
    """
    result = onboarding_service.activate_pharmacy_agent(
        pharmacy_id=req.pharmacy_id,
        morning_run_time=req.morning_run_time or "07:30",
        db=db
    )
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result
