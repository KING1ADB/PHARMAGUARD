import os
import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from .state import AgentState, AgentContext
from .prompts import SYSTEM_ORCHESTRATOR_PROMPT, PATIENT_COORDINATOR_PROMPT
from .memory import global_memory
from ..agents.inventory_agent import InventoryAgent
from ..agents.forecasting_agent import ForecastingAgent
from ..agents.procurement_agent import ProcurementAgent
from ..tools.inventory_tools import query_stock_level, list_low_stock_items, get_inventory_summary_stats
from ..tools.risk_tools import calculate_expiry_risks
from ..tools.report_tools import generate_daily_briefing_markdown, format_purchase_order_text
from ..database.models import Pharmacy, PurchaseOrder, AgentLog, Alert, Medicine


class MasterOrchestrator:
    """
    PharmaGuard Master AI Orchestrator Agent.
    Coordinates the autonomous Observe -> Analyze -> Plan -> Act -> Learn lifecycle
    and manages human-in-the-loop approvals and multi-channel queries.
    """
    def __init__(self):
        self.inventory_agent = InventoryAgent()
        self.forecasting_agent = ForecastingAgent()
        self.procurement_agent = ProcurementAgent()

    def run_autonomous_cycle(self, db: Session, pharmacy_id: str) -> Dict[str, Any]:
        """
        Executes a complete 5-stage autonomous pharmacy intelligence cycle.
        """
        cycle_id = f"CYCLE-{uuid.uuid4().hex[:8].upper()}"
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        pharmacy_name = pharmacy.name if pharmacy else "Community Pharmacy"

        context = AgentContext(
            pharmacy_id=pharmacy_id,
            pharmacy_name=pharmacy_name,
            current_time=datetime.utcnow()
        )

        state = AgentState(cycle_id=cycle_id, phase="OBSERVE", context=context)

        # -----------------------------------------------------------
        # Stage 1: OBSERVE
        # -----------------------------------------------------------
        inv_eval = self.inventory_agent.evaluate(db, pharmacy_id)
        state.observations = {
            "total_skus": inv_eval["health_summary"]["total_skus"],
            "stock_value_cost_fcfa": inv_eval["health_summary"]["total_inventory_cost_fcfa"],
            "critical_stockouts_count": inv_eval["health_summary"]["critical_stockouts_count"],
            "expiring_soon_count": inv_eval["health_summary"]["expiring_soon_count"]
        }
        self._log_phase(db, pharmacy_id, cycle_id, "OBSERVE", "Scanned inventory and expiry dates.")

        # -----------------------------------------------------------
        # Stage 2: ANALYZE
        # -----------------------------------------------------------
        state.phase = "ANALYZE"
        forecast_eval = self.forecasting_agent.evaluate(db, pharmacy_id, horizon_days=21)
        state.analysis = {
            "forecast_horizon_days": 21,
            "urgent_reorders_needed": forecast_eval["urgent_reorders_count"],
            "capital_at_expiry_risk_fcfa": inv_eval["health_summary"]["capital_at_expiry_risk_fcfa"]
        }
        self._log_phase(db, pharmacy_id, cycle_id, "ANALYZE", f"Analyzed run rates. Found {forecast_eval['urgent_reorders_count']} urgent reorders.")

        # -----------------------------------------------------------
        # Stage 3: PLAN
        # -----------------------------------------------------------
        state.phase = "PLAN"
        procurement_eval = self.procurement_agent.plan_procurement(
            db, pharmacy_id, forecast_eval["recommended_reorders"]
        )
        state.plans = {
            "draft_purchase_orders": procurement_eval["draft_orders"]
        }
        state.human_approvals_pending = procurement_eval["draft_orders"]
        self._log_phase(db, pharmacy_id, cycle_id, "PLAN", f"Formulated {len(procurement_eval['draft_orders'])} draft purchase orders.")

        # -----------------------------------------------------------
        # Stage 4: ACT
        # -----------------------------------------------------------
        state.phase = "ACT"
        briefing_md = generate_daily_briefing_markdown(db, pharmacy_id)
        state.actions = [
            {"type": "DAILY_BRIEFING_GENERATED", "channel": "whatsapp_ready"},
            {"type": "ALERTS_REGISTERED", "count": inv_eval["new_alerts_registered"]},
            {"type": "DRAFT_ORDERS_PREPARED", "count": len(procurement_eval["draft_orders"])}
        ]
        self._log_phase(db, pharmacy_id, cycle_id, "ACT", "Compiled briefing and synchronized network alerts.")

        # -----------------------------------------------------------
        # Stage 5: LEARN
        # -----------------------------------------------------------
        state.phase = "LEARN"
        learning_note = (
            f"Cycle {cycle_id} executed successfully. Monitored {inv_eval['health_summary']['total_skus']} SKUs. "
            f"Alerted on {inv_eval['health_summary']['critical_stockouts_count']} stockouts and {inv_eval['health_summary']['expiring_soon_count']} expiries."
        )
        state.learnings.append(learning_note)
        global_memory.record_cycle({
            "cycle_id": cycle_id,
            "pharmacy_id": pharmacy_id,
            "critical_stockouts": inv_eval["health_summary"]["critical_stockouts_count"],
            "expiring_soon": inv_eval["health_summary"]["expiring_soon_count"]
        })
        self._log_phase(db, pharmacy_id, cycle_id, "LEARN", learning_note)

        state.phase = "COMPLETED"
        state.completed_at = datetime.utcnow()

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
            "active_alerts_count": inv_eval["health_summary"]["critical_stockouts_count"] + inv_eval["health_summary"]["expiring_soon_count"],
            "recommended_orders": procurement_eval["draft_orders"],
            "briefing_text": briefing_md
        }

    def handle_user_query(self, db: Session, pharmacy_id: str, query: str, channel: str = "web") -> Dict[str, Any]:
        """
        Processes natural language queries from pharmacists or patients.
        """
        q = query.lower().strip()
        global_memory.add_message("user", query, {"channel": channel})

        # 1. Check for Briefing / Summary request
        if any(w in q for w in ["briefing", "report", "summary", "daily", "overview"]):
            briefing_text = generate_daily_briefing_markdown(db, pharmacy_id)
            global_memory.add_message("agent", briefing_text)
            return {
                "response": briefing_text,
                "suggested_actions": ["Run Autonomous Cycle", "View Purchase Orders", "Check Expiries"],
                "data": {"type": "briefing"}
            }

        # 2. Check for Stockout / Low stock query
        if any(w in q for w in ["low stock", "stockout", "shortage", "running out", "reorder"]):
            low_stock = list_low_stock_items(db, pharmacy_id)
            if not low_stock:
                resp = "✅ All inventory items are currently above safe reorder thresholds."
            else:
                lines = [f"🚨 **Found {len(low_stock)} items facing stockout risk:**\n"]
                for item in low_stock:
                    lines.append(f"• **{item['name']}** ({item['generic_name']}): `{item['quantity_in_stock']} units` (Depletes in ~{item['days_of_stock_remaining']} days)")
                resp = "\n".join(lines)
            global_memory.add_message("agent", resp)
            return {
                "response": resp,
                "suggested_actions": ["Draft Purchase Orders", "View Suppliers"],
                "data": {"items": low_stock}
            }

        # 3. Check for Expiry query
        if any(w in q for w in ["expiry", "expire", "expiring", "perimé", "périmé", "dead stock"]):
            risks = calculate_expiry_risks(db, pharmacy_id)
            lines = [f"⏳ **Expiry Risk Analysis (Capital at Risk: {risks['capital_loss_threat_fcfa']:,.0f} FCFA):**\n"]
            if risks["critical_30_days"]:
                lines.append("**Critical (<30 Days):**")
                for it in risks["critical_30_days"]:
                    lines.append(f"• {it['name']} — `{it['quantity_in_stock']} units` (Exp: {it['expiry_date']}) → *{it['action_recommendation']}*")
            if risks["warning_60_days"]:
                lines.append("\n**Warning (<60 Days):**")
                for it in risks["warning_60_days"]:
                    lines.append(f"• {it['name']} — `{it['quantity_in_stock']} units` (Exp: {it['expiry_date']}) → *{it['action_recommendation']}*")
            resp = "\n".join(lines)
            global_memory.add_message("agent", resp)
            return {
                "response": resp,
                "suggested_actions": ["Apply 30% Discount", "Notify Pharmacist"],
                "data": risks
            }

        # 4. Search specific medicine stock
        words = [w for w in q.split() if len(w) > 3 and w not in ["have", "find", "check", "stock", "price", "search", "where"]]
        search_query = words[0] if words else q
        matches = query_stock_level(db, search_query, pharmacy_id)

        if matches:
            lines = [f"🔍 **Found {len(matches)} matching product(s):**\n"]
            for m in matches:
                lines.append(
                    f"• **{m['name']}** ({m['generic_name']})\n"
                    f"  - In Stock: `{m['quantity_in_stock']} units` (Shelf: {m['location_shelf']})\n"
                    f"  - Price: `{m['selling_price_fcfa']:,.0f} FCFA` | Unit Cost: `{m['unit_cost_fcfa']:,.0f} FCFA`\n"
                    f"  - Expiry: `{m['expiry_date']}` ({m['days_until_expiry']} days left)\n"
                    f"  - Status: {m['stockout_risk_level']} stockout risk"
                )
            resp = "\n".join(lines)
        else:
            resp = f"ℹ️ No medicines found matching '{query}'. Please check the medicine name or generic molecule spelling."

        global_memory.add_message("agent", resp)
        return {
            "response": resp,
            "suggested_actions": ["Check Alternative Suppliers", "View All Medicines"],
            "data": {"matches": matches}
        }

    def approve_purchase_order(self, db: Session, po_id: str) -> Dict[str, Any]:
        """
        Human-in-the-Loop Action: Pharmacist authorizes a draft purchase order.
        """
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if not po:
            return {"status": "ERROR", "message": f"Purchase order {po_id} not found."}

        po.status = "APPROVED"
        po.approved_at = datetime.utcnow()
        db.commit()
        db.refresh(po)

        po_text = format_purchase_order_text(db, po)
        return {
            "status": "SUCCESS",
            "po_id": po.id,
            "new_status": po.status,
            "approved_at": po.approved_at.isoformat(),
            "supplier_id": po.supplier_id,
            "total_amount_fcfa": po.total_amount_fcfa,
            "formatted_order_text": po_text
        }

    def _log_phase(self, db: Session, pharmacy_id: str, cycle_id: str, phase: str, summary: str):
        """Helper to record agent execution logs in database."""
        log = AgentLog(
            pharmacy_id=pharmacy_id,
            cycle_id=cycle_id,
            phase=phase,
            agent_name="MasterOrchestrator",
            summary=summary,
            created_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()


# Orchestrator singleton
orchestrator = MasterOrchestrator()
