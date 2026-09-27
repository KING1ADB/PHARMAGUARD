from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    pharmacy_id: str
    pharmacy_name: str
    city: str = "Douala"
    country: str = "Cameroon"
    current_time: datetime = Field(default_factory=datetime.utcnow)


class AgentState(BaseModel):
    cycle_id: str
    phase: str = "INITIALIZED"  # OBSERVE, ANALYZE, PLAN, ACT, LEARN, COMPLETED
    context: AgentContext
    observations: Dict[str, Any] = Field(default_factory=dict)
    analysis: Dict[str, Any] = Field(default_factory=dict)
    plans: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    human_approvals_pending: List[Dict[str, Any]] = Field(default_factory=list)
    learnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
