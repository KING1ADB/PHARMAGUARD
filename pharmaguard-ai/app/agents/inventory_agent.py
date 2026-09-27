import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..database.models import Alert, AgentAction, Inventory, Medicine, Supplier
from ..tools.inventory_tools import get_inventory
from ..tools.risk_tools import calculate_stock_risk, calculate_expiry_risks


class InventoryAgent:
    """
    PharmaGuard Inventory Intelligence Agent.
    
    Purpose:
    Monitor pharmacy inventory, evaluate stock coverage vs supplier lead times,
    detect critical shortage risks, generate reasoning with confidence scores,
    and maintain auditable records in AgentAction.
    """
    def __init__(self, agent_name: str = "InventoryIntelligenceAgent"):
        self.agent_name = agent_name

    def evaluate(self, db: Session, pharmacy_id: str) -> Dict[str, Any]:
        """
        Executes the inventory intelligence workflow:
        1. Read inventory
        2. Analyze stock levels & sales velocity
        3. Calculate stock coverage
        4. Compare supplier delivery time
        5. Detect shortage risk
        6. Explain reasoning
        7. Generate recommendations
        8. Record auditable decision in AgentAction
        """
        # Step 1: Read inventory
        inventory_items = get_inventory(pharmacy_id, db)
        
        # Step 2-5: Evaluate risks across all items
        evaluated_risks = []
        high_risk_items = []
        
        for item in inventory_items:
            risk_info = calculate_stock_risk(item["medicine_id"], db, pharmacy_id)
            evaluated_risks.append(risk_info)
            if risk_info.get("risk_level") in ["HIGH", "CRITICAL_STOCKOUT"]:
                high_risk_items.append(risk_info)

        # Evaluate Expiry Risks
        expiry_info = calculate_expiry_risks(pharmacy_id, db)

        # Step 6 & 7: Explain reasoning & generate recommendations
        recommendations = []
        for r in high_risk_items:
            recommendations.append({
                "medicine_id": r["medicine_id"],
                "medicine_name": r["name"],
                "risk_level": r["risk_level"],
                "confidence_score": r["confidence_score"],
                "reasoning": r["reasoning"],
                "action": r["recommendation"]
            })

        # Step 8: Persist auditable AgentAction logs & Alerts
        for rec in recommendations:
            # Audit log
            action_log = AgentAction(
                agent_name=self.agent_name,
                action_type="SHORTAGE_RISK_DETECTION",
                reasoning=rec["reasoning"],
                confidence_score=rec["confidence_score"],
                pharmacy_id=pharmacy_id
            )
            db.add(action_log)

            # Active alert
            alert_id = f"ALT-STK-{rec['medicine_id']}"
            existing_alert = db.query(Alert).filter(Alert.id == alert_id, Alert.status == "ACTIVE").first()
            if not existing_alert:
                alert = Alert(
                    id=alert_id,
                    pharmacy_id=pharmacy_id,
                    alert_type="STOCKOUT_RISK",
                    severity="HIGH",
                    medicine_id=rec["medicine_id"],
                    title=f"High Shortage Risk: {rec['medicine_name']}",
                    message=rec["reasoning"],
                    suggested_action=rec["action"],
                    confidence_score=rec["confidence_score"]
                )
                db.add(alert)

        db.commit()

        return {
            "agent": self.agent_name,
            "status": "COMPLETED",
            "total_skus_evaluated": len(inventory_items),
            "high_risk_count": len(high_risk_items),
            "evaluated_risks": evaluated_risks,
            "expiry_risks": expiry_info,
            "recommendations": recommendations
        }
