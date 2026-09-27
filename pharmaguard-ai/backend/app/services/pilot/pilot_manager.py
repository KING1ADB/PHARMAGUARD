from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import (
    Pharmacy,
    Inventory,
    Medicine,
    User,
    PurchaseOrder,
    Alert,
    AgentActionLog
)


class PilotManagementSystem:
    """
    PharmaGuard Production Pilot Management System (Phase 5).
    
    Tracks connected pilot pharmacies, onboarding velocity, data quality scores,
    and live agent operational volume.
    """
    def __init__(self):
        pass

    def get_pilot_overview(self, db: Session) -> Dict[str, Any]:
        """
        Retrieves macro overview across all participating pilot pharmacies.
        """
        pharmacies = db.query(Pharmacy).all()
        total_pharmacies = len(pharmacies)

        active_pilots = sum(1 for p in pharmacies if p.onboarding_status == "PILOT_ACTIVE")
        in_onboarding = total_pharmacies - active_pilots

        total_skus = db.query(Inventory).count()
        total_pos = db.query(PurchaseOrder).count()
        total_alerts = db.query(Alert).count()

        pharmacies_summary = []
        for p in pharmacies:
            pharmacies_summary.append(self.get_pharmacy_pilot_status(p.id, db))

        return {
            "status": "SUCCESS",
            "total_connected_pharmacies": total_pharmacies,
            "active_pilots_count": active_pilots,
            "onboarding_in_progress_count": in_onboarding,
            "total_skus_under_management": total_skus,
            "total_purchase_orders_staged": total_pos,
            "total_alerts_generated": total_alerts,
            "pharmacies": pharmacies_summary
        }

    def get_pharmacy_pilot_status(self, pharmacy_id: str, db: Session) -> Dict[str, Any]:
        """
        Deep-dive into a single pharmacy's pilot health, data quality, and agent activity.
        """
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        if not pharmacy:
            return {"status": "ERROR", "message": f"Pharmacy {pharmacy_id} not found."}

        # 1. Staff & Users
        users = db.query(User).filter(User.pharmacy_id == pharmacy_id).all()

        # 2. Inventory & Data Quality Evaluation
        inv_items = db.query(Inventory).filter(Inventory.pharmacy_id == pharmacy_id).all()
        total_items = len(inv_items)

        if total_items > 0:
            items_with_cost = sum(1 for i in inv_items if (i.unit_cost_fcfa or 0) > 0)
            items_with_expiry = sum(1 for i in inv_items if i.expiry_date is not None)
            items_with_batch = sum(1 for i in inv_items if i.batch_number and i.batch_number != "BATCH-DEFAULT")

            cost_completeness = round((items_with_cost / total_items) * 100, 1)
            expiry_completeness = round((items_with_expiry / total_items) * 100, 1)
            batch_completeness = round((items_with_batch / total_items) * 100, 1)

            # Overall Data Quality Score (0 - 100%)
            data_quality_score = round(
                (0.40 * cost_completeness) + (0.40 * expiry_completeness) + (0.20 * batch_completeness),
                1
            )
        else:
            cost_completeness = 0.0
            expiry_completeness = 0.0
            batch_completeness = 0.0
            data_quality_score = 0.0

        # 3. Agent Operational Activity
        po_count = db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == pharmacy_id).count()
        alerts_count = db.query(Alert).filter(Alert.pharmacy_id == pharmacy_id).count()
        action_count = db.query(AgentActionLog).filter(AgentActionLog.pharmacy_id == pharmacy_id).count()

        return {
            "pharmacy_id": pharmacy.id,
            "organization_name": pharmacy.organization_name,
            "location": pharmacy.location,
            "pilot_tier": pharmacy.pilot_tier,
            "onboarding_status": pharmacy.onboarding_status,
            "agent_active": pharmacy.agent_active,
            "preferred_run_time": pharmacy.preferred_morning_run_time or "07:30",
            "staff_count": len(users),
            "data_quality": {
                "total_active_skus": total_items,
                "overall_data_quality_score": f"{data_quality_score}%",
                "cost_completeness_pct": f"{cost_completeness}%",
                "expiry_completeness_pct": f"{expiry_completeness}%",
                "batch_completeness_pct": f"{batch_completeness}%",
                "data_health": "EXCELLENT" if data_quality_score >= 85 else ("GOOD" if data_quality_score >= 60 else "NEEDS_ATTENTION")
            },
            "agent_activity": {
                "total_purchase_orders_created": po_count,
                "total_alerts_generated": alerts_count,
                "total_autonomous_actions_logged": action_count
            }
        }


# Singleton pilot manager
pilot_manager = PilotManagementSystem()
