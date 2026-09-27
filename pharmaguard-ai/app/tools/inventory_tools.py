from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database.models import Medicine, Pharmacy
from ..services.analysis import get_medicine_risk_profile


def query_stock_level(db: Session, query: str, pharmacy_id: str) -> List[Dict[str, Any]]:
    """
    Tool: Search inventory by brand name, generic molecule name, or category.
    """
    search_term = f"%{query.strip()}%"
    results = (
        db.query(Medicine)
        .filter(
            Medicine.pharmacy_id == pharmacy_id,
            or_(
                Medicine.name.ilike(search_term),
                Medicine.generic_name.ilike(search_term),
                Medicine.category.ilike(search_term)
            )
        )
        .all()
    )
    return [get_medicine_risk_profile(db, med) for med in results]


def list_low_stock_items(db: Session, pharmacy_id: str) -> List[Dict[str, Any]]:
    """
    Tool: Retrieves all items currently below their reorder threshold or with <7 days of stock.
    """
    medicines = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).all()
    low_stock = []
    for med in medicines:
        profile = get_medicine_risk_profile(db, med)
        if profile["stockout_risk_level"] in ["CRITICAL", "HIGH"]:
            low_stock.append(profile)
    return sorted(low_stock, key=lambda x: x["days_of_stock_remaining"])


def update_inventory_quantity(
    db: Session,
    medicine_id: str,
    quantity_delta: int,
    reason: str = "Adjustment"
) -> Optional[Dict[str, Any]]:
    """
    Tool: Adjusts quantity for a medicine (e.g. after receiving supplier order or damage).
    """
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not med:
        return None
    med.quantity_in_stock = max(0, med.quantity_in_stock + quantity_delta)
    db.commit()
    db.refresh(med)
    return get_medicine_risk_profile(db, med)


def get_inventory_summary_stats(db: Session, pharmacy_id: str) -> Dict[str, Any]:
    """
    Tool: Summarizes key inventory counts and category distributions.
    """
    medicines = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).all()
    total_items = len(medicines)
    total_cost = sum(m.quantity_in_stock * m.unit_cost_fcfa for m in medicines)
    total_retail = sum(m.quantity_in_stock * m.selling_price_fcfa for m in medicines)

    category_counts = {}
    for m in medicines:
        category_counts[m.category] = category_counts.get(m.category, 0) + 1

    return {
        "pharmacy_id": pharmacy_id,
        "total_sku_count": total_items,
        "total_stock_value_cost_fcfa": round(total_cost, 2),
        "total_stock_value_retail_fcfa": round(total_retail, 2),
        "category_distribution": category_counts
    }
