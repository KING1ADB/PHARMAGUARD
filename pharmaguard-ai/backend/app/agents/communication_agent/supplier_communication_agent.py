import uuid
import json
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import (
    Pharmacy,
    Supplier,
    PurchaseOrder,
    AgentActionLog,
    AgentMemory
)
from ...memory.long_term.episodic_memory import EpisodicMemoryManager
from ...memory.short_term.working_memory import session_working_memory


class SupplierCommunicationAgent:
    """
    PharmaGuard Supplier Communication Agent (Phase 3).
    
    Responsibilities:
    - Generates professional pharmaceutical purchase orders with regulatory compliance fields.
    - Strictly enforces approval gate: only dispatches orders approved by authorized pharmacists.
    - Dispatches purchase requests via Email, WhatsApp Business, or EDI API.
    - Ingests and processes distributor acknowledgment responses (CONFIRMED, OUT_OF_STOCK, DELAYED).
    - Continuously updates supplier reliability scores and episodic memory.
    """
    def __init__(self, agent_name: str = "SupplierCommunicationAgent"):
        self.agent_name = agent_name

    def generate_purchase_order_document(self, po_id: str, db: Session) -> Dict[str, Any]:
        """
        Formats a formal, professional purchase order document ready for transmission.
        """
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if not po:
            return {"status": "ERROR", "message": f"Purchase order {po_id} not found."}

        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == po.pharmacy_id).first()
        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()

        items = po.items
        pharmacy_name = pharmacy.organization_name if pharmacy else "Licensed Community Pharmacy"
        pharmacy_loc = pharmacy.location if pharmacy else "Douala, Cameroon"
        supplier_name = supplier.name if supplier else "Wholesale Distributor"
        supplier_email = supplier.email if supplier else "orders@distributor.cm"

        # Format items table
        item_lines = []
        for idx, it in enumerate(items, 1):
            item_lines.append(
                f"{idx}. {it.get('medicine_name', it.get('name', 'SKU'))} | "
                f"Qty: {it['quantity']} units | "
                f"Unit Price: {it['unit_cost_fcfa']:,.0f} FCFA | "
                f"Subtotal: {it['subtotal_fcfa']:,.0f} FCFA"
            )

        po_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"OFFICIAL PURCHASE ORDER: {po.id}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"FROM: {pharmacy_name}\n"
            f"LOCATION: {pharmacy_loc}\n"
            f"DATE: {po.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"TO: {supplier_name} ({supplier_email})\n"
            f"PAYMENT TERMS: {supplier.payment_terms if supplier else '30 Days Net'}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ORDERED ITEMS:\n"
            + "\n".join(item_lines) + "\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"TOTAL ORDER VALUE: {po.total_amount_fcfa:,.0f} FCFA\n"
            f"AUTHORIZED BY: {po.approved_by or 'Pending Verification'}\n"
            f"DELIVERY REQUIREMENT: Within {supplier.delivery_time if supplier else 2} business days\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Generated autonomously by PharmaGuard AI Platform\n"
        )

        return {
            "status": "SUCCESS",
            "po_id": po.id,
            "pharmacy_name": pharmacy_name,
            "supplier_name": supplier_name,
            "supplier_email": supplier_email,
            "total_amount_fcfa": po.total_amount_fcfa,
            "items_count": len(items),
            "formatted_document_text": po_text
        }

    def dispatch_approved_order(
        self,
        po_id: str,
        channel: str = "EMAIL",
        db: Session = None,
        dispatch_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Dispatches an approved purchase order to the wholesale distributor.
        Enforces human approval check: orders in DRAFT cannot be dispatched.
        """
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if not po:
            return {"status": "ERROR", "message": f"Purchase order {po_id} not found."}

        if po.status != "APPROVED":
            return {
                "status": "ERROR",
                "message": f"Cannot dispatch order with status '{po.status}'. Pharmacist approval is required."
            }

        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
        doc = self.generate_purchase_order_document(po_id, db)

        # Update order status
        po.status = "DISPATCHED"
        po.dispatch_channel = channel.upper()
        po.dispatched_at = datetime.now(timezone.utc)
        po.supplier_response_status = "PENDING_SUPPLIER_CONFIRMATION"
        po.tracking_reference = f"TRK-{uuid.uuid4().hex[:8].upper()}"
        db.commit()

        # Audit Trail
        audit = AgentActionLog(
            pharmacy_id=po.pharmacy_id,
            agent=self.agent_name,
            action="PURCHASE_ORDER_DISPATCHED",
            reasoning=(
                f"Dispatched PO {po.id} to supplier {supplier.name if supplier else po.supplier_id} "
                f"via {channel.upper()}. Tracking ref: {po.tracking_reference}."
            ),
            confidence_score=1.0,
            approval_status="DISPATCHED"
        )
        db.add(audit)
        db.commit()

        session_working_memory.log_step("SUPPLIER_DISPATCH_COMPLETE", {
            "po_id": po.id,
            "channel": channel,
            "tracking_ref": po.tracking_reference
        })

        return {
            "status": "SUCCESS",
            "po_id": po.id,
            "order_status": po.status,
            "channel": channel.upper(),
            "recipient": supplier.email if supplier else "supplier@distributor.cm",
            "tracking_reference": po.tracking_reference,
            "dispatched_at": po.dispatched_at.isoformat(),
            "document_preview": doc["formatted_document_text"]
        }

    def record_supplier_response(
        self,
        po_id: str,
        response_status: str,  # CONFIRMED, OUT_OF_STOCK, PARTIAL_DELIVERY, DELIVERED
        db: Session,
        actual_delivery_days: Optional[int] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes distributor feedback and dynamically updates supplier reliability scoring.
        """
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        if not po:
            return {"status": "ERROR", "message": f"Purchase order {po_id} not found."}

        supplier = db.query(Supplier).filter(Supplier.id == po.supplier_id).first()
        valid_statuses = ["CONFIRMED", "OUT_OF_STOCK", "PARTIAL_DELIVERY", "DELIVERED", "DELAYED"]
        status_clean = response_status.upper()
        if status_clean not in valid_statuses:
            status_clean = "CONFIRMED"

        po.supplier_response_status = status_clean
        if status_clean == "DELIVERED":
            po.status = "DELIVERED"
            po.actual_delivery_date = date.today()

        # Update supplier reliability score
        if supplier:
            target_lead_time = supplier.delivery_time
            if status_clean == "DELIVERED" and actual_delivery_days is not None:
                if actual_delivery_days <= target_lead_time:
                    event_score = 1.0  # Perfect on-time fulfillment
                else:
                    delay = actual_delivery_days - target_lead_time
                    event_score = max(0.4, 1.0 - (delay * 0.1))
            elif status_clean == "OUT_OF_STOCK":
                event_score = 0.3  # Supply failure penalty
            elif status_clean == "PARTIAL_DELIVERY":
                event_score = 0.7  # Partial fulfillment
            elif status_clean == "CONFIRMED":
                event_score = 0.95
            else:
                event_score = 0.85

            # Exponential Moving Average update: 85% previous + 15% new event
            prev_score = supplier.reliability_score or 0.90
            new_score = round((0.85 * prev_score) + (0.15 * event_score), 3)
            supplier.reliability_score = new_score

            # Log to Episodic Long-Term Memory
            EpisodicMemoryManager.record_decision_feedback(
                pharmacy_id=po.pharmacy_id,
                memory_type="SUPPLIER_RELIABILITY",
                feedback_data={
                    "supplier_id": supplier.id,
                    "supplier_name": supplier.name,
                    "po_id": po.id,
                    "event": status_clean,
                    "event_score": event_score,
                    "previous_score": prev_score,
                    "updated_score": new_score,
                    "notes": notes or "Distributor response logged"
                },
                confidence=1.0,
                db=db
            )

        db.commit()

        return {
            "status": "SUCCESS",
            "po_id": po.id,
            "supplier_id": supplier.id if supplier else po.supplier_id,
            "response_status": status_clean,
            "supplier_updated_reliability": supplier.reliability_score if supplier else 0.90,
            "notes": notes or "N/A"
        }


# Singleton instance of Supplier Communication Agent
supplier_comm_agent = SupplierCommunicationAgent()
