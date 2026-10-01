import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user
from ...database.models.entities import User
from ...services.interaction.agent_interaction_service import agent_interaction_service

logger = logging.getLogger("PharmaGuard.InteractionRouter")
router = APIRouter(prefix="/interaction", tags=["Natural AI Interaction Interface"])


class PharmacistQueryRequest(BaseModel):
    query: str
    pharmacy_id: Optional[str] = None


@router.post("/query")
def process_pharmacist_query_endpoint(
    req: PharmacistQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Processes natural language questions from pharmacists:
    - 'Why did you generate this alert?'
    - 'Explain this recommendation.'
    - 'Prepare a purchase action for 50 boxes of Coartem.'
    - 'Show pharmacy performance.'
    
    Executes real agent tools, queries database catalogs, and leverages memory.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query text cannot be empty.")

    target_pharm_id = req.pharmacy_id or current_user.pharmacy_id
    user_name = getattr(current_user, "full_name", "Pharmacist") or getattr(current_user, "name", "Pharmacist")

    result = agent_interaction_service.process_pharmacist_query(
        query=req.query,
        pharmacy_id=target_pharm_id,
        db=db,
        user_name=user_name
    )
    return result
