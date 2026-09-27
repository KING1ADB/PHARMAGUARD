import io
import pandas as pd
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Inventory, Medicine
from ..database.schemas import (
    MedicineResponse,
    MedicineRiskDetail,
    MedicineCreate,
    MedicineUpdate
)
from ..tools.inventory_tools import get_inventory, query_stock_level
from ..tools.risk_tools import calculate_all_inventory_risks, calculate_stock_risk

router = APIRouter(prefix="/inventory", tags=["Inventory Management"])


@router.get("", response_model=List[MedicineRiskDetail])
def get_all_inventory(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Retrieves all pharmacy inventory with risk metrics."""
    return calculate_all_inventory_risks(pharmacy_id, db)


@router.get("/search", response_model=List[MedicineRiskDetail])
def search_inventory(
    q: str = Query(..., description="Brand name, generic molecule name, or category"),
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Searches medicines by name or therapeutic class."""
    matches = query_stock_level(db, q, pharmacy_id)
    return [calculate_stock_risk(m["medicine_id"], db, pharmacy_id) for m in matches]


@router.get("/risks")
def get_inventory_risks(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """Returns comprehensive inventory risks, stockout coverage, and supplier comparisons."""
    return calculate_all_inventory_risks(pharmacy_id, db)
