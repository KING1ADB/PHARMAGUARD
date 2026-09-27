import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Pharmacy, Medicine, Inventory, Supplier, SalesHistory
from app.tools.inventory_tools.inventory_reader import analyze_stock_level

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    pharmacy = Pharmacy(
        id="PHARM-001",
        organization_name="Pharmacie du Soleil",
        license_number="CMR-PHARM-2024-001",
        region="Littoral",
        city="Douala",
        contact_email="contact@pharmaciesoleil.cm"
    )
    db.add(pharmacy)

    supplier = Supplier(
        id="SUP-001",
        name="Laborex Cameroun",
        lead_time_days=10,  # 10 days delivery time
        reliability_score=0.95,
        contact_email="commandes@laborex.cm"
    )
    db.add(supplier)

    med = Medicine(
        id="MED-016",
        brand_name="Insulatard HM 100IU",
        generic_name="Insulin Human Isophane",
        therapeutic_class="Antidiabetic",
        dosage_form="Vial 10ml",
        unit_cost_fcfa=6500.0,
        unit_sale_price_fcfa=8000.0
    )
    db.add(med)

    # 25 units in stock
    inv = Inventory(
        id="INV-INS-001",
        pharmacy_id="PHARM-001",
        medicine_id="MED-016",
        batch_number="BCH-2026-INS",
        quantity_in_stock=25,
        unit_cost_fcfa=6500.0,
        expiry_date=datetime(2027, 4, 30).date(),
        days_until_expiry=215
    )
    db.add(inv)

    # Historical sales totaling 150 units over 30 days -> 5.0 units/day
    for i in range(1, 31):
        sale = SalesHistory(
            id=f"SALE-INS-{i}",
            pharmacy_id="PHARM-001",
            medicine_id="MED-016",
            quantity_sold=5,
            sale_date=datetime(2026, 8, i).date(),
            unit_sale_price_fcfa=8000.0,
            total_amount_fcfa=40000.0
        )
        db.add(sale)

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_insulin_stockout_risk_evaluation(db_session):
    """
    Validation Test Case:
    - Current stock = 25 units
    - Average daily sales = 5 units/day
    - Stock coverage = 25 / 5 = 5.0 days
    - Supplier lead time = 10 days
    - Since coverage (5.0 days) < supplier delivery (10 days):
      => Risk Level MUST be HIGH
      => Confidence Score MUST be 0.91 (91%)
    """
    analysis = analyze_stock_level(
        pharmacy_id="PHARM-001",
        medicine_id="MED-016",
        db=db_session
    )

    assert analysis["medicine_id"] == "MED-016"
    assert analysis["current_quantity"] == 25
    assert pytest.approx(analysis["avg_daily_sales"], 0.1) == 5.0
    assert pytest.approx(analysis["stock_coverage_days"], 0.1) == 5.0
    assert analysis["supplier_delivery_days"] == 10
    assert analysis["risk_level"] == "HIGH"
    assert analysis["confidence_score"] == 0.91
    assert "shortage risk" in analysis["reasoning"].lower()
