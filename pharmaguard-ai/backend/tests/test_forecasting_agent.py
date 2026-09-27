import pytest
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Pharmacy, Medicine, Inventory, Supplier, SalesHistory
from app.agents.forecasting_agent.forecasting_agent import forecasting_agent
from app.tools.forecasting_tools.demand_forecaster import compute_medicine_forecast, get_seasonal_multiplier

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Pharmacy
    pharmacy = Pharmacy(
        id="PHARM-FC-01",
        organization_name="Pharmacie de l'Avenir",
        location="Douala, Littoral",
        contact_information="contact@avenir.cm"
    )
    db.add(pharmacy)

    # Supplier (5 days delivery)
    supplier = Supplier(
        id="SUP-FC-01",
        name="Cameroun Pharma Distrib",
        delivery_time=5,
        reliability_score=0.94
    )
    db.add(supplier)

    # Medicine 1: Antimalarial (Artemether-Lumefantrine) -> Seasonal surge in rainy months
    med_malaria = Medicine(
        id="MED-MAL-01",
        brand_name="Coartem 80/480mg",
        generic_name="Artemether / Lumefantrine",
        category="Antimalarial",
        dosage_form="Tablet"
    )
    db.add(med_malaria)

    # Medicine 2: Chronic Antidiabetic (Metformin) -> Stable demand
    med_metformin = Medicine(
        id="MED-DIA-01",
        brand_name="Glucophage 850mg",
        generic_name="Metformin HCl",
        category="Antidiabetic",
        dosage_form="Tablet"
    )
    db.add(med_metformin)

    # Inventory 1: Coartem (20 units in stock, rapid sales -> stockout risk)
    inv_malaria = Inventory(
        id="INV-MAL-01",
        pharmacy_id="PHARM-FC-01",
        medicine_id="MED-MAL-01",
        supplier_id="SUP-FC-01",
        quantity=20,
        unit_cost_fcfa=2200.0,
        selling_price_fcfa=3000.0,
        expiry_date=date.today() + timedelta(days=365)
    )
    db.add(inv_malaria)

    # Inventory 2: Metformin (200 units in stock -> safe stock)
    inv_metformin = Inventory(
        id="INV-DIA-01",
        pharmacy_id="PHARM-FC-01",
        medicine_id="MED-DIA-01",
        supplier_id="SUP-FC-01",
        quantity=200,
        unit_cost_fcfa=1500.0,
        selling_price_fcfa=2200.0,
        expiry_date=date.today() + timedelta(days=500)
    )
    db.add(inv_metformin)

    # Historical sales for Coartem: 4 units/day over 10 days
    for d in range(1, 11):
        db.add(SalesHistory(
            id=f"SALE-MAL-{d}",
            pharmacy_id="PHARM-FC-01",
            medicine_id="MED-MAL-01",
            quantity=4,
            sale_date=date.today() - timedelta(days=15-d),
            unit_price_fcfa=3000.0,
            total_amount_fcfa=12000.0
        ))

    # Historical sales for Metformin: 5 units/day over 10 days
    for d in range(1, 11):
        db.add(SalesHistory(
            id=f"SALE-DIA-{d}",
            pharmacy_id="PHARM-FC-01",
            medicine_id="MED-DIA-01",
            quantity=5,
            sale_date=date.today() - timedelta(days=15-d),
            unit_price_fcfa=2200.0,
            total_amount_fcfa=11000.0
        ))

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_seasonal_multiplier_detection():
    # Rainy season month (July = month 7)
    res_malaria_rainy = get_seasonal_multiplier("Antimalarial", current_month=7)
    assert res_malaria_rainy["is_seasonal_surge"] is True
    assert res_malaria_rainy["multiplier"] == 1.35

    # Chronic antidiabetic
    res_diabetes = get_seasonal_multiplier("Antidiabetic", current_month=7)
    assert res_diabetes["is_seasonal_surge"] is False
    assert res_diabetes["multiplier"] == 1.0


def test_forecasting_coartem_stockout_prediction(test_db):
    """
    Test Coartem (Antimalarial) Demand Forecast & Stockout Date Prediction:
    - 20 units in stock
    - 4 units/day baseline sales
    - Forecast projects depletion in ~4-5 days
    - Supplier lead time is 5 days
    - Depletion is within supplier delivery window -> stockout_before_replenishment is True
    """
    fc = compute_medicine_forecast("PHARM-FC-01", "MED-MAL-01", test_db, forecast_horizon_days=30)

    assert fc["medicine_id"] == "MED-MAL-01"
    assert fc["current_stock"] == 20
    assert fc["base_daily_sales"] == 4.0
    assert fc["days_until_stockout"] <= 5.0
    assert fc["stockout_before_replenishment"] is True
    assert fc["confidence_score"] >= 0.80
    assert "Coartem" in fc["reasoning"]
    assert fc["supplier_lead_time_days"] == 5


def test_forecasting_metformin_safe_stock(test_db):
    """
    Test Metformin (Antidiabetic) Demand Forecast:
    - 200 units in stock
    - 5 units/day baseline sales
    - Depletion in ~40 days > supplier delivery (5 days)
    - stockout_before_replenishment is False
    - stockout_status is SAFE_HORIZON
    """
    fc = compute_medicine_forecast("PHARM-FC-01", "MED-DIA-01", test_db, forecast_horizon_days=30)

    assert fc["medicine_id"] == "MED-DIA-01"
    assert fc["current_stock"] == 200
    assert fc["base_daily_sales"] == 5.0
    assert fc["days_until_stockout"] >= 35.0
    assert fc["stockout_before_replenishment"] is False
    assert fc["stockout_status"] == "SAFE_HORIZON"


def test_forecasting_agent_analyze_future_state(test_db):
    """
    Test PharmacyForecastingAgent catalog analysis.
    """
    res = forecasting_agent.analyze_future_state("PHARM-FC-01", test_db, horizon_days=30)

    assert res["status"] == "SUCCESS"
    assert res["evaluated_skus_count"] == 2
    assert res["imminent_stockouts_count"] >= 1  # Coartem is imminent
    assert len(res["forecasts"]) == 2
    assert "PREDICTIVE DEMAND" in res["narrative_summary"]
