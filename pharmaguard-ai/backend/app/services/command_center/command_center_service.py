import json
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import (
    Pharmacy,
    Inventory,
    Medicine,
    Supplier,
    PurchaseOrder,
    Alert,
    AgentActionLog,
    AgentMemory
)
from ...agents.orchestrator.morning_orchestrator import multi_agent_orchestrator
from ...evaluation.agent_evaluator import agent_evaluator


class PharmacistCommandCenterService:
    """
    Pharmacist AI Command Center Service (Phase 6).
    
    Provides the primary executive interface for pharmacists:
    1. Morning Intelligence Briefing
    2. Active Prioritized Alerts
    3. Staged AI Actions & Pending Approval Queue
    4. Transparent Step-by-Step Chain-of-Thought Reasoning Explanations
    """
    def __init__(self):
        pass

    def get_command_center_summary(self, pharmacy_id: str, db: Session) -> Dict[str, Any]:
        """
        Aggregates the unified Command Center dashboard payload for a pharmacy.
        """
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        if not pharmacy:
            return {"status": "ERROR", "message": f"Pharmacy {pharmacy_id} not found."}

        # 1. Latest Morning Intelligence Briefing
        latest_cycle_log = db.query(AgentActionLog).filter(
            AgentActionLog.pharmacy_id == pharmacy_id,
            AgentActionLog.action.like("%MORNING_CYCLE%")
        ).order_by(AgentActionLog.timestamp.desc()).first()

        latest_cycle_summary = {}
        if latest_cycle_log and latest_cycle_log.details:
            try:
                latest_cycle_summary = json.loads(latest_cycle_log.details)
            except Exception:
                latest_cycle_summary = {"raw_details": latest_cycle_log.details}

        # 2. Active Prioritized Alerts
        active_alerts = db.query(Alert).filter(
            Alert.pharmacy_id == pharmacy_id,
            Alert.status == "ACTIVE"
        ).order_by(
            Alert.severity.desc(),
            Alert.created_at.desc()
        ).all()

        alerts_list = []
        for a in active_alerts:
            med = db.query(Medicine).filter(Medicine.id == a.medicine_id).first() if a.medicine_id else None
            alerts_list.append({
                "alert_id": a.id,
                "severity": a.severity,
                "alert_type": a.alert_type,
                "medicine_id": a.medicine_id,
                "medicine_name": med.brand_names if med else (a.medicine_id or "General"),
                "generic_name": med.generic_name if med else "N/A",
                "message": a.message,
                "recommended_action": a.recommended_action,
                "created_at": a.created_at.isoformat() if a.created_at else None
            })

        # 3. Pending AI Actions / Purchase Orders in Approval Queue
        pending_pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.pharmacy_id == pharmacy_id,
            PurchaseOrder.status == "DRAFT"
        ).order_by(PurchaseOrder.created_at.desc()).all()

        approval_queue = []
        for po in pending_pos:
            sup = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
            items = []
            if po.items_json:
                try:
                    items = json.loads(po.items_json)
                except Exception:
                    items = []
            
            approval_queue.append({
                "po_id": po.id,
                "supplier_id": po.supplier_id,
                "supplier_name": sup.name if sup else (po.supplier_id or "Recommended Supplier"),
                "supplier_reliability": f"{int((sup.reliability_score or 0.90) * 100)}%" if sup else "90%",
                "total_amount_fcfa": po.total_amount_fcfa,
                "items_count": len(items),
                "items": items,
                "notes": po.notes,
                "created_at": po.created_at.isoformat() if po.created_at else None
            })

        # 4. Performance & Trust Scorecard
        scorecard = agent_evaluator.generate_agent_scorecard(pharmacy_id, db)

        return {
            "status": "SUCCESS",
            "pharmacy_id": pharmacy_id,
            "organization_name": pharmacy.organization_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "briefing": {
                "last_run_at": latest_cycle_log.timestamp.isoformat() if latest_cycle_log else None,
                "executive_headline": f"Autonomous Operations Active — {len(active_alerts)} Alerts, {len(pending_pos)} Staged Purchase Actions",
                "cycle_details": latest_cycle_summary
            },
            "active_alerts_count": len(alerts_list),
            "active_alerts": alerts_list,
            "approval_queue_count": len(approval_queue),
            "approval_queue": approval_queue,
            "performance_overview": {
                "trust_index": scorecard.get("trust_index", "0.0%"),
                "forecast_accuracy": scorecard.get("metrics", {}).get("forecast_accuracy", {}).get("metric_value", "N/A"),
                "alert_precision": scorecard.get("metrics", {}).get("alert_precision", {}).get("metric_value", "N/A"),
                "procurement_acceptance_rate": scorecard.get("metrics", {}).get("procurement_acceptance_rate", {}).get("metric_value", "N/A")
            }
        }

    def explain_agent_reasoning(
        self,
        pharmacy_id: str,
        target_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Deep-dive reasoning explanation for a specific Alert ID, Purchase Order ID, or Medicine ID.
        Produces full chain-of-thought breakdown with observed inventory, forecasting equations,
        and supplier ranking rationale.
        """
        # Case 1: Target is an Alert ID
        alert = db.query(Alert).filter(Alert.id == target_id, Alert.pharmacy_id == pharmacy_id).first()
        if alert:
            med = db.query(Medicine).filter(Medicine.id == alert.medicine_id).first() if alert.medicine_id else None
            inv = db.query(Inventory).filter(Inventory.medicine_id == alert.medicine_id, Inventory.pharmacy_id == pharmacy_id).first() if alert.medicine_id else None
            
            return {
                "status": "SUCCESS",
                "target_type": "ALERT",
                "target_id": alert.id,
                "severity": alert.severity,
                "reasoning_chain": [
                    {
                        "step": "1. OBSERVED_INVENTORY_STATE",
                        "finding": f"Stock on hand: {inv.quantity if inv else 'N/A'} units. Expiry date: {inv.expiry_date if inv else 'N/A'}."
                    },
                    {
                        "step": "2. CLINICAL_AND_STORAGE_EVALUATION",
                        "finding": f"Medicine: {med.brand_names if med else 'Unknown'}. Storage: {med.storage_temperature if med else 'Room temp'}. Regulatory: {med.regulatory_schedule if med else 'Standard'}."
                    },
                    {
                        "step": "3. RISK_TRIGGER_CALCULATION",
                        "finding": f"Alert logic evaluated: {alert.alert_type}. Rationale: {alert.message}."
                    },
                    {
                        "step": "4. AGENT_RECOMMENDED_ACTION",
                        "finding": alert.recommended_action or "Review stock buffer and stage procurement replenishment."
                    }
                ]
            }

        # Case 2: Target is a Purchase Order ID
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == target_id, PurchaseOrder.pharmacy_id == pharmacy_id).first()
        if po:
            sup = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
            items = json.loads(po.items_json) if po.items_json else []
            
            return {
                "status": "SUCCESS",
                "target_type": "PURCHASE_ORDER",
                "target_id": po.id,
                "supplier_name": sup.name if sup else po.supplier_id,
                "total_amount_fcfa": po.total_amount_fcfa,
                "reasoning_chain": [
                    {
                        "step": "1. STOCKOUT_RUNOUT_PROJECTION",
                        "finding": f"Automated forecasting projected stockout risk for {len(items)} SKU(s) within the supplier lead time window."
                    },
                    {
                        "step": "2. ECONOMIC_ORDER_OPTIMIZATION",
                        "finding": f"Calculated reorder quantity to cover 30 days of projected demand plus safety buffer: {sum(item.get('quantity', 0) for item in items)} total units."
                    },
                    {
                        "step": "3. SUPPLIER_SELECTION_RATIONALE",
                        "finding": f"Selected {sup.name if sup else 'Primary Supplier'} (Reliability: {int((sup.reliability_score or 0.9) * 100)}%, Lead Time: {sup.delivery_time or 3} days) to minimize stockout risk."
                    },
                    {
                        "step": "4. HUMAN_IN_THE_LOOP_SAFEGUARD",
                        "finding": "Order held in DRAFT status awaiting licensed pharmacist authorization before dispatch."
                    }
                ]
            }

        # Case 3: Target is a Medicine ID
        med = db.query(Medicine).filter(Medicine.id == target_id).first()
        if med:
            inv = db.query(Inventory).filter(Inventory.medicine_id == med.id, Inventory.pharmacy_id == pharmacy_id).first()
            return {
                "status": "SUCCESS",
                "target_type": "MEDICINE_ANALYSIS",
                "medicine_id": med.id,
                "medicine_name": med.brand_names,
                "reasoning_chain": [
                    {
                        "step": "1. CURRENT_INVENTORY",
                        "finding": f"Current stock: {inv.quantity if inv else 0} units. Reorder point: {inv.reorder_level if inv else 10}."
                    },
                    {
                        "step": "2. REGULATORY_AND_STORAGE",
                        "finding": f"Category: {med.category}, Schedule: {med.regulatory_schedule}, Temperature: {med.storage_temperature}."
                    },
                    {
                        "step": "3. STATUS_VERDICT",
                        "finding": "Stock level is stable." if (inv and inv.quantity > (inv.reorder_level or 10)) else "Stock is low or approaching reorder threshold."
                    }
                ]
            }

        return {
            "status": "ERROR",
            "message": f"Entity '{target_id}' not found in active alerts, purchase orders, or medicine catalog."
        }


# Singleton service instance
command_center_service = PharmacistCommandCenterService()
