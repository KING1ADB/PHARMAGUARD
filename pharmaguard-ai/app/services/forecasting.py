from datetime import date, timedelta
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from ..database.models import Inventory, Medicine, Supplier
from .analysis import calculate_daily_sales_velocity


CATEGORY_SEASONAL_FACTORS = {
    "Antimalarial": 1.35,
    "Antibiotic": 1.20,
    "Analgesic/Antipyretic": 1.15,
    "Respiratory": 1.25,
    "Electrolyte": 1.30,
    "Anti-inflammatory": 1.05,
    "Antidiabetic": 1.0,
    "Gastrointestinal": 1.05
}


def forecast_medicine_demand(
    db: Session,
    inv: Inventory,
    med: Medicine,
    days_horizon: int = 14
) -> Dict[str, Any]:
    """
    Projects future demand over days_horizon based on historical run rates and seasonal factors.
    """
    base_velocity = calculate_daily_sales_velocity(db, med.id, inv.pharmacy_id)
    seasonal_multiplier = CATEGORY_SEASONAL_FACTORS.get(med.category, 1.0)
    adjusted_daily_demand = round(max(0.5, base_velocity * seasonal_multiplier), 2)

    projected_demand = round(adjusted_daily_demand * days_horizon, 1)

    if adjusted_daily_demand > 0:
        days_to_depletion = inv.quantity / adjusted_daily_demand
        depletion_date = date.today() + timedelta(days=int(days_to_depletion))
        stockout_in_days = round(days_to_depletion, 1)
    else:
        depletion_date = None
        stockout_in_days = 999.0

    return {
        "medicine_id": med.id,
        "name": med.name,
        "category": med.category,
        "current_stock": inv.quantity,
        "base_daily_velocity": base_velocity,
        "seasonal_multiplier": seasonal_multiplier,
        "adjusted_daily_demand": adjusted_daily_demand,
        "forecast_horizon_days": days_horizon,
        "projected_demand_units": projected_demand,
        "stockout_in_days": stockout_in_days,
        "predicted_depletion_date": depletion_date.isoformat() if depletion_date else None
    }


def compute_reorder_recommendation(
    db: Session,
    inv: Inventory,
    med: Medicine,
    target_cover_days: int = 21
) -> Dict[str, Any]:
    """
    Calculates the optimal replenishment quantity.
    """
    forecast = forecast_medicine_demand(db, inv, med, days_horizon=target_cover_days)
    daily_demand = forecast["adjusted_daily_demand"]

    lead_time_days = 2
    if inv.supplier_id:
        supplier = db.query(Supplier).filter(Supplier.id == inv.supplier_id).first()
        if supplier and supplier.delivery_time:
            lead_time_days = supplier.delivery_time

    safety_stock = round(daily_demand * 2, 0)
    required_stock = round((lead_time_days + target_cover_days) * daily_demand + safety_stock, 0)
    recommended_order_units = max(0, int(required_stock - inv.quantity))

    estimated_cost_fcfa = round(recommended_order_units * inv.unit_cost_fcfa, 2)
    urgency = "CRITICAL" if forecast["stockout_in_days"] <= lead_time_days else (
        "HIGH" if forecast["stockout_in_days"] <= 7 else "ROUTINE"
    )

    return {
        "medicine_id": med.id,
        "name": med.name,
        "supplier_id": inv.supplier_id,
        "current_stock": inv.quantity,
        "lead_time_days": lead_time_days,
        "stockout_in_days": forecast["stockout_in_days"],
        "urgency": urgency,
        "recommended_order_units": recommended_order_units,
        "unit_cost_fcfa": inv.unit_cost_fcfa,
        "estimated_total_cost_fcfa": estimated_cost_fcfa,
        "reasoning": (
            f"Stock ({inv.quantity} units) will deplete in ~{forecast['stockout_in_days']} days. "
            f"Supplier lead time is {lead_time_days} days. "
            f"Reordering {recommended_order_units} units covers {target_cover_days} days demand."
        )
    }
