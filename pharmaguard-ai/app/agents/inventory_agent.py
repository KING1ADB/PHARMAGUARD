from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..services.analysis import analyze_inventory_health, get_medicine_risk_profile
from ..tools.risk_tools import calculate_expiry_risks
from ..database.models import Alert, Medicine
import uuid


class InventoryAgent:
    """
    Sub-Agent: Inventory & Expiry Health Specialist.
    Monitors stock velocities, expiry horizons, and flags critical inventory anomalies.
    """
    def __init__(self, agent_name: str = "InventoryHealthSpecialist"):
        self.agent_name = agent_name

    def evaluate(self, db: Session, pharmacy_id: str) -> Dict[str, Any]:
        """
        Executes an autonomous scan of the pharmacy's inventory health,
        generates structured risk metrics, and registers active database alerts.
        """
        health = analyze_inventory_health(db, pharmacy_id)
        expiry_risks = calculate_expiry_risks(db, pharmacy_id)

        # Generate or sync active database alerts for critical items
        generated_alerts = []
        for item in health["critical_stockout_items"]:
            alert_id = f"ALT-STK-{item['medicine_id']}"
            existing = db.query(Alert).filter(Alert.id == alert_id, Alert.status == "ACTIVE").first()
            if not existing:
                alert = Alert(
                    id=alert_id,
                    pharmacy_id=pharmacy_id,
                    alert_type="STOCKOUT_RISK",
                    severity=item["stockout_risk_level"],
                    medicine_id=item["medicine_id"],
                    title=f"Critical Stockout Threat: {item['name']}",
                    message=f"Only {item['quantity_in_stock']} units left. Estimated depletion in {item['days_of_stock_remaining']} days.",
                    suggested_action="Approve automated supplier replenishment PO."
                )
                db.add(alert)
                generated_alerts.append(alert)

        for item in expiry_risks["critical_30_days"] + expiry_risks["warning_60_days"]:
            alert_id = f"ALT-EXP-{item['medicine_id']}"
            existing = db.query(Alert).filter(Alert.id == alert_id, Alert.status == "ACTIVE").first()
            if not existing:
                alert = Alert(
                    id=alert_id,
                    pharmacy_id=pharmacy_id,
                    alert_type="EXPIRY_WARNING",
                    severity="HIGH" if item["expiry_status"] == "CRITICAL" else "MEDIUM",
                    medicine_id=item["medicine_id"],
                    title=f"Expiring Batch ({item['days_until_expiry']}d left): {item['name']}",
                    message=f"{item['quantity_in_stock']} units at risk (Exp: {item['expiry_date']}).",
                    suggested_action=item.get("action_recommendation", "Apply discount promotion.")
                )
                db.add(alert)
                generated_alerts.append(alert)

        db.commit()

        return {
            "agent": self.agent_name,
            "status": "COMPLETED",
            "health_summary": health,
            "expiry_risks": expiry_risks,
            "new_alerts_registered": len(generated_alerts)
        }
