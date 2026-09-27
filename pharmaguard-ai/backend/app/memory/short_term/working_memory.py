from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class WorkingMemory:
    """
    Tier 1: Working Memory for active execution sessions.
    Stores task goals, tool outputs, and scratchpad reasoning steps.
    """
    def __init__(self, max_entries: int = 50):
        self.max_entries = max_entries
        self._entries: List[Dict[str, Any]] = []

    def log_step(self, step_name: str, data: Dict[str, Any]):
        entry = {
            "step": step_name,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            self._entries.pop(0)

    def get_context(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def clear(self):
        self._entries.clear()


session_working_memory = WorkingMemory()
