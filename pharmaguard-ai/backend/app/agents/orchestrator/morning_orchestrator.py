import uuid
import json
from datetime import datetime, date, timezone
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
from ..inventory_agent.morning_intelligence_agent import morning_agent
from ..forecasting_agent.forecasting_agent import forecasting_agent
from ..procurement_agent.procurement_agent import procurement_agent
from ...memory.short_term.working_memory import session_working_memory
from ...memory.long_term.episodic_memory import EpisodicMemoryManager


class MultiAgentMorningOrchestrator:
    """
    PharmaGuard Multi-Agent Morning Intelligence Orchestrator.
    
    Coordinates the 5-step autonomous morning cycle:
    1. Inventory Agent analyzes current state (batches, expiries, current stock).
    2. Forecasting Agent predicts future state (demand curves, seasonal disease trends, stockout dates).
    3. Procurement Agent evaluates optimal actions (replenishment orders & supplier selection).
    4. Orchestrator unifies results into executive intelligence briefing & alerts.
    5. Human Pharmacist Authorization remains mandatory with episodic learning.
    """
    def __init__(self, orchestrator_name: str = "MultiAgentMorningOrchestrator"):
        self.orchestrator_name = orchestrator_name

    def execute_morning_cycle(self, pharmacy_id: str, db: Session) -> Dict[str, Any]:
        """
        Executes the integrated multi-agent morning cycle.
        """
        cycle_id = f"MORN-ORCH-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        session_working_memory.clear()
        session_working_memory.log_step("ORCHESTRATOR_START", {"cycle_id": cycle_id, "pharmacy_id": pharmacy_id})

        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        pharmacy_name = pharmacy.organization_name if pharmacy else "Community Pharmacy"

        # -------------------------------------------------------------
        # STEP 1: INVENTORY AGENT — CURRENT STATE ANALYSIS
        # -------------------------------------------------------------
        session_working_memory.log_step("STEP_1_INVENTORY_AGENT", {"status": "RUNNING"})
        inv_result = morning_agent.execute_morning_cycle(pharmacy_id, db)
        
        # -------------------------------------------------------------
        # STEP 2: FORECASTING AGENT — PREDICTIVE FUTURE STATE ANALYSIS
        # -------------------------------------------------------------
        session_working_memory.log_step("STEP_2_FORECASTING_AGENT", {"status": "RUNNING"})
        forecast_result = forecasting_agent.analyze_future_state(pharmacy_id, db, horizon_days=30)
        
        # -------------------------------------------------------------
        # STEP 3: PROCUREMENT AGENT — EVALUATE REPLENISHMENT ACTIONS
        # -------------------------------------------------------------
        session_working_memory.log_step("STEP_3_PROCUREMENT_AGENT", {"status": "RUNNING"})
        # Pass current inventory risks and predictive depletion forecasts
        current_risks = []
        for inv_item in db.query(Inventory).filter(Inventory.pharmacy_id == pharmacy_id).all():
            from ...tools.inventory_tools.inventory_reader import analyze_stock_level
            current_risks.append(analyze_stock_level(pharmacy_id, inv_item.medicine_id, db))

        # Check existing draft POs
        existing_drafts = db.query(PurchaseOrder).filter(
            PurchaseOrder.pharmacy_id == pharmacy_id,
            PurchaseOrder.status == "DRAFT"
        ).all()
        
        draft_pos = existing_drafts
        if not draft_pos:
            draft_pos = procurement_agent.evaluate_procurement_needs(
                pharmacy_id=pharmacy_id,
                current_risks=current_risks,
                future_forecasts=forecast_result.get("forecasts", []),
                db=db
            )

        # -------------------------------------------------------------
        # STEP 4: ORCHESTRATOR UNIFICATION & EXECUTIVE REPORTING
        # -------------------------------------------------------------
        session_working_memory.log_step("STEP_4_ORCHESTRATOR_UNIFY", {"status": "SYNTHESIZING"})

        total_skus = forecast_result.get("evaluated_skus_count", 0)
        imminent_stockouts = forecast_result.get("imminent_stockout_risks", [])
        seasonal_surges = forecast_result.get("seasonal_surges", [])
        total_30d_demand = forecast_result.get("total_30d_projected_demand_units", 0.0)

        # Combine inventory report and forecasting narrative
        today_str = date.today().strftime("%A, %d %B %Y")
        report_lines = [
            f"🏥 *PHARMAGUARD AI — MULTI-AGENT MORNING BRIEFING*",
            f"📍 *Pharmacy:* {pharmacy_name} | 📅 *Date:* {today_str}",
            f"📊 *Active SKUs:* {total_skus} | *30-Day Forecast Volume:* {total_30d_demand:,.0f} units",
            "──────────────────────────────────────────────",
            f"🚨 *CURRENT & IMMINENT STOCKOUT RISKS ({len(imminent_stockouts)} SKUs)*"
        ]

        if not imminent_stockouts:
            report_lines.append("✅ All essential medicines currently have sufficient stock coverage.")
        else:
            for s in imminent_stockouts[:5]:
                report_lines.append(
                    f"• *{s['name']}* ({s['generic_name']}): `{s['current_stock']} units in stock` "
                    f"→ Depletes by *{s['estimated_stockout_date']}* (~{s['days_until_stockout']}d) "
                    f"| Run-rate: *{s['projected_daily_demand']}/day* | Lead time: *{s['supplier_lead_time_days']}d*"
                )

        if seasonal_surges:
            report_lines.append("")
            report_lines.append(f"🌧️ *ACTIVE SEASONAL EPIDEMIOLOGICAL SURGES ({len(seasonal_surges)} SKUs)*")
            for surge in seasonal_surges[:4]:
                report_lines.append(
                    f"• *{surge['name']}* ({surge['category']}): +{int((surge['seasonal_multiplier']-1)*100)}% surge — _{surge['seasonal_description']}_"
                )

        report_lines.append("")
        report_lines.append("📋 *AUTONOMOUS PROCUREMENT ACTIONS (Awaiting Pharmacist Approval)*")
        if draft_pos:
            report_lines.append(f"• 📦 *{len(draft_pos)} Staged Purchase Order(s)* prepared for distributor dispatch.")
            for po in draft_pos[:3]:
                report_lines.append(f"  - `{po.id}`: {po.total_amount_fcfa:,.0f} FCFA ({po.status})")
        else:
            report_lines.append("• ✅ No immediate procurement replenishment needed this morning.")

        report_lines.append("──────────────────────────────────────────────")
        report_lines.append("_PharmaGuard AI — Multi-Agent Autonomous Healthcare Intelligence System_")

        full_orchestrated_markdown = "\n".join(report_lines)

        # Base report dictionary compatible with schema
        report_payload = {
            "pharmacy_name": pharmacy_name,
            "date": date.today().isoformat(),
            "execution_time_utc": datetime.now(timezone.utc).isoformat(),
            "total_active_skus": total_skus,
            "total_stock_value_fcfa": inv_result.get("report", {}).get("total_stock_value_fcfa", 0.0),
            "critical_shortages_count": len(imminent_stockouts),
            "expiring_soon_count": inv_result.get("report", {}).get("expiring_soon_count", 0),
            "capital_at_expiry_risk_fcfa": inv_result.get("report", {}).get("capital_at_expiry_risk_fcfa", 0.0),
            "critical_alerts": [
                {
                    "medicine_id": s["medicine_id"],
                    "title": f"Stockout Risk: {s['name']}",
                    "severity": "HIGH",
                    "reasoning": s["reasoning"],
                    "confidence": f"{int(s['confidence_score']*100)}%",
                    "recommendation": f"Replenish via {s['supplier_name']} (Depletion in {s['days_until_stockout']} days)."
                }
                for s in imminent_stockouts
            ],
            "draft_purchase_orders_count": len(draft_pos),
            "recommendations": [
                f"Review and authorize {len(draft_pos)} draft replenishment orders.",
                f"Prepare for seasonal surge on {len(seasonal_surges)} epidemiological SKUs."
            ] if draft_pos else ["Maintain standard operational monitoring."],
            "report_markdown": full_orchestrated_markdown
        }

        return {
            "status": "SUCCESS",
            "cycle_id": cycle_id,
            "pharmacy_id": pharmacy_id,
            "timestamp": datetime.now(timezone.utc),
            "total_skus_evaluated": total_skus,
            "high_shortage_risks": len(imminent_stockouts),
            "critical_expiries": inv_result.get("critical_expiries", 0),
            "draft_orders_created": len(draft_pos),
            "report": report_payload,
            "forecasting_summary": forecast_result
        }

    def process_pharmacist_decision(
        self,
        po_id: str,
        action: str,
        pharmacist_id: str,
        db: Session,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 5: Human-in-the-loop authorization & episodic learning.
        """
        return morning_agent.process_pharmacist_decision(
            po_id=po_id,
            action=action,
            pharmacist_id=pharmacist_id,
            db=db,
            notes=notes
        )


# Singleton instance of Multi-Agent Orchestrator
multi_agent_orchestrator = MultiAgentMorningOrchestrator()
