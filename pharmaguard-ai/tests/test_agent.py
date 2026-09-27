import pytest
from app.database.database import SessionLocal, init_db
from app.agent.orchestrator import orchestrator
from app.database.models import PurchaseOrder, AgentAction


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
    resp = orchestrator.handle_user_query(db, "PHARM-DLA-001", "Analyze this pharmacy")
    assert "PharmaGuard Autonomous Analysis" in resp["response"] or "PHARMAGUARD" in resp["response"]


def test_agent_query_stock(db):
    resp = orchestrator.handle_user_query(db, "PHARM-DLA-001", "Do you have Amoxicillin in stock?")
    assert "Amoxil" in resp["response"] or "Amoxicillin" in resp["response"]


def test_purchase_order_human_approval(db):
    cycle = orchestrator.run_autonomous_cycle(db, "PHARM-DLA-001")
    draft_po = db.query(PurchaseOrder).filter(PurchaseOrder.status == "DRAFT").first()
    
    if draft_po:
        approval_result = orchestrator.approve_purchase_order(db, draft_po.id)
        assert approval_result["status"] == "SUCCESS"
        assert approval_result["new_status"] == "APPROVED"


def test_auditable_agent_actions_logged(db):
    actions = db.query(AgentAction).all()
    assert len(actions) > 0
    for act in actions[:5]:
        assert act.agent_name is not None
        assert act.action_type is not None
        assert act.confidence_score > 0.0
