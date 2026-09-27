from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from ...database.database import get_db
from ...database.models.entities import User
from ...security.jwt_rbac import get_current_active_user
from ...intelligence.medicine_knowledge import MedicineIntelligenceService
from ...services.multi_tenant.regional_intelligence import regional_intelligence

router = APIRouter(prefix="/intelligence", tags=["Medicine & Regional Intelligence Layer"])


@router.get("/medicines/{medicine_id}", summary="Get Verified Clinical, Regulatory & Storage Intelligence")
def get_medicine_clinical_intelligence(
    medicine_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves verified storage temperature, regulatory schedule, DCI, and brand equivalents.
    Complies with strict safety boundaries (no prescribing or diagnosis).
    """
    result = MedicineIntelligenceService.get_medicine_intelligence(medicine_id, db)
    if result.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/regional-supply", summary="Get Multi-Pharmacy Regional Supply & Shortage Index")
def get_regional_supply_insights(
    region: str = Query("Douala", description="City or Region to evaluate"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Multi-tenant regional supply index across pharmacy clusters with strict data privacy.
    """
    return regional_intelligence.get_regional_supply_index(region, db)
