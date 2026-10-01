import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user
from ...database.models.entities import User
from ...services.command_center.command_center_service import command_center_service

logger = logging.getLogger("PharmaGuard.CommandCenterRouter")
router = APIRouter(prefix="/command-center", tags=["Pharmacist AI Command Center"])


@router.get("/summary")
def get_command_center_summary_endpoint(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the unified Pharmacist AI Command Center payload:
    - Morning intelligence briefing
    - Active prioritized alerts
    - Pending AI actions & approval queue
    - Performance & Trust metrics
    """
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = command_center_service.get_command_center_summary(target_pharm_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.get("/reasoning/{target_id}")
def explain_reasoning_endpoint(
    target_id: str,
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the step-by-step chain-of-thought reasoning explanation for an Alert ID,
    Purchase Order ID, or Medicine ID.
    """
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = command_center_service.explain_agent_reasoning(target_pharm_id, target_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result
