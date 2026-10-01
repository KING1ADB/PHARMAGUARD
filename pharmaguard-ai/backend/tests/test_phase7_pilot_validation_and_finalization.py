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
from app.services.pilot_metrics.pilot_measurement_service import pilot_measurement_service
from app.services.reports.pilot_reporting_service import pilot_reporting_service
from app.services.evidence.evidence_package_service import competition_evidence_service
from app.monitoring.deployment_readiness_checker import deployment_readiness_checker

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


def test_pilot_measurement_system_before_after_metrics(client, db_session):
    """
    Test Phase 7 Before/After operational measurement:
    - Stockout reduction
    - Expiry risk reduction
    - Procurement efficiency gain
    - Pharmacist time savings
    - Net economic ROI in FCFA
    """
    pharm_id = "PHARM-MEASURE-01"
    pharm = Pharmacy(id=pharm_id, organization_name="Pharmacie Mesure Pilote", location="Douala", onboarding_status="PILOT_ACTIVE", agent_active=True)
    user = User(id="USR-M-01", pharmacy_id=pharm_id, name="Dr. Valery", email="valery@measure.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    sup = Supplier(id="SUP-M-01", name="Laborex", delivery_time=3, reliability_score=0.96)
    med = Medicine(id="MED-M-01", brand_names="Coartem 20/120mg", generic_name="Artemether", category="Antimalarial")
    inv = Inventory(id="INV-M-01", pharmacy_id=pharm_id, medicine_id="MED-M-01", supplier_id=sup.id, quantity=50, unit_cost_fcfa=2500.0)
    po = PurchaseOrder(id="PO-M-01", pharmacy_id=pharm_id, supplier_id=sup.id, status="APPROVED", total_amount_fcfa=75000.0, items_json='[]')

    db_session.add_all([pharm, user, sup, med, inv, po])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    # Test direct service calculation
    metrics = pilot_measurement_service.compute_pilot_impact_metrics(pharm_id, db_session)
    assert metrics["status"] == "SUCCESS"
    assert "comparison_framework" in metrics
    cf = metrics["comparison_framework"]
    assert "stockout_reduction" in cf
    assert "expiry_risk_reduction" in cf
    assert "procurement_efficiency" in cf
    assert "pharmacist_time_savings" in cf
    assert cf["pharmacist_time_savings"]["weekly_hours_saved"] >= 8.0

    # Test API Endpoint
    resp = client.get(
        "/api/v1/pilot-metrics/impact",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "financial_roi_summary" in data


def test_pilot_reporting_system_all_reports(client, db_session):
    """
    Test all 4 Pilot Reporting generators:
    1. Pharmacy Performance Report
    2. AI Effectiveness Report
    3. Trust Index Evolution Report
    4. Pilot Deployment Summary
    """
    pharm_id = "PHARM-REPORT-01"
    pharm = Pharmacy(id=pharm_id, organization_name="Pharmacie Reportage", location="Yaounde", onboarding_status="PILOT_ACTIVE", agent_active=True)
    user = User(id="USR-R-01", pharmacy_id=pharm_id, name="Dr. Roger", email="roger@rep.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    db_session.add_all([pharm, user])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    # 1. Performance Report
    resp1 = client.get("/api/v1/reports/performance", headers={"Authorization": f"Bearer {token}"})
    assert resp1.status_code == 200
    assert resp1.json()["report_type"] == "PHARMACY_PERFORMANCE_REPORT"

    # 2. AI Effectiveness Report
    resp2 = client.get("/api/v1/reports/ai-effectiveness", headers={"Authorization": f"Bearer {token}"})
    assert resp2.status_code == 200
    assert resp2.json()["report_type"] == "AI_EFFECTIVENESS_REPORT"

    # 3. Trust Evolution Report
    resp3 = client.get("/api/v1/reports/trust-evolution", headers={"Authorization": f"Bearer {token}"})
    assert resp3.status_code == 200
    assert resp3.json()["report_type"] == "TRUST_INDEX_EVOLUTION_REPORT"
    assert len(resp3.json()["evolution_timeline"]) >= 4

    # 4. Deployment Summary Briefing
    resp4 = client.get("/api/v1/reports/deployment-summary", headers={"Authorization": f"Bearer {token}"})
    assert resp4.status_code == 200
    assert resp4.json()["report_type"] == "PILOT_DEPLOYMENT_SUMMARY"
    assert resp4.json()["deployment_verdict"]["status"] == "PILOT_PASSED_READY_FOR_COMMERCIAL_SCALE"


def test_competition_evidence_package(client, db_session):
    """
    Test programmatic Competition Evidence Package exposing:
    - 5-minute live demo script
    - Judge stress scenario
    - Quantified impact metrics
    - Technical architecture
    - Safety & HITL explanations
    """
    pharm_id = "PHARM-EVID-01"
    pharm = Pharmacy(id=pharm_id, organization_name="Pharmacie Evidence", location="Douala", onboarding_status="PILOT_ACTIVE", agent_active=True)
    user = User(id="USR-E-01", pharmacy_id=pharm_id, name="Dr. Evidence", email="evid@cm.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    db_session.add_all([pharm, user])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    resp = client.get("/api/v1/evidence/package", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "demonstration_workflow" in data
    assert len(data["demonstration_workflow"]["steps"]) == 5
    assert "judge_stress_scenario" in data
    assert "impact_benchmarks" in data
    assert "technical_architecture" in data
    assert "safety_and_clinical_governance" in data


def test_production_deployment_checklist_and_preflight_validator(client, db_session):
    """
    Test automated pre-flight production deployment readiness checker across:
    1. Onboarding readiness
    2. Security & tenant isolation
    3. Data quality score
    4. Agent reliability & safety
    """
    pharm_id = "PHARM-CHECK-01"
    pharm = Pharmacy(id=pharm_id, organization_name="Pharmacie Check Preflight", location="Douala", onboarding_status="PILOT_ACTIVE", agent_active=True)
    user = User(id="USR-C-01", pharmacy_id=pharm_id, name="Dr. Preflight", email="preflight@check.cm", password_hash=hash_password("pw"), role="PHARMACIST")
    med = Medicine(id="MED-C-01", brand_names="Paracetamol", generic_name="Paracetamol", category="Analgesic")
    inv = Inventory(id="INV-C-01", pharmacy_id=pharm_id, medicine_id=med.id, quantity=100, unit_cost_fcfa=500.0, expiry_date=date.today() + timedelta(days=365), batch_number="BATCH-OK-1")
    
    db_session.add_all([pharm, user, med, inv])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    # Direct service test
    preflight = deployment_readiness_checker.run_preflight_checks(pharm_id, db_session)
    assert preflight["status"] == "SUCCESS"
    assert preflight["all_passed"] is True
    assert preflight["overall_deployment_readiness"] == "READY_FOR_PILOT_DEPLOYMENT"
    assert len(preflight["preflight_checklist"]) == 4

    # API Endpoint test
    resp = client.get(
        f"/api/v1/evidence/preflight-checks/{pharm_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    api_data = resp.json()
    assert api_data["status"] == "SUCCESS"
    assert api_data["all_passed"] is True
