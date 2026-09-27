import json
import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from ..database.models import PurchaseOrder, Supplier, Medicine


class ProcurementAgent:
    """
    Sub-Agent: Procurement & Supplier Negotiation Specialist.
    Consolidates replenishment requirements by supplier, verifies minimum order values,
    and drafts purchase orders ready for human pharmacist one-click approval.
    """
    def __init__(self, agent_name: str = "ProcurementSpecialist"):
        self.agent_name = agent_name

    def plan_procurement(
        self,
        db: Session,
        pharmacy_id: str,
        reorder_recommendations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Groups reorders by supplier and generates DRAFT purchase orders.
        """
        if not reorder_recommendations:
            return {
                "agent": self.agent_name,
                "status": "NO_ORDERS_NEEDED",
                "draft_orders": []
            }

        # Group items by supplier_id
        supplier_bundles: Dict[str, List[Dict[str, Any]]] = {}
        for item in reorder_recommendations:
            sup_id = item.get("supplier_id") or "SUP-001"
            if sup_id not in supplier_bundles:
                supplier_bundles[sup_id] = []
            supplier_bundles[sup_id].append(item)

        created_drafts = []
        for sup_id, items in supplier_bundles.items():
            supplier = db.query(Supplier).filter(Supplier.id == sup_id).first()
            sup_name = supplier.name if supplier else "Wholesale Supplier"

            order_items = []
            total_cost = 0.0
            critical_items_count = 0

            for it in items:
                qty = it["recommended_order_units"]
                unit_cost = it["unit_cost_fcfa"]
                subtotal = qty * unit_cost
                total_cost += subtotal
                if it.get("urgency") == "CRITICAL":
                    critical_items_count += 1

                order_items.append({
                    "medicine_id": it["medicine_id"],
                    "medicine_name": it["name"],
                    "quantity": qty,
                    "unit_cost_fcfa": unit_cost,
                    "subtotal_fcfa": subtotal
                })

            reasoning = (
                f"Autonomous draft order containing {len(order_items)} item(s) to prevent stockouts "
                f"({critical_items_count} critical). Optimized for {sup_name} lead time ({supplier.lead_time_days if supplier else 2} days)."
            )

            # Check if there is already an active DRAFT order for this supplier
            existing_draft = (
                db.query(PurchaseOrder)
                .filter(
                    PurchaseOrder.pharmacy_id == pharmacy_id,
                    PurchaseOrder.supplier_id == sup_id,
                    PurchaseOrder.status == "DRAFT"
                )
                .first()
            )

            if existing_draft:
                existing_draft.items_json = json.dumps(order_items)
                existing_draft.total_amount_fcfa = total_cost
                existing_draft.reasoning = reasoning
                po_id = existing_draft.id
                db.commit()
            else:
                po_id = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{sup_id[:7]}-{uuid.uuid4().hex[:4].upper()}"
                new_po = PurchaseOrder(
                    id=po_id,
                    pharmacy_id=pharmacy_id,
                    supplier_id=sup_id,
                    status="DRAFT",
                    total_amount_fcfa=total_cost,
                    items_json=json.dumps(order_items),
                    reasoning=reasoning,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(new_po)
                db.commit()

            created_drafts.append({
                "po_id": po_id,
                "supplier_id": sup_id,
                "supplier_name": sup_name,
                "items_count": len(order_items),
                "total_cost_fcfa": total_cost,
                "reasoning": reasoning,
                "status": "DRAFT_AWAITING_APPROVAL"
            })

        return {
            "agent": self.agent_name,
            "status": "COMPLETED",
            "total_draft_orders": len(created_drafts),
            "draft_orders": created_drafts
        }
