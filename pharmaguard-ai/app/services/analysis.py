from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.models import Inventory, Medicine, SalesHistory


def calculate_daily_sales_velocity(db: Session, medicine_id: str, pharmacy_id: str = "PHARM-DLA-001", days_lookback: int = 14) -> float:
    """Calculates average units sold per day for a medicine over recent days."""
    cutoff_date = date.today() - timedelta(days=days_lookback)
    total_sold = (
        db.query(func.sum(SalesHistory.quantity_sold))
        .filter(
            SalesHistory.medicine_id == medicine_id,
            SalesHistory.pharmacy_id == pharmacy_id,
            SalesHistory.date >= cutoff_date
        )
        .scalar()
    )
    if total_sold is None:
        all_sold = (
            db.query(func.sum(SalesHistory.quantity_sold))
            .filter(SalesHistory.medicine_id == medicine_id, SalesHistory.pharmacy_id == pharmacy_id)
            .scalar()
        ) or 0
        return round(float(all_sold) / 7.0, 2)

    return round(float(total_sold) / max(1, days_lookback), 2)


def get_medicine_risk_profile(db: Session, inv: Inventory, med: Medicine) -> Dict[str, Any]:
    """Evaluates expiry and stockout risk metrics for a single medicine item."""
    today = date.today()
    days_until_expiry = (inv.expiry_date - today).days

    if days_until_expiry <= 0:
        expiry_status = "EXPIRED"
    elif days_until_expiry <= 30:
        expiry_status = "CRITICAL"
    elif days_until_expiry <= 60:
        expiry_status = "WARNING"
    elif days_until_expiry <= 90:
        expiry_status = "NOTICE"
    else:
        expiry_status = "OK"

    velocity = calculate_daily_sales_velocity(db, med.id, inv.pharmacy_id)
    if velocity > 0:
        dir_days = round(inv.quantity / velocity, 1)
    else:
        dir_days = 999.0

    if dir_days <= 3.0 or inv.quantity == 0:
        stockout_risk_level = "CRITICAL"
    elif dir_days <= 7.0 or inv.quantity <= inv.reorder_point:
        stockout_risk_level = "HIGH"
    elif dir_days <= 14.0:
        stockout_risk_level = "MEDIUM"
    else:
        stockout_risk_level = "SAFE"

    return {
        "medicine_id": med.id,
        "name": med.name,
        "generic_name": med.generic_name,
        "category": med.category,
        "quantity_in_stock": inv.quantity,
        "reorder_point": inv.reorder_point,
        "unit_cost_fcfa": inv.unit_cost_fcfa,
        "selling_price_fcfa": inv.selling_price_fcfa,
        "expiry_date": inv.expiry_date.isoformat(),
        "days_until_expiry": days_until_expiry,
        "expiry_status": expiry_status,
        "daily_sales_velocity": velocity,
        "days_of_stock_remaining": dir_days,
        "stockout_risk_level": stockout_risk_level,
        "supplier_id": inv.supplier_id,
        "location_shelf": inv.location_shelf
    }


def analyze_inventory_health(db: Session, pharmacy_id: str) -> Dict[str, Any]:
    """Comprehensive analysis of pharmacy inventory health and risk factors."""
    items = (
        db.query(Inventory, Medicine)
        .join(Medicine, Inventory.medicine_id == Medicine.id)
        .filter(Inventory.pharmacy_id == pharmacy_id)
        .all()
    )

    profiles = [get_medicine_risk_profile(db, inv, med) for inv, med in items]

    total_skus = len(profiles)
    total_inventory_cost = sum(inv.quantity * inv.unit_cost_fcfa for inv, _ in items)
    total_inventory_retail = sum(inv.quantity * inv.selling_price_fcfa for inv, _ in items)

    critical_stockouts = [p for p in profiles if p["stockout_risk_level"] in ["CRITICAL", "HIGH"]]
    expiring_soon = [p for p in profiles if p["expiry_status"] in ["EXPIRED", "CRITICAL", "WARNING"]]

    capital_at_risk = sum(
        p["quantity_in_stock"] * p["unit_cost_fcfa"] for p in expiring_soon
    )

    return {
        "pharmacy_id": pharmacy_id,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_skus": total_skus,
        "total_inventory_cost_fcfa": round(total_inventory_cost, 2),
        "total_inventory_retail_fcfa": round(total_inventory_retail, 2),
        "capital_at_expiry_risk_fcfa": round(capital_at_risk, 2),
        "critical_stockouts_count": len(critical_stockouts),
        "expiring_soon_count": len(expiring_soon),
        "critical_stockout_items": critical_stockouts,
        "expiring_items": expiring_soon,
        "all_items": profiles
    }
