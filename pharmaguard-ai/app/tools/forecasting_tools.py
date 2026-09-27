from datetime import date, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.models import SalesHistory, Medicine


def analyze_sales(medicine_id: str, db: Session, pharmacy_id: str = "PHARM-DLA-001", days_lookback: int = 14) -> Dict[str, Any]:
    """
    Tool: Understand demand patterns and calculate average daily sales.
    """
    cutoff_date = date.today() - timedelta(days=days_lookback)
    
    # Query recent sales records
    sales = (
        db.query(SalesHistory)
        .filter(
            SalesHistory.medicine_id == medicine_id,
            SalesHistory.pharmacy_id == pharmacy_id,
            SalesHistory.date >= cutoff_date
        )
        .all()
    )

    total_units_sold = sum(s.quantity_sold for s in sales)
    
    if not sales:
        # Fallback to all sales records if cutoff had none
        all_sales = (
            db.query(SalesHistory)
            .filter(SalesHistory.medicine_id == medicine_id, SalesHistory.pharmacy_id == pharmacy_id)
            .all()
        )
        total_units_sold = sum(s.quantity_sold for s in all_sales)
        recorded_days = len(set(s.date for s in all_sales)) or 1
        avg_daily_sales = round(total_units_sold / recorded_days, 2)
    else:
        avg_daily_sales = round(total_units_sold / max(1, len(set(s.date for s in sales))), 2)

    return {
        "medicine_id": medicine_id,
        "pharmacy_id": pharmacy_id,
        "total_units_sold_recent": total_units_sold,
        "average_daily_sales": max(0.1, avg_daily_sales),
        "days_observed": days_lookback
    }


def forecast_demand(
    medicine_id: str,
    db: Session,
    pharmacy_id: str = "PHARM-DLA-001",
    horizon_days: int = 14
) -> Dict[str, Any]:
    """
    Tool: Forecasts future demand units over a given horizon.
    """
    sales_analysis = analyze_sales(medicine_id, db, pharmacy_id)
    daily_sales = sales_analysis["average_daily_sales"]
    
    projected_demand = round(daily_sales * horizon_days, 1)

    return {
        "medicine_id": medicine_id,
        "daily_demand_rate": daily_sales,
        "horizon_days": horizon_days,
        "projected_demand_units": projected_demand
    }
