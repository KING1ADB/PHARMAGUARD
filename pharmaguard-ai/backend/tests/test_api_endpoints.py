import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Medicine, Inventory, Supplier, SalesHistory
from app.security.jwt_rbac import hash_password

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create pharmacy
    pharmacy = Pharmacy(
        id="PHARM-001",
        organization_name="Pharmacie Centrale",
        license_number="CMR-PH-001",
        region="Centre",
        city="Yaounde",
        contact_email="direction@pharmacie-centrale.cm"
    )
    db.add(pharmacy)

    # Create test user (Pharmacist)
    hashed_pwd = hash_password("Secret123!")
    user = User(
        id="USR-PHARM-001",
        pharmacy_id="PHARM-001",
        email="pharmacist@pharmguard.ai",
        full_name="Dr. Amina Ndiaye",
        role="PHARMACIST",
        hashed_password=hashed_pwd,
        is_active=True
    )
    db.add(user)

    # Create test supplier
    sup = Supplier(
        id="SUP-001",
        name="Laborex Cameroun",
        lead_time_days=10,
        reliability_score=0.95,
        contact_email="commandes@laborex.cm"
    )
    db.add(sup)

    # Create medicine & inventory
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

    inv = Inventory(
        id="INV-001",
        pharmacy_id="PHARM-001",
        medicine_id="MED-016",
        supplier_id="SUP-001",
        batch_number="BCH-992",
        quantity_in_stock=25,
        unit_cost_fcfa=6500.0,
        days_until_expiry=180
    )
    db.add(inv)

    # Add sales (5 units/day for 10 days)
    for i in range(1, 11):
        sale = SalesHistory(
            id=f"SALE-API-{i}",
            pharmacy_id="PHARM-001",
            medicine_id="MED-016",
            quantity_sold=5,
            sale_date=datetime(2026, 9, i).date(),
            unit_sale_price_fcfa=8000.0,
            total_amount_fcfa=40000.0
        )
        db.add(sale)

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)


def test_root_and_health_endpoints():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["service"] == "PharmaGuard AI Platform"

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "HEALTHY"


def test_auth_login():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "pharmacist@pharmguard.ai", "password": "Secret123!"}
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_trigger_morning_cycle_and_approval_flow():
    # 1. Login to get token
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "pharmacist@pharmguard.ai", "password": "Secret123!"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Trigger Morning Intelligence Cycle
    trigger_res = client.post("/api/v1/agent/morning-cycle", headers=headers)
    assert trigger_res.status_code == 200
    report_data = trigger_res.json()
    assert report_data["status"] == "SUCCESS"
    assert report_data["high_shortage_risks"] >= 1
    assert "report" in report_data

    # 3. Retrieve Alerts
    alerts_res = client.get("/api/v1/agent/alerts", headers=headers)
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) >= 1

    # 4. Retrieve Draft Purchase Orders
    orders_res = client.get("/api/v1/agent/purchase-orders", headers=headers)
    assert orders_res.status_code == 200
    orders = orders_res.json()
    assert len(orders) >= 1
    po_id = orders[0]["id"]

    # 5. Human Authorization (Pharmacist APPROVE)
    approval_res = client.post(
        f"/api/v1/agent/purchase-orders/{po_id}/approval",
        headers=headers,
        json={"action": "APPROVE", "notes": "Approved for emergency insulin stock."}
    )
    assert approval_res.status_code == 200
    approval_body = approval_res.json()
    assert approval_body["status"] == "SUCCESS"
    assert approval_body["order_status"] == "APPROVED"
    assert approval_body["learning_logged"] is True

    # 6. Check Agent Long-Term Episodic Memory
    memory_res = client.get("/api/v1/agent/memory", headers=headers)
    assert memory_res.status_code == 200
    memories = memory_res.json()
    assert len(memories) >= 1

    # 7. Check Agent Audit Logs
    audit_res = client.get("/api/v1/agent/audit-logs", headers=headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert len(logs) >= 1

    # 8. Check Phase 2 Forecasting Intelligence Endpoints
    forecast_res = client.get("/api/v1/agent/forecasts", headers=headers)
    assert forecast_res.status_code == 200
    forecast_body = forecast_res.json()
    assert forecast_body["status"] == "SUCCESS"
    assert forecast_body["evaluated_skus_count"] >= 1
    assert "forecasts" in forecast_body

    single_forecast_res = client.get("/api/v1/agent/forecasts/MED-016", headers=headers)
    assert single_forecast_res.status_code == 200
    single_fc = single_forecast_res.json()
    assert single_fc["medicine_id"] == "MED-016"
    assert "estimated_stockout_date" in single_fc

