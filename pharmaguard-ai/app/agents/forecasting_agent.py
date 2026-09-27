from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..database.models import Inventory, Medicine
from ..services.forecasting import forecast_medicine_demand, compute_reorder_recommendation


class ForecastingAgent:
    """
    Sub-Agent: Demand Prediction & Shortage Anticipator.
    """
    def __init__(self, agent_name: str = "DemandForecaster"):
        self.agent_name = agent_name

    def evaluate(self, db: Session, pharmacy_id: str, horizon_days: int = 21) -> Dict[str, Any]:
        """
        Runs predictive demand forecasting across all inventory items.
        """
        items = (
            db.query(Inventory, Medicine)
            .join(Medicine, Inventory.medicine_id == Medicine.id)
            .filter(Inventory.pharmacy_id == pharmacy_id)
            .all()
        )

        forecasts = []
        reorder_needs = []

        for inv, med in items:
            fc = forecast_medicine_demand(db, inv, med, days_horizon=horizon_days)
            forecasts.append(fc)

            reorder_rec = compute_reorder_recommendation(db, inv, med, target_cover_days=horizon_days)
            if reorder_rec["recommended_order_units"] > 0:
                reorder_needs.append(reorder_rec)

        reorder_needs.sort(key=lambda x: (0 if x["urgency"] == "CRITICAL" else 1, x["stockout_in_days"]))

        return {
            "agent": self.agent_name,
            "status": "COMPLETED",
            "forecast_horizon_days": horizon_days,
            "total_evaluated_skus": len(items),
            "urgent_reorders_count": len([r for r in reorder_needs if r["urgency"] == "CRITICAL"]),
            "recommended_reorders": reorder_needs,
            "all_forecasts": forecasts
        }
