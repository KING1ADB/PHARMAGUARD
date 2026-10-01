import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Inventory, Medicine, Supplier, Alert, PurchaseOrder, SalesHistory
from app.security.jwt_rbac import create_access_token, hash_password
from app.services.command_center.command_center_service import command_center_service
from app.services.interaction.agent_interaction_service import agent_interaction_service
from app.services.simulation.pilot_30day_simulator import pilot_30day_simulator
from app.services.demo.competition_demo_service import competition_demo_service

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    return TestClient(app)


def test_command_center_summary_and_reasoning_explanation(client, db_session):
    """
    Test Command Center briefing, active alerts, pending approval queue,
    and step-by-step reasoning explanation.
    """
    pharm_id = "PHARM-CC-01"
    pharm = Pharmacy(id=pharm_id, organization_name="Pharmacie Command Center", location="Douala", onboarding_status="PILOT_ACTIVE", agent_active=True)
    user = User(id="USR-CC-01", pharmacy_id=pharm_id, name="Dr. Jean", email="jean@cc.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    sup = Supplier(id="SUP-CC-01", name="Wholesale Lab", delivery_time=3, reliability_score=0.95)
    med = Medicine(id="MED-CC-01", brand_names="Insulin 100IU", generic_name="Insulin", category="Antidiabetic", storage_temperature="2-8°C")
    inv = Inventory(id="INV-CC-01", pharmacy_id=pharm_id, medicine_id="MED-CC-01", supplier_id=sup.id, quantity=5, unit_cost_fcfa=6000.0)
    alert = Alert(id="ALT-CC-01", pharmacy_id=pharm_id, medicine_id="MED-CC-01", severity="CRITICAL", alert_type="COLD_CHAIN_SHORTAGE", message="Insulin stock critically low", recommended_action="Stage immediate PO", status="ACTIVE")
    po = PurchaseOrder(id="PO-CC-01", pharmacy_id=pharm_id, supplier_id=sup.id, status="DRAFT", total_amount_fcfa=60000.0, items_json='[{"medicine_id": "MED-CC-01", "name": "Insulin 100IU", "quantity": 10, "unit_cost_fcfa": 6000, "subtotal_fcfa": 60000}]')

    db_session.add_all([pharm, user, sup, med, inv, alert, po])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    # 1. Test Command Center Summary API
    resp = client.get(
        "/api/v1/command-center/summary",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["active_alerts_count"] >= 1
    assert data["approval_queue_count"] >= 1
    assert "briefing" in data

    # 2. Test Step-by-Step Chain-of-Thought Reasoning Explanation for Alert
    resp_reason_alert = client.get(
        f"/api/v1/command-center/reasoning/{alert.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_reason_alert.status_code == 200
    alert_reason = resp_reason_alert.json()
    assert alert_reason["target_type"] == "ALERT"
    assert len(alert_reason["reasoning_chain"]) >= 4

    # 3. Test Reasoning Explanation for Purchase Order
    resp_reason_po = client.get(
        f"/api/v1/command-center/reasoning/{po.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_reason_po.status_code == 200
    po_reason = resp_reason_po.json()
    assert po_reason["target_type"] == "PURCHASE_ORDER"
    assert len(po_reason["reasoning_chain"]) >= 4


def test_natural_ai_interaction_queries(client, db_session):
    """
    Test Natural AI Interaction queries across all 4 key pharmacist intents:
    1. 'Why did you generate this alert?'
    2. 'Explain this recommendation.'
    3. 'Prepare a purchase action for 40 boxes of Coartem.'
    4. 'Show pharmacy performance.'
    """
    pharm_id = "PHARM-INT-01"
    pharm = Pharmacy(id=pharm_id, organization_name="Pharmacie Interaction Test", location="Douala", onboarding_status="PILOT_ACTIVE", agent_active=True)
    user = User(id="USR-INT-01", pharmacy_id=pharm_id, name="Dr. Paul", email="paul@int.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    sup = Supplier(id="SUP-INT-01", name="Centrale Ph", delivery_time=2, reliability_score=0.92)
    med1 = Medicine(id="MED-INT-COA", brand_names="Coartem 20/120mg", generic_name="Artemether", category="Antimalarial")
    med2 = Medicine(id="MED-INT-INS", brand_names="Insulin Rapid", generic_name="Insulin", category="Antidiabetic", storage_temperature="2-8°C")
    inv1 = Inventory(id="INV-INT-COA", pharmacy_id=pharm_id, medicine_id=med1.id, supplier_id=sup.id, quantity=15, unit_cost_fcfa=2200.0)
    inv2 = Inventory(id="INV-INT-INS", pharmacy_id=pharm_id, medicine_id=med2.id, supplier_id=sup.id, quantity=4, unit_cost_fcfa=7000.0)
    alert = Alert(id="ALT-INT-01", pharmacy_id=pharm_id, medicine_id=med2.id, severity="CRITICAL", alert_type="STOCKOUT_RISK", message="Insulin 4 units remaining", recommended_action="Order 20 units", status="ACTIVE")
    po = PurchaseOrder(id="PO-INT-01", pharmacy_id=pharm_id, supplier_id=sup.id, status="DRAFT", total_amount_fcfa=44000.0, items_json='[{"medicine_id": "MED-INT-COA", "name": "Coartem", "quantity": 20, "unit_cost_fcfa": 2200, "subtotal_fcfa": 44000}]')

    db_session.add_all([pharm, user, sup, med1, med2, inv1, inv2, alert, po])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    # Query 1: Alert Inquiry
    resp1 = client.post(
        "/api/v1/interaction/query",
        json={"query": "Why did you generate this alert for Insulin?"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["intent"] == "ALERT_INQUIRY"
    assert "Insulin" in res1["response"] or "alert" in res1["response"].lower()

    # Query 2: Recommendation Explanation
    resp2 = client.post(
        "/api/v1/interaction/query",
        json={"query": "Explain this recommendation and supplier selection."},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["intent"] == "RECOMMENDATION_EXPLANATION"
    assert "Centrale Ph" in res2["response"]

    # Query 3: Action Preparation
    resp3 = client.post(
        "/api/v1/interaction/query",
        json={"query": "Prepare a purchase action for 40 boxes of Coartem."},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp3.status_code == 200
    res3 = resp3.json()
    assert res3["intent"] == "PREPARE_PURCHASE_ACTION"
    assert res3["data"]["quantity"] == 40
    assert res3["data"]["status"] == "DRAFT"

    # Query 4: Performance Inquiry
    resp4 = client.post(
        "/api/v1/interaction/query",
        json={"query": "Show pharmacy performance and Trust Index."},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp4.status_code == 200
    res4 = resp4.json()
    assert res4["intent"] == "PERFORMANCE_INQUIRY"
    assert "Trust Index" in res4["response"]


def test_30_day_pilot_simulation_framework(client, db_session):
    """
    Test the continuous 30-Day Real Pilot Simulation Engine.
    Verifies daily consumption, sales surges, morning intelligence cycles,
    supplier deliveries, and time-series Trust Index evolution.
    """
    sim_result = pilot_30day_simulator.run_30_day_simulation(
        db=db_session,
        pharmacy_name="Simulated 30-Day Pilot Akwa",
        seed=123
    )
    assert sim_result["status"] == "SUCCESS"
    assert sim_result["duration_days"] == 30
    assert len(sim_result["metrics_evolution_timeline"]) == 30
    
    summary = sim_result["summary_results"]
    assert summary["total_sales_units_dispensed"] > 0
    assert summary["total_alerts_managed"] > 0
    assert summary["overall_pilot_verdict"] == "PILOT_READY_EXCELLENT"

    # Verify Trust Index positive progression over 30 days
    timeline = sim_result["metrics_evolution_timeline"]
    day1_trust = timeline[0]["trust_index_pct"]
    day30_trust = timeline[-1]["trust_index_pct"]
    assert day30_trust >= day1_trust

    # Test API Endpoint with Pharmacist user
    user = User(id="USR-SIM-01", pharmacy_id="PHARM-SIM-ROOT", name="Dr. Lead", email="lead@sim.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})
    api_resp = client.post(
        "/api/v1/simulation/30-day",
        json={"pharmacy_name": "API Test Pilot Pharmacy", "seed": 99},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert api_data["status"] == "SUCCESS"
    assert api_data["duration_days"] == 30


def test_competition_demonstration_mode(client, db_session):
    """
    Test the Competition Demonstration Mode verifying all 5 phases:
    1. Autonomous Morning Trigger
    2. Multi-Agent Risk Detection
    3. Explainable Chain-of-Thought Reasoning
    4. Human-in-the-Loop Review & Approval
    5. Real-Time Memory Update & Feedback Adaptation
    """
    demo_result = competition_demo_service.run_live_competition_demo(db_session)
    assert demo_result["status"] == "SUCCESS"
    assert "demonstration_phases" in demo_result

    phases = demo_result["demonstration_phases"]
    assert phases["phase_1_morning_trigger"]["status"] == "EXECUTED_AUTONOMOUSLY"
    assert phases["phase_2_risk_detection"]["alerts_triggered_count"] >= 1
    assert phases["phase_3_reasoning_explanation"]["transparency"] == "FULL_CHAIN_OF_THOUGHT"
    assert phases["phase_4_human_approval"]["action"] == "PHARMACIST_ONE_CLICK_APPROVAL"
    assert phases["phase_5_memory_learning"]["active_memories_count"] >= 1

    # Test API Endpoint
    user = User(id="USR-DEMO-ROOT", pharmacy_id="PHARM-DEMO-ROOT", name="Dr. Demo", email="demo@root.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    db_session.add(user)
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})
    resp = client.post(
        "/api/v1/demo/competition-run",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "demonstration_phases" in data
