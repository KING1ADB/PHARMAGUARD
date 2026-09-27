from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...database.models.entities import Inventory, Medicine, User
from ...database.schemas.entities_schema import MedicineRiskDetail
from ...tools.inventory_tools.inventory_reader import get_current_inventory, analyze_stock_level
from ...security.jwt_rbac import get_current_active_user, require_role, UserRole
from ...services.connectors.csv_connector import import_pharmacy_inventory_csv
from ...services.connectors.excel_connector import import_pharmacy_inventory_excel
from ...services.connectors.barcode_connector import (
    lookup_medicine_by_barcode,
    dispense_stock_by_barcode,
    receive_batch_by_barcode
)

router = APIRouter(prefix="/inventory", tags=["Inventory & Real-World Data Connectors"])


class BarcodeDispenseRequest(BaseModel):
    barcode: str
    quantity: int = 1
    patient_id: Optional[str] = None


class BarcodeReceiveRequest(BaseModel):
    barcode: str
    quantity: int
    batch_number: str
    expiry_date: date
    unit_cost_fcfa: float
    selling_price_fcfa: float
    supplier_id: Optional[str] = None


@router.get("", response_model=List[MedicineRiskDetail], summary="List Live Pharmacy Inventory with Risk Metrics")
def list_inventory_with_risks(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Retrieves all pharmacy stock items with calculated shortage & expiry risks."""
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    items = get_current_inventory(target_pharmacy_id, db)
    return [analyze_stock_level(target_pharmacy_id, it["medicine_id"], db) for it in items]


@router.get("/search", response_model=List[MedicineRiskDetail], summary="Search Live Pharmacy Stock")
def search_stock(
    q: str = Query(..., description="Brand, generic name or category"),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Searches stock for a specific medicine by brand or generic name."""
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    items = get_current_inventory(target_pharmacy_id, db)
    q_low = q.lower()
    matching = [
        it for it in items
        if q_low in it["name"].lower()
        or q_low in it["generic_name"].lower()
        or q_low in (it["category"] or "").lower()
    ]
    return [analyze_stock_level(target_pharmacy_id, it["medicine_id"], db) for it in matching]


@router.post("/upload/csv", summary="Import Pharmacy Inventory from CSV")
async def upload_inventory_csv(
    file: UploadFile = File(...),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Connects real-world CSV inventory exports from pharmacy software (PharmaSys, WINPHARMA, etc.).
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv format.")

    content = await file.read()
    result = import_pharmacy_inventory_csv(
        file_content=content,
        pharmacy_id=target_pharmacy_id,
        db=db,
        filename=file.filename
    )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@router.post("/upload/excel", summary="Import Pharmacy Inventory from Excel (.xlsx / .xls)")
async def upload_inventory_excel(
    file: UploadFile = File(...),
    pharmacy_id: Optional[str] = None,
    sheet_name: Optional[str] = Query(None),
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Connects real-world Excel inventory workbooks from distributor or pharmacy records.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    fn = file.filename.lower()
    if not (fn.endswith(".xlsx") or fn.endswith(".xls")):
        raise HTTPException(status_code=400, detail="File must be an Excel workbook (.xlsx or .xls).")

    content = await file.read()
    result = import_pharmacy_inventory_excel(
        file_content=content,
        pharmacy_id=target_pharmacy_id,
        db=db,
        filename=file.filename,
        sheet_name=sheet_name
    )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@router.get("/barcode/{barcode}", summary="Lookup Medicine & Live Stock by Barcode")
def scan_barcode_lookup(
    barcode: str,
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Real-time Barcode Scanner Connector:
    Resolves EAN-13, UPC, or DataMatrix barcode to medicine catalog and live shelf inventory.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    result = lookup_medicine_by_barcode(barcode, target_pharmacy_id, db)
    if result.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/barcode/dispense", summary="Dispense Medicine & Deduct Stock by Barcode")
def scan_barcode_dispense(
    req: BarcodeDispenseRequest,
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Real-time POS Dispensing:
    Deducts dispensed stock on physical barcode scan and creates sale history transaction.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    result = dispense_stock_by_barcode(
        barcode=req.barcode,
        quantity_dispensed=req.quantity,
        pharmacy_id=target_pharmacy_id,
        db=db,
        patient_id=req.patient_id
    )

    if result.get("status") in ["NOT_FOUND", "INSUFFICIENT_STOCK"]:
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@router.post("/barcode/receive", summary="Receive Distributor Shipment by Barcode")
def scan_barcode_receive(
    req: BarcodeReceiveRequest,
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST, UserRole.ASSISTANT])),
    db: Session = Depends(get_db)
):
    """
    Receiving Bay Action:
    Scans incoming distributor shipment, maps barcode to medicine, and increments live inventory.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    result = receive_batch_by_barcode(
        barcode=req.barcode,
        quantity_received=req.quantity,
        batch_number=req.batch_number,
        expiry_date=req.expiry_date,
        unit_cost_fcfa=req.unit_cost_fcfa,
        selling_price_fcfa=req.selling_price_fcfa,
        pharmacy_id=target_pharmacy_id,
        db=db,
        supplier_id=req.supplier_id
    )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result
