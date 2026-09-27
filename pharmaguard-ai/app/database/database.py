import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/pharmaguard.db")

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_data_from_csv(db: Session):
    """Seed initial data from data/*.csv if tables are empty."""
    import pandas as pd
    from datetime import datetime
    from .models import Pharmacy, Medicine, Inventory, Supplier, SalesHistory

    # 1. Seed Pharmacy
    pharmacy_id = os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001")
    if not db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first():
        default_pharmacy = Pharmacy(
            id=pharmacy_id,
            name=os.getenv("DEFAULT_PHARMACY_NAME", "Pharmacie du Centre - Douala"),
            location=f"{os.getenv('DEFAULT_CITY', 'Douala')}, {os.getenv('DEFAULT_COUNTRY', 'Cameroon')}",
            contact="+237 679 000 111 / contact@pharmacieducentre.cm"
        )
        db.add(default_pharmacy)
        db.commit()

    # 2. Seed Suppliers
    suppliers_csv = BASE_DIR / "data" / "suppliers.csv"
    if suppliers_csv.exists() and db.query(Supplier).count() == 0:
        df_sup = pd.read_csv(suppliers_csv)
        for _, row in df_sup.iterrows():
            sup = Supplier(
                id=str(row["supplier_id"]),
                name=str(row["name"]),
                delivery_time=int(row.get("delivery_time", row.get("lead_time_days", 2))),
                reliability_score=float(row.get("reliability_score", 0.90)),
                contact=str(row.get("contact", row.get("contact_person", ""))),
                phone=str(row.get("phone", "")),
                email=str(row.get("email", "")),
                location=str(row.get("location", row.get("address", "Douala"))),
                minimum_order_value_fcfa=float(row.get("minimum_order_value_fcfa", 50000.0)),
                payment_terms=str(row.get("payment_terms", "30 Days Net"))
            )
            db.add(sup)
        db.commit()

    # 3. Seed Medicines & Inventory
    inventory_csv = BASE_DIR / "data" / "inventory.csv"
    if inventory_csv.exists() and db.query(Medicine).count() == 0:
        df_inv = pd.read_csv(inventory_csv)
        for _, row in df_inv.iterrows():
            med_id = str(row["medicine_id"])
            exp_date = datetime.strptime(str(row["expiry_date"]), "%Y-%m-%d").date()

            # Create catalog medicine if missing
            med = db.query(Medicine).filter(Medicine.id == med_id).first()
            if not med:
                med = Medicine(
                    id=med_id,
                    name=str(row["name"]),
                    generic_name=str(row["generic_name"]),
                    category=str(row.get("category", "General")),
                    strength=str(row.get("strength", "")),
                    form=str(row.get("form", row.get("dosage_form", "Tablet")))
                )
                db.add(med)
                db.flush()

            # Create inventory record
            inv = Inventory(
                id=f"INV-{med_id}",
                pharmacy_id=pharmacy_id,
                medicine_id=med_id,
                quantity=int(row.get("quantity", row.get("quantity_in_stock", 0))),
                expiry_date=exp_date,
                unit_cost_fcfa=float(row.get("unit_cost_fcfa", 0.0)),
                selling_price_fcfa=float(row.get("selling_price_fcfa", 0.0)),
                reorder_point=int(row.get("reorder_point", 15)),
                batch_number=str(row.get("batch_number", "BATCH-DEFAULT")),
                supplier_id=str(row.get("supplier_id", "SUP-001")),
                location_shelf=str(row.get("location_shelf", "General Shelf"))
            )
            db.add(inv)
        db.commit()

    # 4. Seed Sales History
    sales_csv = BASE_DIR / "data" / "sales.csv"
    if sales_csv.exists() and db.query(SalesHistory).count() == 0:
        df_sales = pd.read_csv(sales_csv)
        for _, row in df_sales.iterrows():
            sale_date = datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
            sale = SalesHistory(
                id=str(row["sale_id"]),
                pharmacy_id=pharmacy_id,
                medicine_id=str(row["medicine_id"]),
                quantity_sold=int(row["quantity_sold"]),
                date=sale_date,
                unit_price_fcfa=float(row.get("unit_price_fcfa", 0.0)),
                total_amount_fcfa=float(row.get("total_amount_fcfa", 0.0)),
                customer_type=str(row.get("customer_type", "Walk-in Patient"))
            )
            db.add(sale)
        db.commit()


def init_db():
    """Initializes the database schema and seeds initial data."""
    from . import models
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data_from_csv(db)
    finally:
        db.close()
