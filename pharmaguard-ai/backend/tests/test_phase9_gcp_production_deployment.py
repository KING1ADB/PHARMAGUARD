import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import Base, get_db
from app.database.models.entities import Pharmacy, Medicine, Inventory, Supplier, User
from app.security.jwt_rbac import hash_password, create_access_token
from app.services.gcp.cloud_storage_service import GoogleCloudStorageService, gcs_service
from app.services.gcp.redis_cache_service import MemorystoreRedisService, redis_service
from app.services.gcp.secret_manager_service import GoogleSecretManagerService, secret_manager_service
from app.core.config import settings

# Test DB setup
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    
    # Create test pharmacy
    pharm = Pharmacy(
        id="PHARM-GCP-001",
        organization_name="Pharmacie Bonanjo GCP Prod",
        address="Rue des Palmiers, Bonanjo",
        location="Douala, Cameroon",
        contact_information="+237 677 999 888",
        verification_status="VERIFIED"
    )
    session.add(pharm)
    
    # Create test user
    user = User(
        id="USR-GCP-001",
        pharmacy_id="PHARM-GCP-001",
        name="Dr. Eric Nsangou",
        email="eric.nsangou@bonanjo.cm",
        phone="+237 677 111 222",
        password_hash=hash_password("GcpSecure2026!"),
        role="PHARMACIST",
        is_verified=True
    )
    session.add(user)
    
    # Add medicine and inventory for morning cycle
    med = Medicine(
        id="MED-GCP-001",
        generic_name="Paracetamol",
        brand_names="Doliprane 1000mg",
        category="Analgesics"
    )
    session.add(med)
    
    from datetime import date, timedelta
    inv = Inventory(
        id="INV-GCP-001",
        pharmacy_id="PHARM-GCP-001",
        medicine_id="MED-GCP-001",
        supplier_id="SUP-GCP-001",
        quantity=5, # Critical shortage
        reorder_threshold=20,
        expiry_date=date.today() + timedelta(days=200),
        unit_cost_fcfa=1200.0,
        selling_price_fcfa=1500.0
    )
    session.add(inv)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session

    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db_session):
    return TestClient(app)


def test_google_cloud_storage_service():
    """Validates GCS byte upload, download, and fallback storage mechanism."""
    storage = GoogleCloudStorageService()
    test_data = b"Sample Purchase Order PDF Content for Pharmacie Bonanjo"
    blob_name = "test_orders/PO_2026_001.pdf"

    upload_result = storage.upload_bytes(blob_name, test_data, content_type="application/pdf")
    assert upload_result["status"] == "SUCCESS"
    assert upload_result["size_bytes"] == len(test_data)
    assert "blob_name" in upload_result

    downloaded = storage.download_bytes(blob_name)
    assert downloaded == test_data

    health = storage.check_health()
    assert health["healthy"] is True
    assert "provider" in health


def test_memorystore_redis_service_and_distributed_lock():
    """Validates Redis caching, TTL expiration, and distributed concurrency locking."""
    redis = MemorystoreRedisService()

    # 1. Test set/get cache
    redis.set("gcp:test:key", {"status": "ACTIVE", "code": 200}, expire_seconds=10)
    cached_val = redis.get("gcp:test:key")
    assert cached_val is not None
    assert cached_val["status"] == "ACTIVE"
    assert cached_val["code"] == 200

    # 2. Test Distributed Locking
    lock_name = "daily_morning_run_test_lock"
    acquired_1 = redis.acquire_distributed_lock(lock_name, lock_timeout_seconds=5)
    assert acquired_1 is True

    # Immediate second attempt should fail (already locked)
    acquired_2 = redis.acquire_distributed_lock(lock_name, lock_timeout_seconds=5)
    assert acquired_2 is False

    # Release lock
    released = redis.release_distributed_lock(lock_name)
    assert released is True

    # Should be acquirable again
    acquired_3 = redis.acquire_distributed_lock(lock_name, lock_timeout_seconds=5)
    assert acquired_3 is True
    redis.release_distributed_lock(lock_name)

    health = redis.check_health()
    assert health["healthy"] is True


def test_secret_manager_service():
    """Validates Secret Manager secret resolution and fallback."""
    sm = GoogleSecretManagerService()
    
    # Test secret retrieval with default fallback
    val = sm.get_secret("NON_EXISTENT_SECRET", default="fallback_value_123")
    assert val == "fallback_value_123"

    health = sm.check_health()
    assert health["healthy"] is True
    assert "provider" in health


def test_cloud_scheduler_webhook_endpoints(client):
    """Validates Google Cloud Scheduler healthcheck and authenticated morning agent trigger."""
    # 1. Healthcheck
    res = client.get("/api/v1/scheduler/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert "0 7 * * *" in data["cron_schedule"]

    # 2. Unauthorized trigger attempt
    res_unauth = client.post("/api/v1/scheduler/trigger-morning-intelligence")
    assert res_unauth.status_code == 401
    res_auth = client.post(
        "/api/v1/scheduler/trigger-morning-intelligence?pharmacy_id=PHARM-GCP-001",
        headers={"X-Scheduler-Secret": settings.CLOUD_SCHEDULER_SECRET}
    )
    assert res_auth.status_code == 200
    cycle_data = res_auth.json()
    assert cycle_data["status"] == "SUCCESS"
    assert cycle_data["trigger_source"] == "GOOGLE_CLOUD_SCHEDULER"
    assert cycle_data["pharmacies_processed"] >= 1


def test_production_readiness_probe(client):
    """Validates the multi-service production readiness probe endpoint."""
    res = client.get("/api/v1/monitoring/readiness")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["READY", "DEGRADED"]
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis_memorystore" in data["checks"]
    assert "cloud_storage" in data["checks"]
    assert "secret_manager" in data["checks"]
    assert "notifications" in data["checks"]
