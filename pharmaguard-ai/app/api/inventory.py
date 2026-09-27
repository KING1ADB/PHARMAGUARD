import io
import pandas as pd
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Medicine
from ..database.schemas import (
    MedicineResponse,
    MedicineRiskDetail,
    MedicineCreate,
    MedicineUpdate
)
from ..services.analysis import analyze_inventory_health, get_medicine_risk_profile
from ..tools.inventory_tools import query_stock_level

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


@router.get("", response_model=List[MedicineRiskDetail])
def get_all_inventory(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Retrieves all medicines with real-time stockout and expiry risk calculations."""
    medicines = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).all()
    return [get_medicine_risk_profile(db, med) for med in medicines]


@router.get("/search", response_model=List[MedicineRiskDetail])
def search_inventory(
    q: str = Query(..., description="Brand name, generic molecule name, or category"),
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Searches medicines by name or therapeutic class."""
    return query_stock_level(db, q, pharmacy_id)


@router.get("/health")
def get_inventory_health_report(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Returns comprehensive inventory health, critical stockouts, and capital at risk."""
    return analyze_inventory_health(db, pharmacy_id)


@router.post("", response_model=MedicineResponse)
def add_medicine(
    medicine: MedicineCreate,
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Adds a new medicine item to pharmacy inventory."""
    existing = db.query(Medicine).filter(Medicine.id == medicine.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Medicine ID already exists")

    new_med = Medicine(
        **medicine.model_dump(exclude={"pharmacy_id"}),
        pharmacy_id=pharmacy_id
    )
    db.add(new_med)
    db.commit()
    db.refresh(new_med)
    return new_med


@router.put("/{medicine_id}", response_model=MedicineResponse)
def update_medicine(
    medicine_id: str,
    updates: MedicineUpdate,
    db: Session = Depends(get_db)
):
    """Updates stock quantity, price, or reorder parameters for a medicine."""
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not med:
        raise HTTPException(status_code=404, detail="Medicine not found")

    for key, val in updates.model_dump(exclude_unset=True).items():
        setattr(med, key, val)

    db.commit()
    db.refresh(med)
    return med


@router.post("/upload-csv")
async def upload_inventory_csv(
    file: UploadFile = File(...),
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """
    Batch uploads or syncs inventory from a CSV spreadsheet (Excel/POS export).
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")

    required_columns = {"medicine_id", "name", "generic_name", "quantity_in_stock", "unit_cost_fcfa", "expiry_date"}
    if not required_columns.issubset(df.columns):
        missing = required_columns - set(df.columns)
        raise HTTPException(status_code=400, detail=f"Missing required CSV columns: {missing}")

    created_count = 0
    updated_count = 0

    for _, row in df.iterrows():
        med_id = str(row["medicine_id"])
        exp_date = datetime.strptime(str(row["expiry_date"]), "%Y-%m-%d").date()
        
        med = db.query(Medicine).filter(Medicine.id == med_id, Medicine.pharmacy_id == pharmacy_id).first()
        if med:
            med.quantity_in_stock = int(row["quantity_in_stock"])
            med.unit_cost_fcfa = float(row["unit_cost_fcfa"])
            med.selling_price_fcfa = float(row.get("selling_price_fcfa", med.selling_price_fcfa))
            med.expiry_date = exp_date
            updated_count += 1
        else:
            new_med = Medicine(
                id=med_id,
                pharmacy_id=pharmacy_id,
                name=str(row["name"]),
                generic_name=str(row["generic_name"]),
                category=str(row.get("category", "General")),
                dosage_form=str(row.get("dosage_form", "Tablet")),
                strength=str(row.get("strength", "")),
                batch_number=str(row.get("batch_number", "BATCH-DEFAULT")),
                quantity_in_stock=int(row["quantity_in_stock"]),
                unit_cost_fcfa=float(row["unit_cost_fcfa"]),
                selling_price_fcfa=float(row.get("selling_price_fcfa", float(row["unit_cost_fcfa"]) * 1.4)),
                reorder_point=int(row.get("reorder_point", 15)),
                expiry_date=exp_date,
                supplier_id=str(row.get("supplier_id", "SUP-001")),
                location_shelf=str(row.get("location_shelf", "General Shelf"))
            )
            db.add(new_med)
            created_count += 1

    db.commit()
    return {
        "status": "SUCCESS",
        "total_rows_processed": len(df),
        "created_records": created_count,
        "updated_records": updated_count
    }
