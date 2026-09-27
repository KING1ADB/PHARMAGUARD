import os
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "pharmaguard_enterprise_super_secret_jwt_key_2026_dla_cm")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hashes a plaintext password."""
    # Use sha256 + salt fallback if bcrypt backend issues occur
    try:
        return pwd_context.hash(password)
    except Exception:
        salt = "pharmaguard_salt_"
        return hashlib.sha256((salt + password).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a hash."""
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return pwd_context.verify(plain_password, hashed_password)
        salt = "pharmaguard_salt_"
        return hashlib.sha256((salt + plain_password).encode()).hexdigest() == hashed_password
    except Exception:
        salt = "pharmaguard_salt_"
        return hashlib.sha256((salt + plain_password).encode()).hexdigest() == hashed_password


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please log in again."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token."
        )


def get_current_user_payload(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> Dict[str, Any]:
    """Extracts and verifies JWT claims from request Authorization header."""
    if not credentials:
        # Fallback default admin user for local dev/testing if unauthenticated
        return {
            "sub": "USR-ADMIN-001",
            "name": "Dr. Jean-Paul Mbarga",
            "email": "pharmacist@pharmaguard.cm",
            "role": "PHARMACIST",
            "pharmacy_id": os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001"),
            "permissions": ["READ", "WRITE", "APPROVE_ORDERS", "AUDIT"]
        }
    return decode_access_token(credentials.credentials)


class UserRole:
    OWNER = "OWNER"
    PHARMACIST = "PHARMACIST"
    ASSISTANT = "ASSISTANT"
    AUDITOR = "AUDITOR"


class AuthenticatedUser:
    def __init__(self, id: str, email: str, role: str, pharmacy_id: str, full_name: Optional[str] = None):
        self.id = id
        self.email = email
        self.role = role
        self.pharmacy_id = pharmacy_id
        self.full_name = full_name or email
        self.is_active = True


def get_current_active_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> AuthenticatedUser:
    """Extracts and verifies JWT claims and returns an AuthenticatedUser instance."""
    if not credentials:
        return AuthenticatedUser(
            id="USR-ADMIN-001",
            email="pharmacist@pharmaguard.cm",
            role=UserRole.PHARMACIST,
            pharmacy_id=os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001"),
            full_name="Dr. Jean-Paul Mbarga"
        )
    payload = decode_access_token(credentials.credentials)
    return AuthenticatedUser(
        id=payload.get("sub", "USR-ADMIN-001"),
        email=payload.get("email", "pharmacist@pharmaguard.cm"),
        role=payload.get("role", UserRole.PHARMACIST),
        pharmacy_id=payload.get("pharmacy_id", "PHARM-DLA-001"),
        full_name=payload.get("name", "Dr. Jean-Paul Mbarga")
    )


def require_role(allowed_roles: List[str]):
    """Role-Based Access Control (RBAC) dependency verifying user roles."""
    def role_checker(user: AuthenticatedUser = Depends(get_current_active_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {allowed_roles}"
            )
        return user
    return role_checker


def require_roles(allowed_roles: List[str]):
    return require_role(allowed_roles)


get_current_user = get_current_active_user

