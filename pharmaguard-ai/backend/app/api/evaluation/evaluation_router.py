from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from ...database.database import get_db
from ...database.models.entities import User, Pharmacy
from ...security.jwt_rbac import get_current_active_user, require_role, UserRole
from ...evaluation.agent_evaluator import agent_evaluator

router = APIRouter(prefix="/evaluation", tags=["Agent Evaluation & Trust Framework"])


@router.get("/scorecard", summary="Get Composite Agent Trust & Reliability Scorecard")
def get_agent_scorecard(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Returns the comprehensive production scorecard:
    - Composite Trust Index (0 - 100%)
    - Forecast accuracy (MAE/RMSE)
    - Procurement success & approval rate
    - Alert precision score
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    if not target_pharmacy_id:
        p = db.query(Pharmacy).first()
        target_pharmacy_id = p.id if p else "PHARM-DLA-001"

    return agent_evaluator.generate_agent_scorecard(target_pharmacy_id, db)


@router.get("/forecast-accuracy", summary="Get Demand Forecast Accuracy Metrics (MAE, RMSE, MAPE)")
def get_forecast_accuracy(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Evaluates forecast accuracy against actual observed sales."""
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    return agent_evaluator.evaluate_forecast_accuracy(target_pharmacy_id, db)


@router.get("/procurement-success", summary="Get Procurement Recommendation Acceptance Metrics")
def get_procurement_success(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Measures human approval and modification rates for staged orders."""
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    return agent_evaluator.evaluate_procurement_success_rate(target_pharmacy_id, db)


@router.get("/alert-precision", summary="Get Operational Alert Precision & False Alert Rate")
def get_alert_precision(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Measures alert precision and false alert rate."""
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    return agent_evaluator.evaluate_alert_precision(target_pharmacy_id, db)
