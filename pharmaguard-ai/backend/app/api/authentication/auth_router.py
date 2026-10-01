from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...database.models.entities import User
from ...database.schemas.entities_schema import UserLogin, TokenResponse
from ...security.jwt_rbac import verify_password, create_access_token, get_current_user_payload, get_current_user
from ...services.auth.auth_service import production_auth_service

router = APIRouter(prefix="/auth", tags=["Production Authentication & Security"])


class OwnerRegisterRequest(BaseModel):
    organization_name: str
    license_number: str
    location: str
    owner_name: str
    owner_email: str
    password: str
    phone: Optional[str] = None
    address: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str


class MFAVerifyRequest(BaseModel):
    token: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_owner_endpoint(req: OwnerRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new pharmacy organization and creates the root OWNER account."""
    result = production_auth_service.register_owner_and_pharmacy(
        organization_name=req.organization_name,
        license_number=req.license_number,
        location=req.location,
        owner_name=req.owner_name,
        owner_email=req.owner_email,
        password=req.password,
        phone=req.phone,
        address=req.address,
        db=db
    )
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.post("/login", response_model=TokenResponse)
def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticates a pharmacist or pharmacy owner and returns a signed JWT."""
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token_payload = {
        "sub": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "pharmacy_id": user.pharmacy_id
    }
    access_token = create_access_token(token_payload)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "role": user.role,
        "pharmacy_id": user.pharmacy_id
    }


@router.post("/verify-email")
def verify_email_endpoint(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verifies a user's email address using the received verification token."""
    result = production_auth_service.verify_email_token(req.token, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.post("/forgot-password")
def forgot_password_endpoint(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Initiates password reset and generates a time-limited reset token."""
    return production_auth_service.request_password_reset(req.email, db)


@router.post("/reset-password")
def reset_password_endpoint(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Confirms password reset and updates password hash."""
    result = production_auth_service.confirm_password_reset(req.reset_token, req.new_password, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.post("/mfa/setup")
def setup_mfa_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates an MFA secret for TOTP authenticator setup."""
    return production_auth_service.setup_mfa(current_user.id, db)


@router.post("/mfa/verify")
def verify_mfa_endpoint(
    req: MFAVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verifies 6-digit MFA token and enables MFA on the account."""
    result = production_auth_service.verify_mfa_token(current_user.id, req.token, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("message"))
    return result


@router.get("/me")
def get_authenticated_user_profile(user_payload: dict = Depends(get_current_user_payload)):
    """Returns claims of current authenticated session."""
    return user_payload
