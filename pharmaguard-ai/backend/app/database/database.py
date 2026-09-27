import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
from .models.entities import (
    Base,
    Pharmacy,
    User,
    Medicine,
    Supplier,
    Inventory,
    SalesHistory,
    AgentMemory
)
from ..security.jwt_rbac import hash_password

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/pharmaguard_prod.db")
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency for injecting transactional database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_production_data(db: Session):
    """Auto-seeds baseline Douala pharmacy master data if empty."""
    import pandas as pd
    pharmacy_id = os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001")

    # 1. Seed Pharmacy
    if not db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first():
        pharm = Pharmacy(
            id=pharmacy_id,
            organization_name=os.getenv("DEFAULT_PHARMACY_NAME", "Pharmacie du Centre - Douala"),
            address="Akwa Boulevard de la Liberté, B.P. 1240",
            location=f"{os.getenv('DEFAULT_CITY', 'Douala')}, {os.getenv('DEFAULT_COUNTRY', 'Cameroon')}",
            contact_information="+237 679 000 111 / contact@pharmacieducentre.cm",
            verification_status="VERIFIED"
        )
        db.add(pharm)
        db.commit()

    # 2. Seed Users
    if db.query(User).count() == 0:
        pharmacist_user = User(
            id="USR-PHARM-001",
            pharmacy_id=pharmacy_id,
            name="Dr. Jean-Paul Mbarga",
            email="pharmacist@pharmaguard.cm",
            phone="+237 677 123 456",
            password_hash=hash_password("PharmaGuard2026!"),
            role="PHARMACIST",
            permissions='["READ", "WRITE", "APPROVE_ORDERS", "AUDIT"]'
        )
        owner_user = User(
            id="USR-OWNER-001",
            pharmacy_id=pharmacy_id,
            name="Mme. Sandrine Ngo",
            email="owner@pharmaguard.cm",
            phone="+237 699 234 567",
            password_hash=hash_password("OwnerSecure2026!"),
            role="OWNER",
            permissions='["ALL"]'
        )
        db.add(pharmacist_user)
        db.add(owner_user)
        db.commit()

    # 3. Seed Suppliers
    suppliers_csv = DATA_DIR / "suppliers.csv"
    if suppliers_csv.exists() and db.query(Supplier).count() == 0:
        df_sup = pd.read_csv(suppliers_csv)
        for _, row in df_sup.iterrows():
            sup = Supplier(
                id=str(row["supplier_id"]),
                name=str(row["name"]),
                contact=str(row.get("contact", row.get("contact_person", ""))),
                delivery_time=int(row.get("delivery_time", row.get("lead_time_days", 2))),
                reliability_score=float(row.get("reliability_score", 0.90)),
                minimum_order_value_fcfa=float(row.get("minimum_order_value_fcfa", 50000.0)),
                payment_terms=str(row.get("payment_terms", "30 Days Net")),
                phone=str(row.get("phone", "")),
                email=str(row.get("email", "")),
                location=str(row.get("location", row.get("address", "Douala")))
            )
            db.add(sup)
        db.commit()

    # 4. Seed Medicines & Inventory
    inventory_csv = DATA_DIR / "inventory.csv"
    if inventory_csv.exists() and db.query(Medicine).count() == 0:
        df_inv = pd.read_csv(inventory_csv)
        for _, row in df_inv.iterrows():
            med_id = str(row["medicine_id"])
            exp_date = datetime.strptime(str(row["expiry_date"]), "%Y-%m-%d").date()

            med = db.query(Medicine).filter(Medicine.id == med_id).first()
            if not med:
                med = Medicine(
                    id=med_id,
                    generic_name=str(row["generic_name"]),
                    brand_names=str(row["name"]),
                    category=str(row.get("category", "General")),
                    strength=str(row.get("strength", "")),
                    dosage_form=str(row.get("form", row.get("dosage_form", "Tablet")))
                )
                db.add(med)
                db.flush()

            inv = Inventory(
                id=f"INV-{med_id}",
                pharmacy_id=pharmacy_id,
                medicine_id=med_id,
                supplier_id=str(row.get("supplier_id", "SUP-001")),
                quantity=int(row.get("quantity", row.get("quantity_in_stock", 0))),
                reorder_threshold=int(row.get("reorder_threshold", row.get("reorder_point", 15))),
                expiry_date=exp_date,
                unit_cost_fcfa=float(row.get("unit_cost_fcfa", 0.0)),
                selling_price_fcfa=float(row.get("selling_price_fcfa", 0.0)),
                batch_number=str(row.get("batch_number", "BATCH-DEFAULT")),
                location_shelf=str(row.get("location_shelf", "General Shelf"))
            )
            db.add(inv)
        db.commit()

    # 5. Seed Sales History
    sales_csv = DATA_DIR / "sales.csv"
    if sales_csv.exists() and db.query(SalesHistory).count() == 0:
        df_sales = pd.read_csv(sales_csv)
        for _, row in df_sales.iterrows():
            sale_date = datetime.strptime(str(row["date"]), "%Y-%m-%d")
            sale = SalesHistory(
                id=str(row["sale_id"]),
                pharmacy_id=pharmacy_id,
                medicine_id=str(row["medicine_id"]),
                quantity=int(row.get("quantity", row.get("quantity_sold", 1))),
                unit_price_fcfa=float(row.get("unit_price_fcfa", 0.0)),
                total_amount_fcfa=float(row.get("total_amount_fcfa", 0.0)),
                customer_type=str(row.get("customer_type", "Walk-in Patient")),
                timestamp=sale_date
            )
            db.add(sale)
        db.commit()


def init_db():
    """Initializes the schema tables and seeds initial master data."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_production_data(db)
    finally:
        db.close()
