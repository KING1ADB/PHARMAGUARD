from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database.models import Inventory, Medicine, Pharmacy


def get_inventory(pharmacy_id: str, db: Session) -> List[Dict[str, Any]]:
    """
    Tool: Retrieve current pharmacy stock for all medicines.
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
            "name": med.name,
            "generic_name": med.generic_name,
            "category": med.category,
            "strength": med.strength,
            "form": med.form,
            "quantity": inv.quantity,
            "expiry_date": inv.expiry_date.isoformat(),
            "unit_cost_fcfa": inv.unit_cost_fcfa,
            "selling_price_fcfa": inv.selling_price_fcfa,
            "reorder_point": inv.reorder_point,
            "supplier_id": inv.supplier_id,
            "location_shelf": inv.location_shelf,
            "last_updated": inv.last_updated.isoformat() if inv.last_updated else None
        })
    return result


def query_stock_level(db: Session, query: str, pharmacy_id: str) -> List[Dict[str, Any]]:
    """
    Tool: Search inventory by brand name, generic molecule name, or category.
    """
    search_term = f"%{query.strip()}%"
    items = (
        db.query(Inventory, Medicine)
        .join(Medicine, Inventory.medicine_id == Medicine.id)
        .filter(
            Inventory.pharmacy_id == pharmacy_id,
            or_(
                Medicine.name.ilike(search_term),
                Medicine.generic_name.ilike(search_term),
                Medicine.category.ilike(search_term)
            )
        )
        .all()
    )

    result = []
    for inv, med in items:
        result.append({
            "inventory_id": inv.id,
            "medicine_id": med.id,
            "name": med.name,
            "generic_name": med.generic_name,
            "category": med.category,
            "strength": med.strength,
            "form": med.form,
            "quantity": inv.quantity,
            "expiry_date": inv.expiry_date.isoformat(),
            "unit_cost_fcfa": inv.unit_cost_fcfa,
            "selling_price_fcfa": inv.selling_price_fcfa,
            "location_shelf": inv.location_shelf,
            "supplier_id": inv.supplier_id
        })
    return result


def update_inventory_quantity(
    db: Session,
    medicine_id: str,
    pharmacy_id: str,
    quantity_delta: int,
    reason: str = "Adjustment"
) -> Optional[Dict[str, Any]]:
    """
    Tool: Adjusts quantity for a medicine in pharmacy inventory.
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
        "inventory_id": inv.id,
        "medicine_id": inv.medicine_id,
        "new_quantity": inv.quantity,
        "reason": reason
    }
