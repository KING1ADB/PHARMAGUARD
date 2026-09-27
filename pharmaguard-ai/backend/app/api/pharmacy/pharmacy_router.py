from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database.database import get_db
from ...database.models.entities import Pharmacy, Supplier
from ...database.schemas.entities_schema import PharmacyResponse, SupplierResponse
from ...security.jwt_rbac import get_current_user_payload

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy Operations"])


@router.get("/profile", response_model=PharmacyResponse)
def get_pharmacy_profile(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_payload)
):
    """Retrieves verified pharmacy organization information."""
    pharmacy_id = user.get("pharmacy_id", "PHARM-DLA-001")
    pharm = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    if not pharm:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return pharm


@router.get("/suppliers", response_model=List[SupplierResponse])
def list_connected_suppliers(db: Session = Depends(get_db)):
    """Lists wholesale suppliers with delivery lead times and reliability scores."""
    return db.query(Supplier).all()
