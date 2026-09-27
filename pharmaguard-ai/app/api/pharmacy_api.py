from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database.database import get_db
from ..database.models import Pharmacy, Supplier
from ..database.schemas import PharmacyResponse, SupplierResponse

router = APIRouter(prefix="/pharmacy", tags=["Pharmacy Operations"])


@router.get("/profile", response_model=PharmacyResponse)
def get_pharmacy_profile(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Retrieves the active pharmacy profile and location."""
    pharm = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    if not pharm:
        raise HTTPException(status_code=404, detail="Pharmacy not found")
    return pharm


@router.get("/suppliers", response_model=List[SupplierResponse])
def list_connected_suppliers(db: Session = Depends(get_db)):
    """Lists wholesale medicine suppliers with delivery lead times and reliability."""
    suppliers = db.query(Supplier).all()
    return suppliers
