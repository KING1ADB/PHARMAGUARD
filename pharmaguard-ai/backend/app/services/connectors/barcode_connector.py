from datetime import date, datetime, timezone, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import Medicine, Inventory, SalesHistory, AgentActionLog


def lookup_medicine_by_barcode(barcode: str, pharmacy_id: str, db: Session) -> Dict[str, Any]:
    """
    Looks up a medicine SKU and live inventory by EAN-13, UPC, or DataMatrix barcode.
    """
    barcode_clean = barcode.strip()
    med = db.query(Medicine).filter(Medicine.barcode == barcode_clean).first()
    if not med:
        # Fallback: check if barcode matches Medicine ID
        med = db.query(Medicine).filter(Medicine.id == barcode_clean).first()

    if not med:
        return {
            "status": "NOT_FOUND",
            "barcode": barcode_clean,
            "message": f"No medicine registered with barcode {barcode_clean}."
        }

    inv = db.query(Inventory).filter(
        Inventory.medicine_id == med.id,
        Inventory.pharmacy_id == pharmacy_id
    ).first()

    return {
        "status": "FOUND",
        "barcode": barcode_clean,
        "medicine_id": med.id,
        "name": med.brand_names,
        "generic_name": med.generic_name,
        "category": med.category,
        "dosage_form": med.dosage_form,
        "current_stock": inv.quantity if inv else 0,
        "unit_sale_price_fcfa": inv.selling_price_fcfa if inv else 0.0,
        "expiry_date": inv.expiry_date.isoformat() if inv else None,
        "batch_number": inv.batch_number if inv else None
    }


def dispense_stock_by_barcode(
    barcode: str,
    quantity_dispensed: int,
    pharmacy_id: str,
    db: Session,
    patient_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Real-time POS Action:
    Deducts dispensed stock on physical barcode scan and creates transaction record in SalesHistory.
    """
    lookup = lookup_medicine_by_barcode(barcode, pharmacy_id, db)
    if lookup["status"] == "NOT_FOUND":
        return lookup

    med_id = lookup["medicine_id"]
    inv = db.query(Inventory).filter(
        Inventory.medicine_id == med_id,
        Inventory.pharmacy_id == pharmacy_id
    ).first()

    if not inv or inv.quantity < quantity_dispensed:
        return {
            "status": "INSUFFICIENT_STOCK",
            "medicine_id": med_id,
            "name": lookup["name"],
            "requested_quantity": quantity_dispensed,
            "current_stock": inv.quantity if inv else 0,
            "message": "Cannot dispense: requested quantity exceeds current on-shelf inventory."
        }

    inv.quantity -= quantity_dispensed

    # Record sales history transaction
    total_amount = quantity_dispensed * inv.selling_price_fcfa
    sale = SalesHistory(
        id=f"POS-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{barcode[:6]}",
        pharmacy_id=pharmacy_id,
        medicine_id=med_id,
        quantity=quantity_dispensed,
        unit_price_fcfa=inv.selling_price_fcfa,
        total_amount_fcfa=total_amount,
        customer_type=patient_id or "Walk-in Patient",
        timestamp=datetime.now(timezone.utc)
    )
    db.add(sale)
    db.commit()

    return {
        "status": "SUCCESS",
        "action": "DISPENSED",
        "barcode": barcode,
        "medicine_id": med_id,
        "name": lookup["name"],
        "quantity_dispensed": quantity_dispensed,
        "remaining_stock": inv.quantity,
        "total_amount_fcfa": total_amount,
        "transaction_id": sale.id
    }


def receive_batch_by_barcode(
    barcode: str,
    quantity_received: int,
    batch_number: str,
    expiry_date: date,
    unit_cost_fcfa: float,
    selling_price_fcfa: float,
    pharmacy_id: str,
    db: Session,
    supplier_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Receiving Bay Action:
    Scans incoming distributor shipment, maps barcode to medicine, and increments live inventory.
    """
    barcode_clean = barcode.strip()
    med = db.query(Medicine).filter(Medicine.barcode == barcode_clean).first()
    if not med:
        med = db.query(Medicine).filter(Medicine.id == barcode_clean).first()

    if not med:
        return {
            "status": "ERROR",
            "message": f"Medicine for barcode {barcode_clean} not found in catalog. Create medicine profile first."
        }

    inv = db.query(Inventory).filter(
        Inventory.medicine_id == med.id,
        Inventory.pharmacy_id == pharmacy_id
    ).first()

    if inv:
        inv.quantity += quantity_received
        inv.unit_cost_fcfa = unit_cost_fcfa
        inv.selling_price_fcfa = selling_price_fcfa
        inv.expiry_date = expiry_date
        inv.batch_number = batch_number
        if supplier_id:
            inv.supplier_id = supplier_id
    else:
        inv = Inventory(
            id=f"INV-{pharmacy_id}-{med.id}",
            pharmacy_id=pharmacy_id,
            medicine_id=med.id,
            supplier_id=supplier_id,
            quantity=quantity_received,
            unit_cost_fcfa=unit_cost_fcfa,
            selling_price_fcfa=selling_price_fcfa,
            expiry_date=expiry_date,
            batch_number=batch_number
        )
        db.add(inv)

    # Log receiving action
    audit = AgentActionLog(
        pharmacy_id=pharmacy_id,
        agent="BarcodeReceivingService",
        action="INVENTORY_BATCH_RECEIVED",
        reasoning=f"Received +{quantity_received} units of {med.brand_names} (Lot: {batch_number}, Exp: {expiry_date}).",
        confidence_score=1.0,
        approval_status="CONFIRMED"
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "action": "RECEIVED",
        "barcode": barcode_clean,
        "medicine_id": med.id,
        "name": med.brand_names,
        "quantity_received": quantity_received,
        "total_stock_now": inv.quantity,
        "batch_number": batch_number,
        "expiry_date": expiry_date.isoformat()
    }
