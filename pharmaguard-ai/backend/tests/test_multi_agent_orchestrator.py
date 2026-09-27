import pytest
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import (
    Base,
    Pharmacy,
    Medicine,
    Inventory,
    Supplier,
    SalesHistory,
    PurchaseOrder,
    Alert,
    AgentMemory,
    AgentActionLog
)
from app.agents.orchestrator.morning_orchestrator import multi_agent_orchestrator

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def orch_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Pharmacy
    pharmacy = Pharmacy(
        id="PHARM-ORCH-01",
        organization_name="Pharmacie Principale de Douala",
        location="Douala, Cameroon",
        contact_information="contact@principale.cm"
    )
    db.add(pharmacy)

    # Supplier (8 days lead time)
    supplier = Supplier(
        id="SUP-ORCH-01",
        name="Laborex Distribution",
        delivery_time=8,
        reliability_score=0.96
    )
    db.add(supplier)

    # Medicine: Amoxicillin (Antibiotic)
    med = Medicine(
        id="MED-AMX-01",
        brand_name="Clamoxyl 500mg",
        generic_name="Amoxicilline",
        category="Antibiotic",
        dosage_form="Capsule"
    )
    db.add(med)

    # Inventory: 30 capsules, 6 capsules/day sales -> 5.0 days coverage < 8 days lead time
    inv = Inventory(
        id="INV-AMX-01",
        pharmacy_id="PHARM-ORCH-01",
        medicine_id="MED-AMX-01",
        supplier_id="SUP-ORCH-01",
        quantity=30,
        unit_cost_fcfa=3200.0,
        selling_price_fcfa=4500.0,
        expiry_date=date.today() + timedelta(days=200)
    )
    db.add(inv)

    # 10 days of sales history (6 units/day)
    for i in range(1, 11):
        db.add(SalesHistory(
            id=f"SALE-AMX-{i}",
            pharmacy_id="PHARM-ORCH-01",
            medicine_id="MED-AMX-01",
            quantity=6,
            sale_date=date.today() - timedelta(days=15-i),
            unit_price_fcfa=4500.0,
            total_amount_fcfa=27000.0
        ))

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_multi_agent_morning_orchestration_cycle(orch_db):
    """
    Test the integrated 5-step Multi-Agent Morning Intelligence cycle:
    1. Inventory Agent detects current stock level and batch status.
    2. Forecasting Agent projects 5.0 days depletion date against 8-day delivery.
    3. Procurement Agent stages a draft purchase order.
    4. Orchestrator unifies results into executive report and alerts.
    5. Human pharmacist authorizes order, updating episodic memory.
    """
    # 1. Execute Multi-Agent Cycle
    result = multi_agent_orchestrator.execute_morning_cycle(pharmacy_id="PHARM-ORCH-01", db=orch_db)

    assert result["status"] == "SUCCESS"
    assert result["pharmacy_id"] == "PHARM-ORCH-01"
    assert result["total_skus_evaluated"] >= 1
    assert result["high_shortage_risks"] >= 1
    assert result["draft_orders_created"] >= 1
    assert "report" in result
    assert "forecasting_summary" in result

    # 2. Check Draft Purchase Orders staged
    draft_orders = orch_db.query(PurchaseOrder).filter(
        PurchaseOrder.pharmacy_id == "PHARM-ORCH-01",
        PurchaseOrder.status == "DRAFT"
    ).all()
    assert len(draft_orders) >= 1
    po = draft_orders[0]
    assert po.total_amount_fcfa > 0

    # 3. Human-in-the-Loop Approval Step
    approval_res = multi_agent_orchestrator.process_pharmacist_decision(
        po_id=po.id,
        action="APPROVE",
        pharmacist_id="PHARMACIST-CHIEF-01",
        db=orch_db,
        notes="Authorized seasonal antibiotic replenishment."
    )

    assert approval_res["status"] == "SUCCESS"
    assert approval_res["order_status"] == "APPROVED"
    assert approval_res["learning_logged"] is True

    # 4. Verify Episodic Memory & Audit Trail
    memories = orch_db.query(AgentMemory).filter(AgentMemory.pharmacy_id == "PHARM-ORCH-01").all()
    assert len(memories) >= 1

    audit_logs = orch_db.query(AgentActionLog).filter(AgentActionLog.pharmacy_id == "PHARM-ORCH-01").all()
    assert len(audit_logs) >= 2
