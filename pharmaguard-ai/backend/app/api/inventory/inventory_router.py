import io
import pandas as pd
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...database.models.entities import Inventory, Medicine
from ...database.schemas.entities_schema import MedicineRiskDetail, InventoryUpdate
from ...tools.inventory_tools.inventory_reader import get_current_inventory, analyze_stock_level
from ...security.jwt_rbac import get_current_user_payload

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


@router.get("", response_model=List[MedicineRiskDetail])
def list_inventory_with_risks(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_payload)
):
    """Retrieves all pharmacy stock items with calculated shortage & expiry risks."""
    pharmacy_id = user.get("pharmacy_id", "PHARM-DLA-001")
    items = get_current_inventory(pharmacy_id, db)
    return [analyze_stock_level(pharmacy_id, it["medicine_id"], db) for it in items]


@router.get("/search", response_model=List[MedicineRiskDetail])
def search_stock(
    q: str = Query(..., description="Brand or generic name"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_payload)
):
    """Searches stock for a specific medicine."""
    pharmacy_id = user.get("pharmacy_id", "PHARM-DLA-001")
    items = get_current_inventory(pharmacy_id, db)
    matching = [it for it in items if q.lower() in it["name"].lower() or q.lower() in it["generic_name"].lower()]
    return [analyze_stock_level(pharmacy_id, it["medicine_id"], db) for it in matching]


@router.post("/ingest")
async def ingest_inventory_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user_payload)
):
    """
    Real-world inventory ingestion from CSV (POS/Excel export).
    """
    pharmacy_id = user.get("pharmacy_id", "PHARM-DLA-001")
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    updated = 0
    created = 0

    for _, row in df.iterrows():
        med_id = str(row["medicine_id"])
        exp_date = datetime.strptime(str(row["expiry_date"]), "%Y-%m-%d").date()

        med = db.query(Medicine).filter(Medicine.id == med_id).first()
        if not med:
            med = Medicine(
                id=med_id,
                generic_name=str(row["generic_name"]),
                brand_names=str(row.get("name", row["generic_name"])),
                category=str(row.get("category", "General")),
                strength=str(row.get("strength", "")),
                dosage_form=str(row.get("form", "Tablet"))
            )
            db.add(med)
            db.flush()

        inv = db.query(Inventory).filter(Inventory.medicine_id == med_id, Inventory.pharmacy_id == pharmacy_id).first()
        if inv:
            inv.quantity = int(row["quantity"])
            inv.expiry_date = exp_date
            inv.unit_cost_fcfa = float(row.get("unit_cost_fcfa", inv.unit_cost_fcfa))
            updated += 1
        else:
            inv = Inventory(
                id=f"INV-{med_id}",
                pharmacy_id=pharmacy_id,
                medicine_id=med_id,
                quantity=int(row["quantity"]),
                expiry_date=exp_date,
                unit_cost_fcfa=float(row.get("unit_cost_fcfa", 0.0)),
                selling_price_fcfa=float(row.get("selling_price_fcfa", 0.0)),
                reorder_threshold=int(row.get("reorder_threshold", 15)),
                supplier_id=str(row.get("supplier_id", "SUP-001"))
            )
            db.add(inv)
            created += 1

    db.commit()
    return {
        "status": "SUCCESS",
        "records_ingested": len(df),
        "created": created,
        "updated": updated
    }
