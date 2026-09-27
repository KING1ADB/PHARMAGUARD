from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database.models import Medicine, SaleRecord, Supplier


def calculate_daily_sales_velocity(db: Session, medicine_id: str, days_lookback: int = 14) -> float:
    """Calculates average units sold per day for a medicine over recent days."""
    cutoff_date = date.today() - timedelta(days=days_lookback)
    total_sold = (
        db.query(func.sum(SaleRecord.quantity_sold))
        .filter(SaleRecord.medicine_id == medicine_id, SaleRecord.date >= cutoff_date)
        .scalar()
    )
    if total_sold is None:
        # Fallback to all-time average if no recent sales
        total_sold = (
            db.query(func.sum(SaleRecord.quantity_sold))
            .filter(SaleRecord.medicine_id == medicine_id)
            .scalar()
        ) or 0
        days_count = max(1, (date.today() - date(2026, 9, 20)).days or 7)
        return round(float(total_sold) / days_count, 2)

    return round(float(total_sold) / max(1, days_lookback), 2)


def get_medicine_risk_profile(db: Session, medicine: Medicine) -> Dict[str, Any]:
    """Evaluates expiry and stockout risk metrics for a single medicine item."""
    today = date.today()
    days_until_expiry = (medicine.expiry_date - today).days

    # Expiry Classification
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

    # Velocity and Stockout Risk
    velocity = calculate_daily_sales_velocity(db, medicine.id)
    if velocity > 0:
        dir_days = round(medicine.quantity_in_stock / velocity, 1)
    else:
        dir_days = 999.0

    if dir_days <= 3.0 or medicine.quantity_in_stock == 0:
        stockout_risk_level = "CRITICAL"
    elif dir_days <= 7.0 or medicine.quantity_in_stock <= medicine.reorder_point:
        stockout_risk_level = "HIGH"
    elif dir_days <= 14.0:
        stockout_risk_level = "MEDIUM"
    else:
        stockout_risk_level = "SAFE"

    return {
        "medicine_id": medicine.id,
        "name": medicine.name,
        "generic_name": medicine.generic_name,
        "category": medicine.category,
        "quantity_in_stock": medicine.quantity_in_stock,
        "reorder_point": medicine.reorder_point,
        "unit_cost_fcfa": medicine.unit_cost_fcfa,
        "selling_price_fcfa": medicine.selling_price_fcfa,
        "expiry_date": medicine.expiry_date.isoformat(),
        "days_until_expiry": days_until_expiry,
        "expiry_status": expiry_status,
        "daily_sales_velocity": velocity,
        "days_of_stock_remaining": dir_days,
        "stockout_risk_level": stockout_risk_level,
        "supplier_id": medicine.supplier_id,
        "location_shelf": medicine.location_shelf
    }


def analyze_inventory_health(db: Session, pharmacy_id: str) -> Dict[str, Any]:
    """Comprehensive analysis of pharmacy inventory health and risk factors."""
    medicines = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).all()
    
    profiles = [get_medicine_risk_profile(db, med) for med in medicines]

    total_skus = len(profiles)
    total_inventory_cost_fcfa = sum(m.quantity_in_stock * m.unit_cost_fcfa for m in medicines)
    total_inventory_retail_fcfa = sum(m.quantity_in_stock * m.selling_price_fcfa for m in medicines)

    critical_stockouts = [p for p in profiles if p["stockout_risk_level"] in ["CRITICAL", "HIGH"]]
    expiring_soon = [p for p in profiles if p["expiry_status"] in ["EXPIRED", "CRITICAL", "WARNING"]]
    
    capital_at_expiry_risk = sum(
        p["quantity_in_stock"] * p["unit_cost_fcfa"] for p in expiring_soon
    )

    return {
        "pharmacy_id": pharmacy_id,
        "analysis_timestamp": datetime.utcnow().isoformat(),
        "total_skus": total_skus,
        "total_inventory_cost_fcfa": round(total_inventory_cost_fcfa, 2),
        "total_inventory_retail_fcfa": round(total_inventory_retail_fcfa, 2),
        "capital_at_expiry_risk_fcfa": round(capital_at_expiry_risk, 2),
        "critical_stockouts_count": len(critical_stockouts),
        "expiring_soon_count": len(expiring_soon),
        "critical_stockout_items": critical_stockouts,
        "expiring_items": expiring_soon,
        "all_items": profiles
    }
