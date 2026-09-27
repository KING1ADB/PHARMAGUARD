import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

# Determine database path relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/pharmaguard.db")

# SQLite connection args
connect_args = {"check_same_thread": False} if DB_PATH.startswith("sqlite") else {}

engine = create_engine(DB_PATH, echo=False, connect_args=connect_args)
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
    from .models import Medicine, Supplier, SaleRecord, Pharmacy

    # Check if pharmacy exists
    if not db.query(Pharmacy).first():
        default_pharmacy = Pharmacy(
            id=os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001"),
            name=os.getenv("DEFAULT_PHARMACY_NAME", "Pharmacie du Centre - Douala"),
            city=os.getenv("DEFAULT_CITY", "Douala"),
            country=os.getenv("DEFAULT_COUNTRY", "Cameroon"),
            phone="+237 679 000 111",
            email="contact@pharmacieducentre.cm",
            is_connected_to_network=True
        )
        db.add(default_pharmacy)
        db.commit()

    # Seed Suppliers
    suppliers_csv = BASE_DIR / "data" / "suppliers.csv"
    if suppliers_csv.exists() and db.query(Supplier).count() == 0:
        df_sup = pd.read_csv(suppliers_csv)
        for _, row in df_sup.iterrows():
            sup = Supplier(
                id=str(row["supplier_id"]),
                name=str(row["name"]),
                contact_person=str(row["contact_person"]),
                phone=str(row["phone"]),
                email=str(row["email"]),
                city=str(row["city"]),
                address=str(row["address"]),
                lead_time_days=int(row["lead_time_days"]),
                minimum_order_value_fcfa=float(row["minimum_order_value_fcfa"]),
                reliability_score=float(row["reliability_score"]),
                payment_terms=str(row["payment_terms"])
            )
            db.add(sup)
        db.commit()

    # Seed Medicines / Inventory
    inventory_csv = BASE_DIR / "data" / "inventory.csv"
    if inventory_csv.exists() and db.query(Medicine).count() == 0:
        df_inv = pd.read_csv(inventory_csv)
        for _, row in df_inv.iterrows():
            exp_date = datetime.strptime(str(row["expiry_date"]), "%Y-%m-%d").date()
            med = Medicine(
                id=str(row["medicine_id"]),
                pharmacy_id=os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001"),
                name=str(row["name"]),
                generic_name=str(row["generic_name"]),
                category=str(row["category"]),
                dosage_form=str(row["dosage_form"]),
                strength=str(row["strength"]),
                batch_number=str(row["batch_number"]),
                quantity_in_stock=int(row["quantity_in_stock"]),
                unit_cost_fcfa=float(row["unit_cost_fcfa"]),
                selling_price_fcfa=float(row["selling_price_fcfa"]),
                reorder_point=int(row["reorder_point"]),
                expiry_date=exp_date,
                supplier_id=str(row["supplier_id"]),
                location_shelf=str(row.get("location_shelf", "General Shelf"))
            )
            db.add(med)
        db.commit()

    # Seed Sales History
    sales_csv = BASE_DIR / "data" / "sales.csv"
    if sales_csv.exists() and db.query(SaleRecord).count() == 0:
        df_sales = pd.read_csv(sales_csv)
        for _, row in df_sales.iterrows():
            sale_date = datetime.strptime(str(row["date"]), "%Y-%m-%d").date()
            sale = SaleRecord(
                id=str(row["sale_id"]),
                pharmacy_id=os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001"),
                medicine_id=str(row["medicine_id"]),
                date=sale_date,
                quantity_sold=int(row["quantity_sold"]),
                unit_price_fcfa=float(row["unit_price_fcfa"]),
                total_amount_fcfa=float(row["total_amount_fcfa"]),
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
