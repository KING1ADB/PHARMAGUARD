import io
import csv
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import Medicine, Inventory, Pharmacy, Supplier


HEADER_SYNONYMS = {
    "medicine_id": ["id", "code", "reference", "code_cip", "sku", "item_code", "medicine_id"],
    "brand_name": ["name", "brand_name", "designation", "nom", "produit", "nom_commercial", "article", "medicine_name"],
    "generic_name": ["generic_name", "dci", "molecules", "principe_actif", "generic"],
    "category": ["category", "famille", "classe_therapeutique", "categorie", "therapeutic_class"],
    "quantity": ["quantity", "stock", "quantite", "qty", "stock_actuel", "qte_en_stock", "current_stock", "stock_quantity", "on_hand"],
    "unit_cost_fcfa": ["unit_cost", "cost", "prix_achat", "unit_cost_fcfa", "pa_ht", "buying_price", "prix_fournisseur"],
    "selling_price_fcfa": ["selling_price", "price", "prix_vente", "unit_sale_price_fcfa", "pv_ttc", "retail_price"],
    "expiry_date": ["expiry_date", "date_peremption", "peremption", "exp_date", "expiry", "date_limite"],
    "batch_number": ["batch", "batch_number", "lot", "numero_lot", "num_lot", "batch_no"]
}


def find_matched_column(df_columns: List[str], target_field: str) -> Optional[str]:
    col_map = {col.strip().lower().replace(" ", "_"): col for col in df_columns}
    synonyms = HEADER_SYNONYMS.get(target_field, [target_field])
    for syn in synonyms:
        if syn in col_map:
            return col_map[syn]
    return None


def parse_date_flexibly(date_val: Any) -> date:
    if pd.isna(date_val):
        return date.today() + timedelta(days=365)
    if isinstance(date_val, (date, datetime)):
        return date_val.date() if isinstance(date_val, datetime) else date_val

    date_str = str(date_val).strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return date.today() + timedelta(days=365)


def import_pharmacy_inventory_csv(
    file_content: bytes,
    pharmacy_id: str,
    db: Session,
    filename: str = "import.csv"
) -> Dict[str, Any]:
    """
    Ingests live inventory batches from a CSV file into the database.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_content))
    except Exception as e:
        return {"status": "ERROR", "message": f"Failed to parse CSV file: {str(e)}"}

    if df.empty:
        return {"status": "ERROR", "message": "The CSV file is empty."}

    columns = list(df.columns)
    name_col = find_matched_column(columns, "brand_name")
    qty_col = find_matched_column(columns, "quantity")
    cost_col = find_matched_column(columns, "unit_cost_fcfa")
    price_col = find_matched_column(columns, "selling_price_fcfa")
    exp_col = find_matched_column(columns, "expiry_date")
    batch_col = find_matched_column(columns, "batch_number")
    id_col = find_matched_column(columns, "medicine_id")
    generic_col = find_matched_column(columns, "generic_name")
    cat_col = find_matched_column(columns, "category")

    if not name_col or not qty_col:
        return {
            "status": "ERROR",
            "message": f"Required columns (Medicine Name and Quantity) could not be detected. Found headers: {columns}"
        }

    imported_count = 0
    updated_count = 0

    for idx, row in df.iterrows():
        name_val = str(row[name_col]).strip()
        if not name_val or pd.isna(row[name_col]):
            continue

        med_id = str(row[id_col]).strip() if id_col and not pd.isna(row[id_col]) else f"MED-IMP-{idx+1:04d}"
        generic_val = str(row[generic_col]).strip() if generic_col and not pd.isna(row[generic_col]) else name_val
        cat_val = str(row[cat_col]).strip() if cat_col and not pd.isna(row[cat_col]) else "General Medicine"

        try:
            qty_val = int(row[qty_col]) if not pd.isna(row[qty_col]) else 0
        except (ValueError, TypeError):
            qty_val = 0

        try:
            cost_val = float(row[cost_col]) if cost_col and not pd.isna(row[cost_col]) else 1000.0
        except (ValueError, TypeError):
            cost_val = 1000.0

        try:
            price_val = float(row[price_col]) if price_col and not pd.isna(row[price_col]) else (cost_val * 1.3)
        except (ValueError, TypeError):
            price_val = cost_val * 1.3

        expiry_val = parse_date_flexibly(row[exp_col]) if exp_col else (date.today() + timedelta(days=365))
        batch_val = str(row[batch_col]).strip() if batch_col and not pd.isna(row[batch_col]) else f"LOT-{date.today().year}-{idx+1:03d}"

        # 1. Upsert Medicine in catalog
        med = db.query(Medicine).filter(Medicine.id == med_id).first()
        if not med:
            med = Medicine(
                id=med_id,
                brand_names=name_val,
                generic_name=generic_val,
                category=cat_val,
                dosage_form="Tablet"
            )
            db.add(med)

        # 2. Upsert Inventory Item
        inv = db.query(Inventory).filter(
            Inventory.pharmacy_id == pharmacy_id,
            Inventory.medicine_id == med_id
        ).first()

        if inv:
            inv.quantity = qty_val
            inv.unit_cost_fcfa = cost_val
            inv.selling_price_fcfa = price_val
            inv.expiry_date = expiry_val
            inv.batch_number = batch_val
            updated_count += 1
        else:
            new_inv = Inventory(
                id=f"INV-{pharmacy_id}-{med_id}",
                pharmacy_id=pharmacy_id,
                medicine_id=med_id,
                quantity=qty_val,
                unit_cost_fcfa=cost_val,
                selling_price_fcfa=price_val,
                expiry_date=expiry_val,
                batch_number=batch_val
            )
            db.add(new_inv)
            imported_count += 1

    db.commit()

    return {
        "status": "SUCCESS",
        "filename": filename,
        "pharmacy_id": pharmacy_id,
        "total_rows_processed": len(df),
        "new_items_created": imported_count,
        "existing_items_updated": updated_count
    }
