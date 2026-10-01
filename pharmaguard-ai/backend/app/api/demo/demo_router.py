import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user, require_roles
from ...database.models.entities import User
from ...services.demo.competition_demo_service import competition_demo_service

logger = logging.getLogger("PharmaGuard.DemoRouter")
router = APIRouter(prefix="/demo", tags=["Competition Demonstration Mode"])


@router.post("/competition-run")
def run_competition_demonstration_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Executes the live Competition Demonstration showcasing real production multi-agent capabilities:
    1. Autonomous Morning Cycle Trigger
    2. Multi-Agent Risk Detection (Cold-chain stockout & seasonal surges)
    3. Explainable Chain-of-Thought Reasoning Generation
    4. Human-in-the-Loop Review & One-Click Decision Execution
    5. Real-Time Memory Update & Agent Learning
    """
    result = competition_demo_service.run_live_competition_demo(db)
    return result
