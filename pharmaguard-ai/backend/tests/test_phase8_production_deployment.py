import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Inventory, Medicine
from app.services.auth.auth_service import production_auth_service
from app.services.notifications.notification_dispatch_service import notification_service
from app.monitoring.agent_reliability_monitor import agent_reliability_monitor

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


def test_production_authentication_lifecycle(client, db_session):
    """
    Test Phase 8 complete production authentication lifecycle:
    1. Register Owner & Pharmacy
    2. Verify Email with Token
    3. Password Reset Workflow (Forgot Password & Confirm Reset)
    4. MFA Setup and Verification
    """
    # 1. Register Owner & Pharmacy via API
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Pharmacie Moderne Bonanjo",
            "license_number": "LIC-CMR-2026-8800",
            "location": "Douala, Littoral",
            "owner_name": "Dr. Beatrice Ewane",
            "owner_email": "dr.ewane@moderne.cm",
            "password": "ProductionPassword2026!",
            "phone": "+237699554433"
        }
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["status"] == "SUCCESS"
    assert reg_data["is_verified"] is False
    verification_token = reg_data["verification_token"]
    user_id = reg_data["user_id"]
    token = reg_data["access_token"]

    # 2. Verify Email
    verify_resp = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token}
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "SUCCESS"

    user = db_session.query(User).filter(User.id == user_id).first()
    assert user.is_verified is True

    # 3. Forgot Password Request
    forgot_resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "dr.ewane@moderne.cm"}
    )
    assert forgot_resp.status_code == 200
    forgot_data = forgot_resp.json()
    reset_token = forgot_data.get("reset_token")
    assert reset_token is not None

    # 4. Confirm Password Reset
    reset_resp = client.post(
        "/api/v1/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "BrandNewSecurePassword2026!"}
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["status"] == "SUCCESS"

    # 5. Login with new password
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "dr.ewane@moderne.cm", "password": "BrandNewSecurePassword2026!"}
    )
    assert login_resp.status_code == 200
    new_token = login_resp.json()["access_token"]

    # 6. Setup & Verify MFA
    mfa_setup_resp = client.post(
        "/api/v1/auth/mfa/setup",
        headers={"Authorization": f"Bearer {new_token}"}
    )
    assert mfa_setup_resp.status_code == 200
    assert "mfa_secret" in mfa_setup_resp.json()

    mfa_verify_resp = client.post(
        "/api/v1/auth/mfa/verify",
        json={"token": "123456"},
        headers={"Authorization": f"Bearer {new_token}"}
    )
    assert mfa_verify_resp.status_code == 200
    assert mfa_verify_resp.json()["mfa_enabled"] is True


@pytest.mark.asyncio
async def test_production_notification_dispatch():
    """
    Test production notification dispatch service across WhatsApp, Email, and SMS.
    """
    # WhatsApp alert
    wa_res = await notification_service.send_whatsapp_alert(
        recipient_phone="+237699112233",
        template_name="morning_intelligence_summary",
        template_params=["Pharmacie du Centre", "3", "2"]
    )
    assert wa_res["status"] in ["QUEUED_LOG_ONLY", "DELIVERED"]
    assert wa_res["channel"] == "WHATSAPP"

    # Email notification
    email_res = notification_service.send_email_notification(
        recipient_email="pharmacist@pharmaguard.cm",
        subject="Daily Morning Intelligence Briefing",
        body_text="Your morning operations report is ready."
    )
    assert email_res["status"] in ["QUEUED_LOG_ONLY", "DELIVERED"]
    assert email_res["channel"] == "EMAIL"

    # SMS alert
    sms_res = await notification_service.send_sms_alert(
        recipient_phone="+237699112233",
        message_text="PharmaGuard: Critical Insulin shortage alert. Please review Action Center."
    )
    assert sms_res["status"] in ["QUEUED_LOG_ONLY", "DELIVERED"]
    assert sms_res["channel"] == "SMS"


def test_ai_reliability_monitor_and_prometheus(client, db_session):
    """
    Test AI Agent Reliability Monitor and Prometheus scraping endpoints.
    """
    agent_reliability_monitor.record_agent_cycle(0.38, success=True)
    agent_reliability_monitor.record_agent_cycle(0.42, success=True)

    # 1. JSON Telemetry Endpoint
    resp = client.get("/api/v1/monitoring/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert "telemetry" in data
    assert data["telemetry"]["agent_availability_pct"] >= 99.0

    # 2. Prometheus Endpoint
    prom_resp = client.get("/api/v1/monitoring/prometheus")
    assert prom_resp.status_code == 200
    prom_text = prom_resp.text
    assert "pharmaguard_uptime_seconds" in prom_text
    assert "pharmaguard_agent_actions_total" in prom_text


def test_production_health_and_root_endpoints(client):
    """
    Test health check and root endpoints in production mode.
    """
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert root_resp.json()["service"] == "PharmaGuard AI Platform"

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "HEALTHY"
    assert health_resp.json()["agent_status"] == "ACTIVE"
