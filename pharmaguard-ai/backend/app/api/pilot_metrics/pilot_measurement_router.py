import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user
from ...database.models.entities import User
from ...services.pilot_metrics.pilot_measurement_service import pilot_measurement_service

logger = logging.getLogger("PharmaGuard.PilotMeasurementRouter")
router = APIRouter(prefix="/pilot-metrics", tags=["Pilot Measurement System"])


@router.get("/impact")
def get_pilot_impact_metrics_endpoint(
    pharmacy_id: Optional[str] = None,
    duration_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns comparative Before/After operational impact metrics:
    - Stockout reduction rate (% decrease)
    - Expiry risk reduction (FCFA saved)
    - Procurement efficiency gain
    - Pharmacist weekly time savings
    - Overall financial ROI
    """
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    result = pilot_measurement_service.compute_pilot_impact_metrics(
        pharmacy_id=target_pharm_id,
        db=db,
        duration_days=duration_days
    )
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.get("message"))
    return result
