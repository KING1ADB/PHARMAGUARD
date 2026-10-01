import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user
from ...database.models.entities import User
from ...services.evidence.evidence_package_service import competition_evidence_service
from ...monitoring.deployment_readiness_checker import deployment_readiness_checker

logger = logging.getLogger("PharmaGuard.EvidenceRouter")
router = APIRouter(prefix="/evidence", tags=["Competition Evidence & Deployment Readiness"])


@router.get("/package")
def get_competition_evidence_package_endpoint(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the comprehensive Competition Evidence Package:
    - 5-Minute Live Demonstration Workflow
    - Judge Stress Scenario Details
    - Quantified Impact Benchmarks
    - Technical Architecture Summary
    - Clinical & Operational Safety Explanations
    - Real-time Pilot Impact Metrics
    """
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    return competition_evidence_service.get_evidence_package(target_pharm_id, db)


@router.get("/preflight-checks/{pharmacy_id}")
def run_preflight_checks_endpoint(
    pharmacy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Runs automated pre-flight production deployment validation across:
    1. Onboarding readiness
    2. Security & RBAC
    3. Data Quality Score
    4. Agent reliability & safety
    """
    result = deployment_readiness_checker.run_preflight_checks(pharmacy_id, db)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result
