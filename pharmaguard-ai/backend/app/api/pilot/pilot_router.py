import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user, require_roles
from ...database.models.entities import User
from ...services.pilot.pilot_manager import pilot_manager
from ...services.validation.pilot_scenario_runner import pilot_scenario_runner

logger = logging.getLogger("PharmaGuard.PilotRouter")
router = APIRouter(prefix="/pilot", tags=["Production Pilot Management"])


@router.get("/overview")
def get_pilot_overview_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["OWNER", "AUDITOR"]))
):
    """
    Retrieve macro overview across all connected pilot pharmacies, onboarding velocity,
    and agent operational load.
    """
    return pilot_manager.get_pilot_overview(db)


@router.get("/pharmacies/{pharmacy_id}")
def get_pharmacy_pilot_status_endpoint(
    pharmacy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Inspect a single pharmacy's pilot onboarding status, data quality scores, and agent metrics.
    """
    if current_user.role not in ["OWNER", "AUDITOR"] and current_user.pharmacy_id != pharmacy_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot access other pharmacy pilot data."
        )
    result = pilot_manager.get_pharmacy_pilot_status(pharmacy_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.post("/validate-scenarios")
def run_pilot_validation_scenarios_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["OWNER", "AUDITOR"]))
):
    """
    Execute real-world validation framework running all 4 pilot simulation scenarios:
    1. Stock Shortage Detection & DRAFT PO Staging
    2. Supplier Delays & Reliability Score Decay
    3. Seasonal Demand Changes & Forecasting Multiplier Integration
    4. Pharmacist Feedback Learning & Episodic Memory Adaptation
    """
    return pilot_scenario_runner.run_all_scenarios(db)
