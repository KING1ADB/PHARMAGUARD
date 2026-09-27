from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..tools.notification_tools import generate_daily_report, send_notification
from ..tools.medicine_tools import search_medicine_catalog, get_generic_substitutes


class CommunicationAgent:
    """
    Sub-Agent: Multi-Channel Communication & Patient Coordinator.
    Formats executive briefings for pharmacists and provides verified medicine locator
    and generic molecule matching for patients.
    """
    def __init__(self, agent_name: str = "CommunicationAgent"):
        self.agent_name = agent_name

    def format_daily_briefing(self, db: Session, pharmacy_id: str) -> Dict[str, Any]:
        """
        Generates and formats the daily operational briefing.
        """
        report = generate_daily_report(pharmacy_id, db)
        return {
            "agent": self.agent_name,
            "status": "COMPLETED",
            "report_markdown": report["report_markdown"],
            "critical_alerts_count": report["critical_alerts_count"],
            "recommendations": report["recommendations"]
        }

    def handle_patient_inquiry(self, db: Session, requested_medicine: str) -> Dict[str, Any]:
        """
        Assists a patient in finding a medicine and resolving generic equivalents safely.
        """
        matches = search_medicine_catalog(db, requested_medicine)
        
        if not matches:
            return {
                "agent": self.agent_name,
                "found": False,
                "message": (
                    f"No exact match found for '{requested_medicine}'. "
                    "Please consult a licensed pharmacist for proper prescription verification."
                )
            }

        primary = matches[0]
        substitutes = get_generic_substitutes(db, primary["generic_name"])

        return {
            "agent": self.agent_name,
            "found": True,
            "medicine_name": primary["name"],
            "generic_molecule": primary["generic_name"],
            "dosage_form": primary["form"],
            "strength": primary["strength"],
            "substitute_options": [s["name"] for s in substitutes if s["name"] != primary["name"]],
            "safety_disclaimer": "Always consult your doctor or dispensing pharmacist before switching medications."
        }
