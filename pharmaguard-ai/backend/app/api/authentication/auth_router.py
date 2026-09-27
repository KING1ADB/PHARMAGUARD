from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...database.database import get_db
from ...database.models.entities import User
from ...database.schemas.entities_schema import UserLogin, TokenResponse, UserResponse
from ...security.jwt_rbac import verify_password, create_access_token, get_current_user_payload

router = APIRouter(prefix="/auth", tags=["Authentication & Security"])


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


@router.get("/me")
def get_authenticated_user_profile(user_payload: dict = Depends(get_current_user_payload)):
    """Returns claims of current authenticated session."""
    return user_payload
