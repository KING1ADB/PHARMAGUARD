import pytest
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Pharmacy, Medicine, Inventory, Supplier, PurchaseOrder, AgentMemory, AgentActionLog
from app.agents.communication_agent.supplier_communication_agent import supplier_comm_agent

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def comm_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    pharmacy = Pharmacy(
        id="PHARM-COMM-01",
        organization_name="Pharmacie du Grand Sud",
        location="Douala, Cameroon",
        contact_information="contact@grandsud.cm"
    )
    db.add(pharmacy)

    supplier = Supplier(
        id="SUP-COMM-01",
        name="Ubipharm Cameroun",
        delivery_time=3,
        reliability_score=0.90,
        email="orders@ubipharm.cm"
    )
    db.add(supplier)

    med = Medicine(
        id="MED-COMM-01",
        brand_name="Paracetamol 1g",
        generic_name="Paracetamol",
        category="Analgesic"
    )
    db.add(med)

    po_draft = PurchaseOrder(
        id="PO-COMM-TEST-01",
        pharmacy_id="PHARM-COMM-01",
        supplier_id="SUP-COMM-01",
        status="DRAFT",
        total_amount_fcfa=150000.0,
        items_json='[{"medicine_id": "MED-COMM-01", "medicine_name": "Paracetamol 1g", "quantity": 100, "unit_cost_fcfa": 1500, "subtotal_fcfa": 150000}]'
    )
    db.add(po_draft)

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_generate_purchase_order_document(comm_db):
    doc = supplier_comm_agent.generate_purchase_order_document("PO-COMM-TEST-01", comm_db)
    assert doc["status"] == "SUCCESS"
    assert doc["po_id"] == "PO-COMM-TEST-01"
    assert "Paracetamol 1g" in doc["formatted_document_text"]
    assert "150,000 FCFA" in doc["formatted_document_text"]


def test_dispatch_approval_enforcement(comm_db):
    # Order is in DRAFT -> Dispatch MUST be blocked
    res_blocked = supplier_comm_agent.dispatch_approved_order("PO-COMM-TEST-01", channel="EMAIL", db=comm_db)
    assert res_blocked["status"] == "ERROR"
    assert "approval is required" in res_blocked["message"].lower()

    # Approve order
    po = comm_db.query(PurchaseOrder).filter(PurchaseOrder.id == "PO-COMM-TEST-01").first()
    po.status = "APPROVED"
    po.approved_by = "PHARMACIST-001"
    comm_db.commit()

    # Now dispatch MUST succeed
    res_dispatched = supplier_comm_agent.dispatch_approved_order("PO-COMM-TEST-01", channel="EMAIL", db=comm_db)
    assert res_dispatched["status"] == "SUCCESS"
    assert res_dispatched["order_status"] == "DISPATCHED"
    assert res_dispatched["tracking_reference"].startswith("TRK-")


def test_record_supplier_response_and_reliability_update(comm_db):
    # Approve and dispatch order
    po = comm_db.query(PurchaseOrder).filter(PurchaseOrder.id == "PO-COMM-TEST-01").first()
    po.status = "APPROVED"
    comm_db.commit()
    supplier_comm_agent.dispatch_approved_order("PO-COMM-TEST-01", channel="EMAIL", db=comm_db)

    # 1. Supplier confirms order
    conf_res = supplier_comm_agent.record_supplier_response(
        po_id="PO-COMM-TEST-01",
        response_status="CONFIRMED",
        db=comm_db,
        notes="Order in preparation"
    )
    assert conf_res["status"] == "SUCCESS"
    assert conf_res["response_status"] == "CONFIRMED"

    # 2. Supplier delivers on time (2 days <= 3 days lead time)
    deliv_res = supplier_comm_agent.record_supplier_response(
        po_id="PO-COMM-TEST-01",
        response_status="DELIVERED",
        db=comm_db,
        actual_delivery_days=2
    )
    assert deliv_res["status"] == "SUCCESS"
    assert deliv_res["response_status"] == "DELIVERED"
    # Reliability score should increase from 0.90 towards 1.0
    assert deliv_res["supplier_updated_reliability"] > 0.90

    # 3. Check memory feedback logged
    memories = comm_db.query(AgentMemory).filter(AgentMemory.memory_type == "SUPPLIER_RELIABILITY").all()
    assert len(memories) >= 2
