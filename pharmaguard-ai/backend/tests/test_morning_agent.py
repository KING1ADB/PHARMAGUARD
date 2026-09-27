import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Pharmacy, Medicine, Inventory, Supplier, SalesHistory, PurchaseOrder, Alert, AgentMemory, AgentActionLog
from app.agents.inventory_agent.morning_intelligence_agent import morning_agent
from app.memory.long_term.episodic_memory import EpisodicMemoryManager

# Use an in-memory SQLite database for deterministic test runs
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

    # Seed test pharmacy
    pharmacy = Pharmacy(
        id="PHARM-TEST-001",
        organization_name="Test Central Pharmacy",
        license_number="LIC-TEST-001",
        region="Centre",
        city="Yaounde",
        contact_email="test@pharmguard.ai"
    )
    db.add(pharmacy)

    # Seed test supplier (10 days lead time)
    supplier = Supplier(
        id="SUP-TEST-001",
        name="Cameroon National Drug Distributor",
        lead_time_days=10,
        reliability_score=0.92,
        contact_email="orders@cndd.cm"
    )
    db.add(supplier)

    # Seed test medicine
    med = Medicine(
        id="MED-INS-01",
        brand_name="Mixtard 30 HM",
        generic_name="Human Insulin 100IU/ml",
        therapeutic_class="Antidiabetic",
        dosage_form="Vial 10ml",
        unit_cost_fcfa=6500.0,
        unit_sale_price_fcfa=7800.0
    )
    db.add(med)

    # Seed inventory (25 units in stock, low coverage)
    inv = Inventory(
        id="INV-TEST-001",
        pharmacy_id="PHARM-TEST-001",
        medicine_id="MED-INS-01",
        supplier_id="SUP-TEST-001",
        batch_number="BATCH-INS-99",
        quantity_in_stock=25,
        unit_cost_fcfa=6500.0,
        expiry_date=datetime(2027, 6, 30).date(),
        days_until_expiry=276
    )
    db.add(inv)

    # Seed sales (5 units/day for 10 days)
    for d in range(1, 11):
        sale = SalesHistory(
            id=f"SALE-TEST-{d}",
            pharmacy_id="PHARM-TEST-001",
            medicine_id="MED-INS-01",
            quantity_sold=5,
            sale_date=datetime(2026, 9, d).date(),
            unit_sale_price_fcfa=7800.0,
            total_amount_fcfa=39000.0
        )
        db.add(sale)

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_morning_agent_autonomous_cycle(test_db):
    """
    Test the complete 6-step Morning Intelligence Agent autonomous cycle.
    """
    # 1. Trigger Morning Cycle
    result = morning_agent.execute_morning_cycle(pharmacy_id="PHARM-TEST-001", db=test_db)

    assert result["status"] == "SUCCESS"
    assert result["pharmacy_id"] == "PHARM-TEST-001"
    assert result["total_skus_evaluated"] == 1
    assert result["high_shortage_risks"] == 1
    assert result["draft_orders_created"] == 1

    # 2. Verify Alert was saved in database
    alerts = test_db.query(Alert).filter(Alert.pharmacy_id == "PHARM-TEST-001").all()
    assert len(alerts) == 1
    assert alerts[0].severity == "HIGH"
    assert "Mixtard 30 HM" in alerts[0].title

    # 3. Verify Draft Purchase Order was created
    draft_orders = test_db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == "PHARM-TEST-001").all()
    assert len(draft_orders) == 1
    po = draft_orders[0]
    assert po.status == "DRAFT"
    assert po.total_amount_fcfa > 0

    # 4. Human Approval Step (Pharmacist authorizes order)
    approval_res = morning_agent.process_pharmacist_decision(
        po_id=po.id,
        action="APPROVE",
        pharmacist_id="PHARMACIST-001",
        db=test_db,
        notes="Urgent replenishment for diabetic patients"
    )

    assert approval_res["status"] == "SUCCESS"
    assert approval_res["order_status"] == "APPROVED"
    assert approval_res["learning_logged"] is True

    # 5. Verify Long-term Episodic Memory & Audit Trail
    memories = test_db.query(AgentMemory).filter(AgentMemory.pharmacy_id == "PHARM-TEST-001").all()
    assert len(memories) >= 1
    assert memories[0].memory_type == "ORDER_AUTHORIZATION_FEEDBACK"

    audit_logs = test_db.query(AgentActionLog).filter(AgentActionLog.pharmacy_id == "PHARM-TEST-001").all()
    assert len(audit_logs) >= 2  # SHORTAGE_RISK_FLAGGED and PURCHASE_ORDER_APPROVED
