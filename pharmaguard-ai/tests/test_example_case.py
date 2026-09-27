import pytest
from app.database.database import SessionLocal, init_db
from app.database.models import Medicine, Inventory, Supplier, SalesHistory
from app.tools.risk_tools import calculate_stock_risk
from app.agent.orchestrator import orchestrator


@pytest.fixture(scope="module")
def db():
    init_db()
    session = SessionLocal()
    yield session
    session.close()


def test_insulin_specification_test_case(db):
    """
    Direct test case from specification:
    Medicine: Insulin
    Quantity: 25 units
    Daily sales: 5 units
    Supplier delivery: 10 days
    
    Expected reasoning:
    Stock coverage: 25 / 5 = 5 days
    Supplier delivery: 10 days
    Conclusion: High shortage risk
    Confidence: 91%
    """
    # 1. Test direct tool risk calculation
    risk_data = calculate_stock_risk("MED-016", db, "PHARM-DLA-001")
    
    assert risk_data["name"] == "Insulin Mixtard 30"
    assert risk_data["current_quantity"] == 25
    assert risk_data["average_daily_sales"] == 5.0
    assert risk_data["stock_coverage_days"] == 5.0
    assert risk_data["supplier_delivery_days"] == 10
    assert risk_data["risk_level"] == "HIGH"
    assert risk_data["confidence_score"] == 0.91
    
    expected_substring = "covers approximately 5 days while supplier delivery requires 10 days"
    assert expected_substring in risk_data["reasoning"]

    # 2. Test Agent interactive natural language query
    agent_resp = orchestrator.handle_user_query(db, "PHARM-DLA-001", "Analyze stock of Insulin")
    
    assert "high shortage risk" in agent_resp["response"].lower()
    assert "covers approximately 5 days while supplier delivery requires 10 days" in agent_resp["response"]
    assert "91%" in agent_resp["response"]
    assert agent_resp["data"]["confidence_score"] == 0.91
