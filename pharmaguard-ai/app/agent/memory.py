from typing import Dict, List, Any, Optional
from datetime import datetime


class AgentMemory:
    """
    Working and episodic memory store for PharmaGuard AI.
    Retains conversational turns, recent decision cycles, and pharmacist feedback patterns.
    """
    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self._conversation_history: List[Dict[str, Any]] = []
        self._cycle_history: List[Dict[str, Any]] = []
        self._pharmacist_preferences: Dict[str, Any] = {
            "preferred_suppliers": ["SUP-001", "SUP-002"],
            "auto_discount_short_dated": True,
            "stockout_alert_urgency_days": 3
        }

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Records a user or agent interaction."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }
        self._conversation_history.append(entry)
        if len(self._conversation_history) > self.max_history:
            self._conversation_history.pop(0)

    def record_cycle(self, cycle_data: Dict[str, Any]):
        """Records a completed autonomous decision cycle."""
        self._cycle_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            **cycle_data
        })
        if len(self._cycle_history) > 20:
            self._cycle_history.pop(0)

    def get_recent_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent conversation history."""
        return self._conversation_history[-limit:]

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._pharmacist_preferences.get(key, default)

    def update_preference(self, key: str, value: Any):
        self._pharmacist_preferences[key] = value

    def clear(self):
        self._conversation_history.clear()
        self._cycle_history.clear()


# Global in-process memory singleton
global_memory = AgentMemory()
