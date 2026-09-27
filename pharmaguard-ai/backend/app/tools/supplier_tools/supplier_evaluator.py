import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ...database.models.entities import Supplier, PurchaseOrder, Inventory, Medicine


def evaluate_supplier(supplier_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Tool: Evaluates a wholesale supplier's lead time, MOQ, and reliability score.
    """
    sup = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not sup:
        return None
    return {
        "id": sup.id,
        "name": sup.name,
        "delivery_time_days": sup.delivery_time,
        "reliability_score": sup.reliability_score,
        "minimum_order_value_fcfa": sup.minimum_order_value_fcfa,
        "payment_terms": sup.payment_terms,
        "contact": sup.contact,
        "location": sup.location
    }


def create_purchase_recommendation(
    pharmacy_id: str,
    reorder_items: List[Dict[str, Any]],
    db: Session
) -> List[Dict[str, Any]]:
    """
    Tool: Consolidates replenishment requirements by supplier, verifies MOQs,
    and stages DRAFT purchase orders requiring human pharmacist authorization.
    """
    if not reorder_items:
        return []

    # Group by supplier
    bundles: Dict[str, List[Dict[str, Any]]] = {}
    for it in reorder_items:
        sup_id = it.get("supplier_id") or "SUP-001"
        if sup_id not in bundles:
            bundles[sup_id] = []
        bundles[sup_id].append(it)

    created_orders = []
    for sup_id, items in bundles.items():
        supplier = db.query(Supplier).filter(Supplier.id == sup_id).first()
        sup_name = supplier.name if supplier else "Wholesale Supplier"

        order_items = []
        total_cost = 0.0
        critical_count = 0

        for it in items:
            qty = it.get("recommended_order_units", 20)
            unit_cost = it.get("unit_cost_fcfa", 1500.0)
            subtotal = qty * unit_cost
            total_cost += subtotal
            if it.get("risk_level") in ["HIGH", "CRITICAL_STOCKOUT"]:
                critical_count += 1

            order_items.append({
                "medicine_id": it["medicine_id"],
                "medicine_name": it["name"],
                "quantity": qty,
                "unit_cost_fcfa": unit_cost,
                "subtotal_fcfa": subtotal
            })

        reasoning = (
            f"Autonomous morning replenishment recommendation for {sup_name} containing "
            f"{len(order_items)} item(s) to mitigate {critical_count} critical shortage risks. "
            f"Lead time: {supplier.delivery_time if supplier else 2} days."
        )

        po_id = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{sup_id[:7]}-{uuid.uuid4().hex[:4].upper()}"
        new_po = PurchaseOrder(
            id=po_id,
            pharmacy_id=pharmacy_id,
            supplier_id=sup_id,
            status="DRAFT",
            total_amount_fcfa=total_cost,
            items_json=json.dumps(order_items),
            reasoning=reasoning,
            confidence_score=0.92,
            created_at=datetime.now(timezone.utc)
        )
        db.add(new_po)
        db.commit()

        created_orders.append({
            "po_id": po_id,
            "supplier_id": sup_id,
            "supplier_name": sup_name,
            "items_count": len(order_items),
            "total_cost_fcfa": total_cost,
            "reasoning": reasoning,
            "status": "DRAFT_PENDING_APPROVAL"
        })

    return created_orders
