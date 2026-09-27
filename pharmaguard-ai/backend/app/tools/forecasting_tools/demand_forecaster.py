import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from ...database.models.entities import Inventory, Medicine, SalesHistory, Supplier, Pharmacy


# Regional Seasonal Profiles (e.g., Central / West Africa: Cameroon, etc.)
SEASONAL_DISEASE_PATTERNS = {
    "Antimalarial": {
        # Peak rainy season transmission (May - October)
        "months": [5, 6, 7, 8, 9, 10],
        "multiplier": 1.35,
        "description": "High rainy season transmission surge (Malaria vector proliferation)"
    },
    "Antibiotic": {
        # Harmattan / dry dusty season & seasonal transition respiratory infections
        "months": [11, 12, 1, 2, 7, 8],
        "multiplier": 1.25,
        "description": "Seasonal respiratory infection surge (Harmattan / weather transition)"
    },
    "Respiratory / Cough": {
        "months": [11, 12, 1, 2, 7, 8],
        "multiplier": 1.30,
        "description": "Dust and cold season broncho-pulmonary surge"
    },
    "Antidiabetic": {
        # Chronic maintenance therapies have stable non-seasonal baseline
        "months": list(range(1, 13)),
        "multiplier": 1.00,
        "description": "Stable chronic pathology baseline"
    },
    "Antihypertensive": {
        "months": list(range(1, 13)),
        "multiplier": 1.00,
        "description": "Stable chronic cardiovascular maintenance"
    },
    "Analgesic / Antipyretic": {
        "months": [5, 6, 7, 8, 9, 10],
        "multiplier": 1.20,
        "description": "Fever and general malaise accompanying seasonal epidemics"
    }
}


def get_seasonal_multiplier(category: str, current_month: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculates seasonal demand multiplier based on therapeutic class and calendar month.
    """
    month = current_month or datetime.now(timezone.utc).month
    
    for cat_key, profile in SEASONAL_DISEASE_PATTERNS.items():
        if cat_key.lower() in category.lower() or category.lower() in cat_key.lower():
            if month in profile["months"]:
                return {
                    "is_seasonal_surge": profile["multiplier"] > 1.0,
                    "multiplier": profile["multiplier"],
                    "pattern": profile["description"],
                    "category_match": cat_key
                }
            else:
                return {
                    "is_seasonal_surge": False,
                    "multiplier": 1.0,
                    "pattern": "Off-peak seasonal period",
                    "category_match": cat_key
                }
                
    return {
        "is_seasonal_surge": False,
        "multiplier": 1.0,
        "pattern": "Standard baseline demand",
        "category_match": "General"
    }


def compute_medicine_forecast(
    pharmacy_id: str,
    medicine_id: str,
    db: Session,
    forecast_horizon_days: int = 30
) -> Dict[str, Any]:
    """
    Core Statistical & Clinical Forecasting Tool:
    - Analyzes historical sales velocity & trend trajectory.
    - Applies regional seasonal adjustments.
    - Estimates exact stockout depletion date.
    - Evaluates stockout vulnerability against supplier delivery lead time.
    """
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    inv = db.query(Inventory).filter(Inventory.medicine_id == medicine_id, Inventory.pharmacy_id == pharmacy_id).first()
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()

    if not med:
        return {"status": "ERROR", "message": f"Medicine {medicine_id} not found."}

    current_stock = inv.quantity if inv else 0
    supplier_lead_time = 2
    supplier_name = "Primary Wholesale Distributor"

    if inv and inv.supplier_id:
        sup = db.query(Supplier).filter(Supplier.id == inv.supplier_id).first()
        if sup:
            supplier_lead_time = sup.delivery_time
            supplier_name = sup.name
    else:
        sup = db.query(Supplier).first()
        if sup:
            supplier_lead_time = sup.delivery_time
            supplier_name = sup.name

    # 1. Ingest sales history
    sales_records = (
        db.query(SalesHistory)
        .filter(SalesHistory.medicine_id == medicine_id, SalesHistory.pharmacy_id == pharmacy_id)
        .order_by(SalesHistory.timestamp.asc())
        .all()
    )

    today = date.today()
    current_month = today.month

    # Seasonal factors
    seasonal_info = get_seasonal_multiplier(med.category or "", current_month)
    seasonal_multiplier = seasonal_info["multiplier"]

    # 2. Historical demand analysis
    if not sales_records:
        # Fallback baseline when sales history is nascent
        base_daily_sales = 0.5
        trend_slope = 0.0
        trend_direction = "STABLE"
        data_points_count = 0
        confidence = 0.75
    else:
        # Group sales by date
        daily_quantities = {}
        for s in sales_records:
            s_date = s.timestamp.date() if isinstance(s.timestamp, datetime) else s.timestamp
            daily_quantities[s_date] = daily_quantities.get(s_date, 0) + s.quantity

        data_points_count = len(daily_quantities)
        quantities_list = list(daily_quantities.values())

        # Average daily baseline
        total_units = sum(quantities_list)
        base_daily_sales = round(total_units / max(1, data_points_count), 2)

        # Trend calculation (Linear regression slope over past sales)
        if len(quantities_list) >= 3:
            x = np.arange(len(quantities_list))
            y = np.array(quantities_list)
            # Slope calculation
            slope, _ = np.polyfit(x, y, 1)
            trend_slope = round(float(slope), 3)
            if trend_slope > 0.15:
                trend_direction = "SURGING"
            elif trend_slope < -0.15:
                trend_direction = "DECLINING"
            else:
                trend_direction = "STABLE"
        else:
            trend_slope = 0.0
            trend_direction = "STABLE"

        # Confidence based on historical depth and variance
        std_dev = float(np.std(quantities_list)) if len(quantities_list) > 1 else 0.0
        cv = (std_dev / base_daily_sales) if base_daily_sales > 0 else 0.5
        confidence = round(max(0.70, min(0.96, 0.95 - (cv * 0.1) + min(0.05, data_points_count * 0.005))), 2)

    # 3. Forecasted daily demand with seasonal & trend adjustment
    trend_factor = max(-0.5, min(0.5, trend_slope * 0.2))
    projected_daily_demand = round(max(0.1, base_daily_sales * (1.0 + trend_factor) * seasonal_multiplier), 2)

    # Multi-horizon projections
    forecast_7d = round(projected_daily_demand * 7, 1)
    forecast_14d = round(projected_daily_demand * 14, 1)
    forecast_30d = round(projected_daily_demand * 30, 1)

    # 4. Stockout Prediction & Depletion Date
    if current_stock <= 0:
        days_until_stockout = 0.0
        estimated_stockout_date = today.isoformat()
        stockout_status = "IMMEDIATE_STOCKOUT"
        is_vulnerable = True
    else:
        days_until_stockout = round(current_stock / projected_daily_demand, 1)
        depletion_delta = timedelta(days=math.floor(days_until_stockout))
        estimated_stockout_date = (today + depletion_delta).isoformat()

        if days_until_stockout <= supplier_lead_time:
            stockout_status = "CRITICAL_BEFORE_DELIVERY"
            is_vulnerable = True
        elif days_until_stockout <= (supplier_lead_time + 4):
            stockout_status = "VULNERABLE_NEAR_TERM"
            is_vulnerable = True
        else:
            stockout_status = "SAFE_HORIZON"
            is_vulnerable = False

    # 5. Clinical & Operational Reasoning Narrative
    location_str = pharmacy.location if pharmacy else "Central Pharmacy"
    reasoning_parts = [
        f"{med.brand_names} ({med.generic_name}) current baseline velocity is {base_daily_sales} units/day."
    ]
    if seasonal_info["is_seasonal_surge"]:
        reasoning_parts.append(
            f"Seasonal factor for {seasonal_info['category_match']} is elevated ({int((seasonal_multiplier-1)*100)}% surge: {seasonal_info['pattern']})."
        )
    if trend_direction == "SURGING":
        reasoning_parts.append(f"Demand trajectory is surging (velocity slope +{trend_slope}).")
    elif trend_direction == "DECLINING":
        reasoning_parts.append(f"Demand trajectory is moderating (velocity slope {trend_slope}).")

    reasoning_parts.append(
        f"Adjusted projected run-rate is {projected_daily_demand} units/day. "
        f"Existing stock ({current_stock} units) will deplete by {estimated_stockout_date} (~{days_until_stockout} days)."
    )

    if is_vulnerable:
        reasoning_parts.append(
            f"⚠️ CRITICAL: Stockout expected in {days_until_stockout} days, which is within or near the {supplier_lead_time}-day supplier lead time from {supplier_name}."
        )

    explanation = " ".join(reasoning_parts)

    return {
        "medicine_id": med.id,
        "name": med.brand_names,
        "generic_name": med.generic_name,
        "category": med.category,
        "pharmacy_location": location_str,
        "current_stock": current_stock,
        "base_daily_sales": base_daily_sales,
        "trend_direction": trend_direction,
        "trend_slope": trend_slope,
        "seasonal_multiplier": seasonal_multiplier,
        "seasonal_description": seasonal_info["pattern"],
        "projected_daily_demand": projected_daily_demand,
        "forecast_7d_units": forecast_7d,
        "forecast_14d_units": forecast_14d,
        "forecast_30d_units": forecast_30d,
        "days_until_stockout": days_until_stockout,
        "estimated_stockout_date": estimated_stockout_date,
        "supplier_lead_time_days": supplier_lead_time,
        "supplier_name": supplier_name,
        "stockout_status": stockout_status,
        "stockout_before_replenishment": is_vulnerable,
        "confidence_score": confidence,
        "reasoning": explanation
    }
