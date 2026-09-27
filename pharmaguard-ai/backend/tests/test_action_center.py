import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Medicine, Supplier, PurchaseOrder, AgentMemory
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


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_action_center_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    pharmacy = Pharmacy(
        id="PHARM-AC-01",
        organization_name="Pharmacie Action Center",
        location="Douala, Cameroon"
    )
    db.add(pharmacy)

    user = User(
        id="USR-AC-01",
        pharmacy_id="PHARM-AC-01",
        email="pharmacist.ac@pharmguard.ai",
        name="Dr. Patrice Eto'o",
        role="PHARMACIST",
        password_hash=hash_password("Action123!")
    )
    db.add(user)

    supplier1 = Supplier(
        id="SUP-AC-01",
        name="Laborex",
        delivery_time=2,
        email="orders@laborex.cm"
    )
    db.add(supplier1)

    supplier2 = Supplier(
        id="SUP-AC-02",
        name="Ubipharm",
        delivery_time=4,
        email="commandes@ubipharm.cm"
    )
    db.add(supplier2)

    # Staged DRAFT Purchase Orders
    po1 = PurchaseOrder(
        id="PO-AC-001",
        pharmacy_id="PHARM-AC-01",
        supplier_id="SUP-AC-01",
        status="DRAFT",
        total_amount_fcfa=50000.0,
        items_json='[{"medicine_id": "MED-01", "medicine_name": "Paracetamol 500mg", "quantity": 50, "unit_cost_fcfa": 1000, "subtotal_fcfa": 50000}]'
    )
    po2 = PurchaseOrder(
        id="PO-AC-002",
        pharmacy_id="PHARM-AC-01",
        supplier_id="SUP-AC-01",
        status="DRAFT",
        total_amount_fcfa=120000.0,
        items_json='[{"medicine_id": "MED-02", "medicine_name": "Amoxicilline 500mg", "quantity": 40, "unit_cost_fcfa": 3000, "subtotal_fcfa": 120000}]'
    )
    db.add(po1)
    db.add(po2)

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def test_action_center_queue_and_decisions():
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "pharmacist.ac@pharmguard.ai", "password": "Action123!"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Pending Queue
    queue_res = client.get("/api/v1/action-center/queue", headers=headers)
    assert queue_res.status_code == 200
    queue = queue_res.json()
    assert len(queue) == 2

    # 3. Decision: APPROVE PO-AC-001 with Auto-dispatch
    approve_res = client.post(
        "/api/v1/action-center/decide/PO-AC-001",
        headers=headers,
        json={
            "action": "APPROVE",
            "auto_dispatch": True,
            "dispatch_channel": "EMAIL",
            "notes": "Approved standard stock"
        }
    )
    assert approve_res.status_code == 200
    appr_data = approve_res.json()
    assert appr_data["status"] == "SUCCESS"
    assert appr_data["order_status"] == "DISPATCHED"
    assert appr_data["dispatch"]["tracking_reference"].startswith("TRK-")

    # 4. Decision: MODIFY PO-AC-002 (Switch to Supplier 2 & Increase Qty)
    modify_res = client.post(
        "/api/v1/action-center/decide/PO-AC-002",
        headers=headers,
        json={
            "action": "MODIFY",
            "modified_supplier_id": "SUP-AC-02",
            "modified_items": [{
                "medicine_id": "MED-02",
                "medicine_name": "Amoxicilline 500mg",
                "quantity": 60,
                "unit_cost_fcfa": 2900.0,
                "subtotal_fcfa": 174000.0
            }],
            "auto_dispatch": True,
            "dispatch_channel": "EMAIL",
            "notes": "Switched to Ubipharm due to better bulk rate"
        }
    )
    assert modify_res.status_code == 200
    mod_data = modify_res.json()
    assert mod_data["status"] == "SUCCESS"
    assert mod_data["decision"] == "MODIFY"

    # 5. Track Executions
    exec_res = client.get("/api/v1/action-center/executions", headers=headers)
    assert exec_res.status_code == 200
    executions = exec_res.json()
    assert len(executions) >= 2

    # 6. Supplier Response Confirmation
    resp_ack = client.post(
        "/api/v1/action-center/executions/PO-AC-001/supplier-response?response_status=DELIVERED&actual_delivery_days=2",
        headers=headers
    )
    assert resp_ack.status_code == 200
    assert resp_ack.json()["response_status"] == "DELIVERED"
