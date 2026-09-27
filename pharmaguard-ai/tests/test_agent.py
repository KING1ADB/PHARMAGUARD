import pytest
from app.database.database import SessionLocal, init_db
from app.agent.orchestrator import orchestrator
from app.database.models import PurchaseOrder


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def test_autonomous_decision_cycle(db):
    result = orchestrator.run_autonomous_cycle(db, "PHARM-DLA-001")
    assert result["cycle_id"].startswith("CYCLE-")
    assert "phase_results" in result
    assert "briefing_text" in result
    assert len(result["briefing_text"]) > 50


def test_agent_query_briefing(db):
    resp = orchestrator.handle_user_query(db, "PHARM-DLA-001", "Give me today's briefing")
    assert "PHARMAGUARD AI" in resp["response"]
    assert "CRITICAL" in resp["response"] or "Stock" in resp["response"]


def test_agent_query_stock(db):
    resp = orchestrator.handle_user_query(db, "PHARM-DLA-001", "Do you have Amoxicillin in stock?")
    assert "Amoxil" in resp["response"] or "Amoxicillin" in resp["response"]


def test_purchase_order_human_approval(db):
    # Ensure a cycle ran and generated draft orders
    cycle = orchestrator.run_autonomous_cycle(db, "PHARM-DLA-001")
    draft_po = db.query(PurchaseOrder).filter(PurchaseOrder.status == "DRAFT").first()
    
    if draft_po:
        approval_result = orchestrator.approve_purchase_order(db, draft_po.id)
        assert approval_result["status"] == "SUCCESS"
        assert approval_result["new_status"] == "APPROVED"
        assert "formatted_order_text" in approval_result
