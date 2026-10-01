import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user
from ...database.models.entities import User
from ...services.reports.pilot_reporting_service import pilot_reporting_service

logger = logging.getLogger("PharmaGuard.PilotReportingRouter")
router = APIRouter(prefix="/reports", tags=["Pilot Reporting System"])


@router.get("/performance")
def get_pharmacy_performance_report_endpoint(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates pharmacy inventory and stock health performance report."""
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = pilot_reporting_service.generate_pharmacy_performance_report(target_pharm_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.get("/ai-effectiveness")
def get_ai_effectiveness_report_endpoint(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates AI agent accuracy, precision, and operational effectiveness report."""
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = pilot_reporting_service.generate_ai_effectiveness_report(target_pharm_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.get("/trust-evolution")
def get_trust_evolution_report_endpoint(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates Trust Index historical evolution report."""
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = pilot_reporting_service.generate_trust_index_evolution_report(target_pharm_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result


@router.get("/deployment-summary")
def get_deployment_summary_report_endpoint(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generates comprehensive pilot deployment executive briefing."""
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = pilot_reporting_service.generate_pilot_deployment_summary(target_pharm_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result
