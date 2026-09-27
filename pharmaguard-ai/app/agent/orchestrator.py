import os
import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from .state import AgentState, AgentContext
from .prompts import SYSTEM_ORCHESTRATOR_PROMPT, INVENTORY_AGENT_PROMPT
from .memory import global_memory
from ..agents.inventory_agent import InventoryAgent
from ..agents.forecasting_agent import ForecastingAgent
from ..agents.procurement_agent import ProcurementAgent
from ..agents.communication_agent import CommunicationAgent
from ..tools.inventory_tools import get_inventory, query_stock_level
from ..tools.risk_tools import calculate_stock_risk, calculate_all_inventory_risks, calculate_expiry_risks
from ..tools.notification_tools import generate_daily_report
from ..database.models import Pharmacy, PurchaseOrder, AgentAction, Alert, Inventory, Medicine, Supplier


class MasterOrchestrator:
    """
    PharmaGuard AI Master Orchestrator.
    Executes the autonomous cycle:
    Observe → Analyze → Reason → Recommend → Request Approval → Act → Learn.
    """
    def __init__(self):
        self.inventory_agent = InventoryAgent()
        self.forecasting_agent = ForecastingAgent()
        self.procurement_agent = ProcurementAgent()
        self.communication_agent = CommunicationAgent()

    def run_autonomous_cycle(self, db: Session, pharmacy_id: str = "PHARM-DLA-001") -> Dict[str, Any]:
        """
        Executes a complete 5-stage autonomous pharmacy intelligence cycle.
        """
        cycle_id = f"CYCLE-{uuid.uuid4().hex[:8].upper()}"
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        pharmacy_name = pharmacy.name if pharmacy else "Community Pharmacy"

        context = AgentContext(
            pharmacy_id=pharmacy_id,
            pharmacy_name=pharmacy_name,
            current_time=datetime.now(timezone.utc)
        )

        state = AgentState(cycle_id=cycle_id, phase="OBSERVE", context=context)

        # -----------------------------------------------------------
        # Stage 1: OBSERVE
        # -----------------------------------------------------------
        inv_eval = self.inventory_agent.evaluate(db, pharmacy_id)
        state.observations = {
            "total_skus": inv_eval["total_skus_evaluated"],
            "high_risk_count": inv_eval["high_risk_count"]
        }
        self._log_action(db, pharmacy_id, "OBSERVE", f"Observed {inv_eval['total_skus_evaluated']} inventory SKUs.", 0.95)

        # -----------------------------------------------------------
        # Stage 2: ANALYZE & REASON
        # -----------------------------------------------------------
        state.phase = "ANALYZE"
        forecast_eval = self.forecasting_agent.evaluate(db, pharmacy_id, horizon_days=21)
        state.analysis = {
            "forecast_horizon_days": 21,
            "urgent_reorders_needed": forecast_eval["urgent_reorders_count"],
            "capital_at_expiry_risk_fcfa": inv_eval["expiry_risks"]["capital_at_risk_fcfa"]
        }
        self._log_action(db, pharmacy_id, "ANALYZE", f"Analyzed run rates. Identified {forecast_eval['urgent_reorders_count']} urgent reorders.", 0.92)

        # -----------------------------------------------------------
        # Stage 3: PLAN & RECOMMEND
        # -----------------------------------------------------------
        state.phase = "PLAN"
        procurement_eval = self.procurement_agent.plan_procurement(
            db, pharmacy_id, forecast_eval["recommended_reorders"]
        )
        state.plans = {
            "draft_purchase_orders": procurement_eval["draft_orders"]
        }
        state.human_approvals_pending = procurement_eval["draft_orders"]
        self._log_action(db, pharmacy_id, "RECOMMEND", f"Prepared {len(procurement_eval['draft_orders'])} draft purchase orders requiring approval.", 0.90)

        # -----------------------------------------------------------
        # Stage 4: ACT (With Human Oversight)
        # -----------------------------------------------------------
        state.phase = "ACT"
        report_data = generate_daily_report(pharmacy_id, db)
        state.actions = [
            {"type": "DAILY_REPORT_GENERATED", "alerts_count": report_data["critical_alerts_count"]},
            {"type": "DRAFT_ORDERS_PREPARED", "count": len(procurement_eval["draft_orders"])}
        ]
        self._log_action(db, pharmacy_id, "ACT", "Compiled operational intelligence report and synchronized alerts.", 0.95)

        # -----------------------------------------------------------
        # Stage 5: LEARN
        # -----------------------------------------------------------
        state.phase = "LEARN"
        learning_note = (
            f"Cycle {cycle_id} complete. Evaluated {inv_eval['total_skus_evaluated']} items. "
            f"Flagged {inv_eval['high_risk_count']} shortage risks and {len(inv_eval['expiry_risks']['critical_30_days'])} critical expiries."
        )
        state.learnings.append(learning_note)
        global_memory.record_cycle({
            "cycle_id": cycle_id,
            "pharmacy_id": pharmacy_id,
            "high_risk_count": inv_eval["high_risk_count"]
        })
        self._log_action(db, pharmacy_id, "LEARN", learning_note, 0.95)

        state.phase = "COMPLETED"
        state.completed_at = datetime.now(timezone.utc)

        return {
            "cycle_id": cycle_id,
            "pharmacy_id": pharmacy_id,
            "timestamp": state.completed_at,
            "phase_results": {
                "observations": state.observations,
                "analysis": state.analysis,
                "plans": state.plans,
                "actions": state.actions,
                "learnings": state.learnings
            },
            "active_alerts_count": inv_eval["high_risk_count"],
            "recommended_orders": procurement_eval["draft_orders"],
            "briefing_text": report_data["report_markdown"]
        }

    def handle_user_query(self, db: Session, pharmacy_id: str, query: str, channel: str = "web") -> Dict[str, Any]:
        """
        Processes natural language requests such as 'Analyze this pharmacy' or specific product queries.
        """
        q = query.lower().strip()
        global_memory.add_message("user", query, {"channel": channel})

        # 1. Comprehensive Pharmacy Analysis Workflow ("Analyze this pharmacy")
        if "analyze" in q and ("pharmacy" in q or "all" in q or "everything" in q or "operations" in q):
            cycle_result = self.run_autonomous_cycle(db, pharmacy_id)
            report = generate_daily_report(pharmacy_id, db)
            
            resp_lines = [
                f"📊 **PharmaGuard Autonomous Analysis for {report['pharmacy_name']}**\n",
                f"I have observed **{len(get_inventory(pharmacy_id, db))} medicines**, analyzed sales velocities, and compared supplier delivery lead times.\n"
            ]

            if report["critical_alerts"]:
                resp_lines.append(f"🚨 **Detected {len(report['critical_alerts'])} High Shortage Risks:**")
                for a in report["critical_alerts"]:
                    resp_lines.append(f"• **{a['title']}** (Confidence: {a['confidence']})\n  _{a['reasoning']}_")
                resp_lines.append("")

            resp_lines.append(f"⏳ **Capital at Expiry Risk (<60d):** {report['capital_at_expiry_risk_fcfa']:,.0f} FCFA\n")
            resp_lines.append("📋 **Key Recommendations:**")
            for rec in report["recommendations"]:
                resp_lines.append(f"• {rec}")

            full_resp = "\n".join(resp_lines)
            global_memory.add_message("agent", full_resp)
            return {
                "response": full_resp,
                "suggested_actions": ["Review Purchase Orders", "Authorize Draft Orders", "View Expiries"],
                "data": cycle_result
            }

        # 2. Specific Medicine Analysis (e.g. "Insulin", "Amoxicillin")
        meds = db.query(Medicine).all()
        target_med = None
        for m in meds:
            if m.name.lower() in q or m.generic_name.lower() in q or (len(m.name.split()) > 0 and m.name.split()[0].lower() in q):
                target_med = m
                break

        if target_med:
            risk = calculate_stock_risk(target_med.id, db, pharmacy_id)
            if risk.get("status") != "ERROR":
                resp = (
                    f"{risk['name']} has a {risk['risk_level'].lower()} shortage risk because "
                    f"current inventory covers approximately {int(risk['stock_coverage_days']) if risk['stock_coverage_days'].is_integer() else risk['stock_coverage_days']} days "
                    f"while supplier delivery requires {risk['supplier_delivery_days']} days. "
                    f"I recommend {risk['recommendation'].lower()}"
                )
                confidence_pct = int(risk["confidence_score"] * 100)
                full_resp = f"{resp}\n\n**Confidence:** {confidence_pct}%"
                global_memory.add_message("agent", full_resp)
                return {
                    "response": full_resp,
                    "suggested_actions": [f"Draft PO for {risk['name']}", "View Alternative Suppliers"],
                    "data": risk
                }

        # 3. Expiry query
        if any(w in q for w in ["expiry", "expire", "expiring", "dead stock"]):
            risks = calculate_expiry_risks(pharmacy_id, db)
            lines = [f"⏳ **Expiry Analysis (Capital at Risk: {risks['capital_at_risk_fcfa']:,.0f} FCFA):**\n"]
            if risks["critical_30_days"]:
                lines.append("**Critical (<30 Days):**")
                for it in risks["critical_30_days"]:
                    lines.append(f"• {it['name']} — `{it['quantity']} units` (Exp: {it['expiry_date']}) → *{it['action_recommendation']}*")
            if risks["warning_60_days"]:
                lines.append("\n**Warning (<60 Days):**")
                for it in risks["warning_60_days"]:
                    lines.append(f"• {it['name']} — `{it['quantity']} units` (Exp: {it['expiry_date']}) → *{it['action_recommendation']}*")
            resp = "\n".join(lines)
            global_memory.add_message("agent", resp)
            return {
                "response": resp,
                "suggested_actions": ["Apply 30% FEFO Promotion", "Notify Dispensing Team"],
                "data": risks
            }

        # 4. Default Search
        matches = query_stock_level(db, q, pharmacy_id)
        if matches:
            lines = [f"🔍 **Found {len(matches)} matching product(s):**\n"]
            for m in matches:
                lines.append(
                    f"• **{m['name']}** ({m['generic_name']})\n"
                    f"  - Quantity: `{m['quantity']} units` | Shelf: `{m['location_shelf']}`\n"
                    f"  - Price: `{m['selling_price_fcfa']:,.0f} FCFA` | Cost: `{m['unit_cost_fcfa']:,.0f} FCFA`\n"
                    f"  - Expiry: `{m['expiry_date']}`"
                )
            resp = "\n".join(lines)
        else:
            resp = f"ℹ️ No medicines found matching '{query}'. Please specify the brand or generic name."

        global_memory.add_message("agent", resp)
        return {
            "response": resp,
            "suggested_actions": ["Analyze this pharmacy", "View All Inventory"],
            "data": {"matches": matches}
        }

    def approve_purchase_order(self, db: Session, po_id: str) -> Dict[str, Any]:
        """
        Human-in-the-Loop Approval: Pharmacist authorizes a draft purchase order.
        """
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if not po:
            return {"status": "ERROR", "message": f"Purchase order {po_id} not found."}

        po.status = "APPROVED"
        po.approved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(po)

        self._log_action(db, po.pharmacy_id, "AUTHORIZE_PURCHASE_ORDER", f"Pharmacist authorized PO {po.id} for {po.total_amount_fcfa:,.0f} FCFA.", 1.0)

        return {
            "status": "SUCCESS",
            "po_id": po.id,
            "new_status": po.status,
            "approved_at": po.approved_at.isoformat(),
            "supplier_id": po.supplier_id,
            "total_amount_fcfa": po.total_amount_fcfa
        }

    def _log_action(self, db: Session, pharmacy_id: str, action_type: str, reasoning: str, confidence: float):
        """Records an auditable AgentAction record in PostgreSQL."""
        action = AgentAction(
            agent_name="MasterOrchestrator",
            action_type=action_type,
            reasoning=reasoning,
            confidence_score=confidence,
            pharmacy_id=pharmacy_id,
            timestamp=datetime.now(timezone.utc)
        )
        db.add(action)
        db.commit()


orchestrator = MasterOrchestrator()
