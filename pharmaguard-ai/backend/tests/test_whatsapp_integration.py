import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Medicine, Inventory, Supplier, PurchaseOrder
from app.security.jwt_rbac import hash_password
from app.services.whatsapp_service import WHATSAPP_VERIFY_TOKEN

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
def setup_whatsapp_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    pharmacy = Pharmacy(
        id="PHARM-WA-01",
        organization_name="Pharmacie du Wouri",
        location="Douala, Cameroon"
    )
    db.add(pharmacy)

    # Registered pharmacist with WhatsApp phone number
    user = User(
        id="USR-WA-01",
        pharmacy_id="PHARM-WA-01",
        email="dr.kamga@pharmguard.ai",
        name="Dr. Samuel Kamga",
        phone="+237699123456",
        role="PHARMACIST",
        password_hash=hash_password("Kamga2026!")
    )
    db.add(user)

    supplier = Supplier(
        id="SUP-WA-01",
        name="Laborex",
        delivery_time=2,
        email="orders@laborex.cm"
    )
    db.add(supplier)

    med = Medicine(
        id="MED-WA-01",
        brand_name="Doliprane 1000mg",
        generic_name="Paracetamol",
        category="Analgesic"
    )
    db.add(med)

    po = PurchaseOrder(
        id="PO-WA-9999",
        pharmacy_id="PHARM-WA-01",
        supplier_id="SUP-WA-01",
        status="DRAFT",
        total_amount_fcfa=85000.0,
        items_json='[{"medicine_id": "MED-WA-01", "name": "Doliprane 1000mg", "quantity": 50, "unit_cost_fcfa": 1700, "subtotal_fcfa": 85000}]'
    )
    db.add(po)

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def test_whatsapp_webhook_verification():
    # Valid verification handshake
    res = client.get(
        f"/api/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.verify_token={WHATSAPP_VERIFY_TOKEN}&hub.challenge=11559955"
    )
    assert res.status_code == 200
    assert res.text == "11559955"

    # Invalid token handshake
    res_bad = client.get(
        "/api/v1/integrations/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=WRONG_TOKEN&hub.challenge=11559955"
    )
    assert res_bad.status_code == 403


def test_whatsapp_inbound_message_approval_flow():
    # Simulate incoming Meta WhatsApp webhook payload with APPROVE command
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "237699000000", "phone_number_id": "1000"},
                    "messages": [{
                        "from": "237699123456",
                        "id": "wamid.HBgLMTIzNDU2",
                        "timestamp": "1727440000",
                        "text": {"body": "APPROVE PO-WA-9999"},
                        "type": "text"
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    res = client.post("/api/v1/integrations/whatsapp/webhook", json=webhook_payload)
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["status"] == "SUCCESS"
    assert res_json["events_processed"] == 1
    event_result = res_json["results"][0]
    assert event_result["status"] == "PO_APPROVED_AND_DISPATCHED"
    assert event_result["po_id"] == "PO-WA-9999"


def test_whatsapp_unauthorized_phone_rejection():
    # Non-registered phone number sends command
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": "237677000000",  # Unregistered number
                        "text": {"body": "REPORT"},
                        "type": "text"
                    }]
                }
            }]
        }]
    }

    res = client.post("/api/v1/integrations/whatsapp/webhook", json=webhook_payload)
    assert res.status_code == 200
    event_result = res.json()["results"][0]
    assert event_result["status"] == "UNAUTHORIZED"
