import io
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Inventory, Medicine, Supplier
from app.security.jwt_rbac import create_access_token, hash_password
from app.services.validation.pilot_scenario_runner import pilot_scenario_runner
from app.services.pilot.pilot_manager import pilot_manager
from app.services.onboarding.onboarding_service import onboarding_service

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
    
    # Override FastAPI db dependency for testing
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


def test_pilot_onboarding_end_to_end_flow(client, db_session):
    """
    Test the complete 4-step onboarding workflow:
    1. Register Pharmacy
    2. Provision Staff User (PHARMACIST)
    3. Connect Inventory CSV
    4. Activate Autonomous Agent
    """
    # Step 1: Register Pharmacy
    reg_resp = client.post(
        "/api/v1/onboarding/register",
        json={
            "organization_name": "Pharmacie Principale Douala",
            "license_number": "LIC-CMR-2026-9901",
            "location": "Douala",
            "contact_email": "admin@pharmacie-principale.cm",
            "address": "Avenue Charles de Gaulle, Akwa",
            "pilot_tier": "STANDARD_PILOT"
        }
    )
    assert reg_resp.status_code == 201
    pharm_data = reg_resp.json()
    assert pharm_data["status"] == "SUCCESS"
    assert pharm_data["onboarding_status"] == "REGISTERED"
    pharmacy_id = pharm_data["pharmacy_id"]

    # Step 2: Setup Staff Account
    staff_resp = client.post(
        "/api/v1/onboarding/staff",
        json={
            "pharmacy_id": pharmacy_id,
            "name": "Dr. Jean Mbarga",
            "email": "dr.jean@pharmacie-principale.cm",
            "password": "SecurePassword123!",
            "role": "PHARMACIST",
            "phone": "+237699112233"
        }
    )
    assert staff_resp.status_code == 201
    staff_data = staff_resp.json()
    assert staff_data["status"] == "SUCCESS"
    assert staff_data["role"] == "PHARMACIST"

    # Step 3: Connect Initial Data via CSV
    csv_content = (
        "medicine_id,name,category,current_stock,reorder_level,unit_cost_fcfa,expiry_date,batch_number,supplier_id\n"
        "MED-ONB-01,Paracetamol 500mg,Analgesic,120,30,500,2027-12-31,BATCH-A1,SUP-LOCAL\n"
        "MED-ONB-02,Coartem 20/120mg,Antimalarial,45,20,2500,2027-06-30,BATCH-A2,SUP-LOCAL\n"
    )
    csv_file = io.BytesIO(csv_content.encode("utf-8"))

    conn_resp = client.post(
        "/api/v1/onboarding/connect-data",
        data={"pharmacy_id": pharmacy_id},
        files={"file": ("inventory_onboarding.csv", csv_file, "text/csv")}
    )
    assert conn_resp.status_code == 200
    conn_data = conn_resp.json()
    assert conn_data["status"] == "SUCCESS"
    assert conn_data["step"] == "DATA_CONNECTED"
    assert conn_data["items_imported"] == 2

    # Step 4: Activate Agent
    act_resp = client.post(
        "/api/v1/onboarding/activate",
        json={
            "pharmacy_id": pharmacy_id,
            "morning_run_time": "07:30"
        }
    )
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["status"] == "SUCCESS"
    assert act_data["onboarding_status"] == "PILOT_ACTIVE"
    assert act_data["active_skus_evaluated"] == 2


def test_pilot_management_overview_and_data_quality(client, db_session):
    """
    Test the pilot manager tracking data quality scoring and overview across connected pharmacies.
    """
    # Create Owner User
    owner = User(
        id="USR-OWNER-PILOT",
        pharmacy_id="PHARM-CENTRAL",
        name="Pilot Administrator",
        email="admin@pharmaguard.ai",
        password_hash=hash_password("adminpass"),
        role="OWNER"
    )
    db_session.add(owner)

    # Create 2 pilot pharmacies with varying data completeness
    p1 = Pharmacy(id="PHARM-A", organization_name="Pharmacy Alpha", location="Douala", onboarding_status="PILOT_ACTIVE", agent_active=True)
    p2 = Pharmacy(id="PHARM-B", organization_name="Pharmacy Beta", location="Yaounde", onboarding_status="REGISTERED", agent_active=False)
    db_session.add_all([p1, p2])

    m1 = Medicine(id="MED-P1", brand_names="Amoxicillin 500mg", generic_name="Amoxicillin", category="Antibiotic")
    db_session.add(m1)

    # Fully complete inventory item (cost, expiry, batch)
    inv1 = Inventory(
        id="INV-P1",
        pharmacy_id="PHARM-A",
        medicine_id="MED-P1",
        quantity=50,
        unit_cost_fcfa=1500.0,
        expiry_date=date.today() + timedelta(days=200),
        batch_number="BATCH-QUAL-99"
    )
    db_session.add(inv1)
    db_session.commit()

    token = create_access_token({"sub": owner.email, "role": owner.role, "pharmacy_id": owner.pharmacy_id})

    # Query Pilot Overview
    resp = client.get(
        "/api/v1/pilot/overview",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_connected_pharmacies"] >= 2
    assert data["active_pilots_count"] >= 1

    # Query Pharmacy Alpha Pilot Status
    resp_alpha = client.get(
        "/api/v1/pilot/pharmacies/PHARM-A",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp_alpha.status_code == 200
    alpha_data = resp_alpha.json()
    assert alpha_data["organization_name"] == "Pharmacy Alpha"
    assert alpha_data["data_quality"]["data_health"] == "EXCELLENT"
    assert alpha_data["data_quality"]["overall_data_quality_score"] == "100.0%"


def test_agent_performance_dashboard_metrics(client, db_session):
    """
    Test the Agent Performance Dashboard metrics endpoint (/api/v1/dashboard/pilot-metrics).
    """
    pharm = Pharmacy(
        id="PHARM-DASH",
        organization_name="Clinique Centrale Pharmacy",
        location="Douala",
        onboarding_status="PILOT_ACTIVE",
        agent_active=True
    )
    user = User(
        id="USR-DASH",
        pharmacy_id="PHARM-DASH",
        name="Chief Pharmacist",
        email="dash@clinique.cm",
        password_hash=hash_password("dashpass"),
        role="PHARMACIST"
    )
    db_session.add_all([pharm, user])
    db_session.commit()

    token = create_access_token({"sub": user.email, "role": user.role, "pharmacy_id": user.pharmacy_id})

    resp = client.get(
        "/api/v1/dashboard/pilot-metrics",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "agent_performance" in data
    assert "trust_index" in data["agent_performance"]
    assert "system_health" in data
    assert data["system_health"]["scheduler_status"] == "RUNNING"


def test_real_world_validation_scenario_runner(client, db_session):
    """
    Test running all 4 real-world validation scenarios:
    - Stock Shortage Detection
    - Supplier Delays & Reliability Scoring
    - Seasonal Demand Surge
    - Pharmacist Feedback Learning
    """
    # Direct Service Runner Execution
    results = pilot_scenario_runner.run_all_scenarios(db_session)
    assert results["all_passed"] is True
    assert results["scenarios_passed"] == "4/4"
    assert len(results["results"]) == 4

    # API Endpoint Execution with OWNER token
    owner = User(
        id="USR-OWNER-VALIDATE",
        pharmacy_id="PHARM-ROOT",
        name="Root Admin",
        email="root@pharmaguard.ai",
        password_hash=hash_password("rootpass"),
        role="OWNER"
    )
    db_session.add(owner)
    db_session.commit()

    token = create_access_token({"sub": owner.email, "role": owner.role, "pharmacy_id": owner.pharmacy_id})
    resp = client.post(
        "/api/v1/pilot/validate-scenarios",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["all_passed"] is True
    assert data["scenarios_passed"] == "4/4"
