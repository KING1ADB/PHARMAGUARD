import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ...database.models.entities import AgentMemory, AgentActionLog


class EpisodicMemoryManager:
    """
    Tier 2: Operational Episodic Memory.
    Learns from pharmacist actions (approvals, rejections, manual adjustments)
    and persists operational knowledge in PostgreSQL `agent_memory`.
    """
    @staticmethod
    def record_decision_feedback(
        pharmacy_id: str,
        memory_type: str,
        feedback_data: Dict[str, Any],
        confidence: float,
        db: Session
    ) -> AgentMemory:
        """
        Stores learned behavior (e.g. 'Pharmacist approved PO-2026-SUP001', 'Pharmacist reduced Insulin order by 5 units').
        """
        memory_id = f"MEM-{uuid.uuid4().hex[:8].upper()}"
        mem = AgentMemory(
            id=memory_id,
            pharmacy_id=pharmacy_id,
            memory_type=memory_type,
            information=json.dumps(feedback_data),
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(mem)
        db.commit()
        db.refresh(mem)
        return mem

    @staticmethod
    def get_learned_preferences(pharmacy_id: str, db: Session) -> Dict[str, Any]:
        """
        Retrieves all active learned operational preferences for a pharmacy.
        """
        records = (
            db.query(AgentMemory)
            .filter(AgentMemory.pharmacy_id == pharmacy_id)
            .order_by(AgentMemory.timestamp.desc())
            .limit(20)
            .all()
        )

        preferences = {
            "preferred_suppliers": ["SUP-001", "SUP-002"],
            "safety_stock_buffer_days": 2,
            "auto_discount_approval_rate": 0.85,
            "recent_feedback": []
        }

        for r in records:
            try:
                info = json.loads(r.information)
                preferences["recent_feedback"].append({
                    "type": r.memory_type,
                    "confidence": r.confidence,
                    "timestamp": r.timestamp.isoformat(),
                    "info": info
                })
            except Exception:
                continue

        return preferences
