import pytest
from datetime import date, timedelta
from app.database.database import SessionLocal, init_db
from app.database.models import Medicine, SaleRecord
from app.services.analysis import calculate_daily_sales_velocity, get_medicine_risk_profile, analyze_inventory_health
from app.services.forecasting import forecast_medicine_demand, compute_reorder_recommendation


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def test_velocity_calculation(db):
    velocity = calculate_daily_sales_velocity(db, "MED-001")
    assert isinstance(velocity, float)
    assert velocity >= 0.0


def test_medicine_risk_profile(db):
    med = db.query(Medicine).filter(Medicine.id == "MED-002").first()
    assert med is not None
    profile = get_medicine_risk_profile(db, med)
    assert "stockout_risk_level" in profile
    assert "expiry_status" in profile
    assert profile["days_until_expiry"] > 0


def test_inventory_health_analysis(db):
    health = analyze_inventory_health(db, "PHARM-DLA-001")
    assert health["total_skus"] >= 15
    assert health["total_inventory_cost_fcfa"] > 0
    assert "critical_stockout_items" in health
    assert "expiring_items" in health


def test_demand_forecasting(db):
    med = db.query(Medicine).filter(Medicine.id == "MED-001").first()
    fc = forecast_medicine_demand(db, med, days_horizon=14)
    assert fc["projected_demand_units"] > 0
    assert fc["seasonal_multiplier"] >= 1.0


def test_reorder_recommendation(db):
    med = db.query(Medicine).filter(Medicine.id == "MED-002").first()
    rec = compute_reorder_recommendation(db, med, target_cover_days=21)
    assert "recommended_order_units" in rec
    assert rec["recommended_order_units"] >= 0
    assert "reasoning" in rec
