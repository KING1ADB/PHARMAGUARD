import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import require_roles, get_current_user
from ...database.models.entities import User
from ...services.simulation.pilot_30day_simulator import pilot_30day_simulator

logger = logging.getLogger("PharmaGuard.SimulationRouter")
router = APIRouter(prefix="/simulation", tags=["Real Pilot Simulation Framework"])


class SimulationRequest(BaseModel):
    pharmacy_name: Optional[str] = "Simulated Pilot Pharmacy"
    seed: Optional[int] = 42


@router.post("/30-day")
def run_30_day_simulation_endpoint(
    req: SimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["OWNER", "AUDITOR", "PHARMACIST"]))
):
    """
    Executes a continuous 30-day operational simulation measuring:
    - Daily inventory movements & sales surges
    - Supplier delays vs on-time deliveries
    - Pharmacist decision iterations
    - Day-by-day evolution of Trust Index, Forecast Accuracy, Alert Precision, and Acceptance Rate.
    """
    result = pilot_30day_simulator.run_30_day_simulation(
        db=db,
        pharmacy_name=req.pharmacy_name or "Simulated Pilot Pharmacy",
        seed=req.seed or 42
    )
    return result
