from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ...database.models.entities import Inventory, Medicine, Supplier, SalesHistory


def get_current_inventory(pharmacy_id: str, db: Session) -> List[Dict[str, Any]]:
    """
    Tool: Retrieve all current inventory batches, locations, and shelf details for a pharmacy.
    """
    items = (
        db.query(Inventory, Medicine)
        .join(Medicine, Inventory.medicine_id == Medicine.id)
        .filter(Inventory.pharmacy_id == pharmacy_id)
        .all()
    )

    result = []
    for inv, med in items:
        result.append({
            "inventory_id": inv.id,
            "pharmacy_id": inv.pharmacy_id,
            "medicine_id": med.id,
            "generic_name": med.generic_name,
            "name": med.brand_names,
            "category": med.category,
            "strength": med.strength,
            "dosage_form": med.dosage_form,
            "quantity": inv.quantity,
            "reorder_threshold": inv.reorder_threshold,
            "expiry_date": inv.expiry_date.isoformat(),
            "unit_cost_fcfa": inv.unit_cost_fcfa,
            "selling_price_fcfa": inv.selling_price_fcfa,
            "batch_number": inv.batch_number,
            "supplier_id": inv.supplier_id,
            "location_shelf": inv.location_shelf
        })
    return result


def update_inventory(pharmacy_id: str, medicine_id: str, quantity_delta: int, db: Session, reason: str = "Physical Audit / Dispensing") -> Optional[Dict[str, Any]]:
    """
    Tool: Updates current stock quantity for an inventory item.
    """
    inv = (
        db.query(Inventory)
        .filter(Inventory.medicine_id == medicine_id, Inventory.pharmacy_id == pharmacy_id)
        .first()
    )
    if not inv:
        return None
    inv.quantity = max(0, inv.quantity + quantity_delta)
    db.commit()
    db.refresh(inv)
    return {
        "status": "SUCCESS",
        "medicine_id": medicine_id,
        "new_quantity": inv.quantity,
        "reason": reason
    }


def analyze_stock_level(pharmacy_id: str, medicine_id: str, db: Session) -> Dict[str, Any]:
    """
    Tool: Calculates stock coverage in days and checks against supplier delivery lead time.
    """
    inv = (
        db.query(Inventory)
        .filter(Inventory.medicine_id == medicine_id, Inventory.pharmacy_id == pharmacy_id)
        .first()
    )
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not inv or not med:
        return {"status": "ERROR", "message": f"Medicine {medicine_id} not found."}

    # Retrieve sales history
    sales = (
        db.query(SalesHistory)
        .filter(SalesHistory.medicine_id == medicine_id, SalesHistory.pharmacy_id == pharmacy_id)
        .all()
    )
    total_units_sold = sum(s.quantity for s in sales)
    days_recorded = len(set(s.timestamp.date() for s in sales)) or 1
    avg_daily_sales = round(total_units_sold / days_recorded, 2) if total_units_sold > 0 else 0.5

    # Retrieve supplier lead time
    supplier_delivery_days = 2
    supplier_name = "Wholesale Supplier"
    sup = None
    if inv.supplier_id:
        sup = db.query(Supplier).filter(Supplier.id == inv.supplier_id).first()
    if not sup:
        sup = db.query(Supplier).first()
    if sup:
        supplier_delivery_days = sup.delivery_time
        supplier_name = sup.name

    # Calculate stock coverage
    stock_coverage_days = round(inv.quantity / avg_daily_sales, 1)

    # Expiry evaluation
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

    # Evaluate shortage risk & reasoning
    if inv.quantity == 0 or stock_coverage_days <= 0:
        risk_level = "CRITICAL_STOCKOUT"
        confidence_score = 0.98
        reasoning = f"{med.brand_names} is out of stock. Immediate replenishment required."
        recommendation = "Execute urgent supplier order."
    elif stock_coverage_days < supplier_delivery_days:
        risk_level = "HIGH"
        confidence_score = 0.91
        reasoning = (
            f"{med.brand_names} has a high shortage risk because current inventory covers "
            f"approximately {int(stock_coverage_days) if stock_coverage_days.is_integer() else stock_coverage_days} days "
            f"while supplier delivery requires {supplier_delivery_days} days. "
            f"I recommend reviewing replenishment options."
        )
        recommendation = "Review replenishment options immediately."
    elif stock_coverage_days <= supplier_delivery_days + 3:
        risk_level = "MEDIUM"
        confidence_score = 0.88
        reasoning = f"{med.brand_names} has moderate stock coverage ({stock_coverage_days} days)."
        recommendation = "Monitor daily run rate."
    else:
        risk_level = "SAFE"
        confidence_score = 0.95
        reasoning = f"{med.brand_names} stock is healthy ({stock_coverage_days} days coverage)."
        recommendation = "Maintain regular monitoring."

    return {
        "medicine_id": med.id,
        "name": med.brand_names,
        "generic_name": med.generic_name,
        "category": med.category,
        "current_quantity": inv.quantity,
        "average_daily_sales": avg_daily_sales,
        "avg_daily_sales": avg_daily_sales,
        "stock_coverage_days": stock_coverage_days,
        "supplier_delivery_days": supplier_delivery_days,
        "supplier_name": supplier_name,
        "supplier_id": sup.id if sup else None,
        "risk_level": risk_level,
        "confidence_score": confidence_score,
        "reasoning": reasoning,
        "recommendation": recommendation,
        "unit_cost_fcfa": inv.unit_cost_fcfa,
        "selling_price_fcfa": inv.selling_price_fcfa,
        "expiry_date": inv.expiry_date.isoformat(),
        "days_until_expiry": days_until_expiry,
        "expiry_status": expiry_status
    }
