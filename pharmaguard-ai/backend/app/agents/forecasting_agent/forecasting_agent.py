import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import (
    Pharmacy,
    Inventory,
    Medicine,
    AgentActionLog,
    Alert
)
from ...tools.forecasting_tools.demand_forecaster import compute_medicine_forecast
from ...memory.short_term.working_memory import session_working_memory


class PharmacyForecastingAgent:
    """
    PharmaGuard Pharmacy Forecasting Intelligence Agent (Phase 2).
    
    Responsibilities:
    - Analyzes historical sales patterns & demand velocity.
    - Applies regional seasonal epidemiological multipliers.
    - Projects multi-horizon demand (7, 14, 30 days).
    - Estimates exact stockout depletion dates.
    - Detects vulnerabilities where stockout occurs before supplier replenishment arrives.
    - Explains clinical & mathematical reasoning with confidence scoring.
    """
    def __init__(self, agent_name: str = "ForecastingIntelligenceAgent"):
        self.agent_name = agent_name

    def forecast_single_medicine(
        self,
        pharmacy_id: str,
        medicine_id: str,
        db: Session,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generates deep-dive demand projection and stockout timeline for a specific medicine.
        """
        forecast = compute_medicine_forecast(pharmacy_id, medicine_id, db, horizon_days)
        return forecast

    def analyze_future_state(
        self,
        pharmacy_id: str,
        db: Session,
        horizon_days: int = 30
    ) -> Dict[str, Any]:
        """
        Autonomous Step 2 in Morning Intelligence Cycle:
        Predicts future pharmacy state across all active inventory items.
        """
        session_working_memory.log_step("FORECASTING_START", {"pharmacy_id": pharmacy_id, "horizon": horizon_days})

        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        pharmacy_name = pharmacy.organization_name if pharmacy else "Community Pharmacy"

        # Ingest all active SKUs in inventory
        inventory_items = (
            db.query(Inventory)
            .filter(Inventory.pharmacy_id == pharmacy_id)
            .all()
        )

        all_forecasts: List[Dict[str, Any]] = []
        imminent_stockout_risks: List[Dict[str, Any]] = []
        seasonal_surges: List[Dict[str, Any]] = []
        total_30d_projected_units = 0.0

        for item in inventory_items:
            fc = compute_medicine_forecast(pharmacy_id, item.medicine_id, db, horizon_days)
            if fc.get("status") == "ERROR":
                continue

            all_forecasts.append(fc)
            total_30d_projected_units += fc.get("forecast_30d_units", 0.0)

            # Check if stockout is predicted before replenishment or in near term (<7 days)
            if fc.get("stockout_before_replenishment") or fc.get("days_until_stockout", 999) <= 7.0:
                imminent_stockout_risks.append(fc)

            # Check seasonal surge
            if fc.get("seasonal_multiplier", 1.0) > 1.05:
                seasonal_surges.append(fc)

        # Sort imminent risks by urgency (fewest days until stockout first)
        imminent_stockout_risks.sort(key=lambda x: x.get("days_until_stockout", 999))

        session_working_memory.log_step("FORECASTING_COMPLETE", {
            "evaluated_skus": len(all_forecasts),
            "imminent_stockouts_count": len(imminent_stockout_risks),
            "seasonal_surge_count": len(seasonal_surges),
            "total_30d_units": total_30d_projected_units
        })

        # Generate Forecasting Summary Narrative
        summary_lines = [
            f"🔮 *PREDICTIVE DEMAND & DEPLETION INTELLIGENCE*",
            f"• *Evaluated SKUs:* {len(all_forecasts)} | *30-Day Demand Volume:* {total_30d_projected_units:,.0f} units",
            f"• *Imminent Stockout Trajectories:* {len(imminent_stockout_risks)} SKU(s)",
            f"• *Active Seasonal Disease Surges:* {len(seasonal_surges)} SKU(s)"
        ]

        if imminent_stockout_risks:
            summary_lines.append("\n⚠️ *PROJECTED STOCKOUT TIMELINES:*")
            for r in imminent_stockout_risks[:5]:
                summary_lines.append(
                    f"• *{r['name']}*: Depletion by *{r['estimated_stockout_date']}* (~{r['days_until_stockout']} days) "
                    f"| Run-rate: {r['projected_daily_demand']}/day | Supplier lead: {r['supplier_lead_time_days']}d"
                )

        return {
            "status": "SUCCESS",
            "agent": self.agent_name,
            "pharmacy_id": pharmacy_id,
            "pharmacy_name": pharmacy_name,
            "timestamp": datetime.now(timezone.utc),
            "evaluated_skus_count": len(all_forecasts),
            "imminent_stockouts_count": len(imminent_stockout_risks),
            "seasonal_surges_count": len(seasonal_surges),
            "total_30d_projected_demand_units": round(total_30d_projected_units, 1),
            "forecasts": all_forecasts,
            "imminent_stockout_risks": imminent_stockout_risks,
            "seasonal_surges": seasonal_surges,
            "narrative_summary": "\n".join(summary_lines)
        }


# Singleton instance of Forecasting Agent
forecasting_agent = PharmacyForecastingAgent()
