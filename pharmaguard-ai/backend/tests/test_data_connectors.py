import pytest
import io
import pandas as pd
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Pharmacy, Medicine, Inventory, SalesHistory
from app.services.connectors.csv_connector import import_pharmacy_inventory_csv
from app.services.connectors.excel_connector import import_pharmacy_inventory_excel
from app.services.connectors.barcode_connector import (
    lookup_medicine_by_barcode,
    dispense_stock_by_barcode,
    receive_batch_by_barcode
)

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def connector_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    pharmacy = Pharmacy(
        id="PHARM-CONN-01",
        organization_name="Pharmacie de Test Connectors",
        location="Yaounde, Cameroon"
    )
    db.add(pharmacy)

    med = Medicine(
        id="MED-BAR-01",
        brand_name="Efferalgan 1g",
        generic_name="Paracetamol",
        category="Analgesic",
        barcode="3582910012345"
    )
    db.add(med)

    inv = Inventory(
        id="INV-BAR-01",
        pharmacy_id="PHARM-CONN-01",
        medicine_id="MED-BAR-01",
        quantity=50,
        unit_cost_fcfa=1200.0,
        selling_price_fcfa=1800.0,
        expiry_date=date.today() + timedelta(days=360),
        batch_number="LOT-2026-EFF"
    )
    db.add(inv)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_csv_import_connector(connector_db):
    csv_data = (
        "Designation,DCI,Quantite,Prix_Achat,Prix_Vente,Peremption,Lot\n"
        "Augmentin 1g,Amoxicilline/Acide Clavulanique,40,4500,6000,2027-08-30,BATCH-AUG-01\n"
        "Ciprofloxacine 500mg,Ciprofloxacine,60,2000,3200,2027-10-15,BATCH-CIP-02\n"
    ).encode("utf-8")

    res = import_pharmacy_inventory_csv(
        file_content=csv_data,
        pharmacy_id="PHARM-CONN-01",
        db=connector_db,
        filename="stock_export.csv"
    )

    assert res["status"] == "SUCCESS"
    assert res["total_rows_processed"] == 2
    assert res["new_items_created"] == 2

    # Verify inventory was created
    items = connector_db.query(Inventory).filter(Inventory.pharmacy_id == "PHARM-CONN-01").all()
    assert len(items) == 3  # 1 initial + 2 new


def test_excel_import_connector(connector_db):
    df = pd.DataFrame([
        {
            "Nom_Commercial": "Spasfon Lyoc",
            "DCI": "Phloroglucinol",
            "Famille": "Antispasmodique",
            "Stock_Actuel": 25,
            "PA_HT": 1800.0,
            "PV_TTC": 2500.0,
            "Date_Peremption": "2027-12-31",
            "Numero_Lot": "LOT-SPAS-01"
        }
    ])
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    res = import_pharmacy_inventory_excel(
        file_content=excel_buffer.getvalue(),
        pharmacy_id="PHARM-CONN-01",
        db=connector_db,
        filename="grossiste_facture.xlsx"
    )

    assert res["status"] == "SUCCESS"
    assert res["total_rows_processed"] == 1
    assert res["new_items_created"] == 1


def test_barcode_lookup_and_dispense_and_receive(connector_db):
    # 1. Lookup
    lookup = lookup_medicine_by_barcode("3582910012345", "PHARM-CONN-01", connector_db)
    assert lookup["status"] == "FOUND"
    assert lookup["name"] == "Efferalgan 1g"
    assert lookup["current_stock"] == 50

    # 2. Dispense 5 units
    disp_res = dispense_stock_by_barcode(
        barcode="3582910012345",
        quantity_dispensed=5,
        pharmacy_id="PHARM-CONN-01",
        db=connector_db,
        patient_id="PATIENT-001"
    )
    assert disp_res["status"] == "SUCCESS"
    assert disp_res["remaining_stock"] == 45
    assert disp_res["total_amount_fcfa"] == 5 * 1800.0

    # Check SalesHistory transaction
    sales = connector_db.query(SalesHistory).filter(SalesHistory.pharmacy_id == "PHARM-CONN-01").all()
    assert len(sales) == 1
    assert sales[0].quantity == 5

    # 3. Receive shipment of +30 units
    rec_res = receive_batch_by_barcode(
        barcode="3582910012345",
        quantity_received=30,
        batch_number="LOT-2026-REC-01",
        expiry_date=date(2028, 1, 1),
        unit_cost_fcfa=1200.0,
        selling_price_fcfa=1800.0,
        pharmacy_id="PHARM-CONN-01",
        db=connector_db
    )
    assert rec_res["status"] == "SUCCESS"
    assert rec_res["total_stock_now"] == 75  # 45 + 30
