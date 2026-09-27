import pytest
from datetime import date, datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db
from app.database.models.entities import Base, Pharmacy, User, Medicine, Inventory, Supplier
from app.security.jwt_rbac import hash_password
from app.services.multi_tenant.regional_intelligence import regional_intelligence
from app.monitoring.health_monitor import production_monitor

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_multi_tenant_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Pharmacy 1 (Douala Centre)
    p1 = Pharmacy(id="PHARM-DLA-01", organization_name="Pharmacie Akwa", location="Douala, Littoral")
    # Pharmacy 2 (Douala Bonanjo)
    p2 = Pharmacy(id="PHARM-DLA-02", organization_name="Pharmacie Bonanjo", location="Douala, Littoral")
    # Pharmacy 3 (Yaounde)
    p3 = Pharmacy(id="PHARM-YDE-01", organization_name="Pharmacie Bastos", location="Yaounde, Centre")
    db.add_all([p1, p2, p3])

    med = Medicine(id="MED-MAL-01", brand_names="Coartem", generic_name="Artemether/Lumefantrine", category="Antimalarial")
    db.add(med)

    # Inventory in Pharmacy 1 (In Stock: 50 units)
    db.add(Inventory(id="INV-01", pharmacy_id="PHARM-DLA-01", medicine_id="MED-MAL-01", quantity=50, expiry_date=date(2027, 6, 1)))
    # Inventory in Pharmacy 2 (Stockout: 0 units)
    db.add(Inventory(id="INV-02", pharmacy_id="PHARM-DLA-02", medicine_id="MED-MAL-01", quantity=0, expiry_date=date(2027, 6, 1)))

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


def test_regional_supply_aggregation_and_tenant_isolation():
    db = TestingSessionLocal()
    try:
        # Regional supply index for Douala
        dla_index = regional_intelligence.get_regional_supply_index("Douala", db)
        assert dla_index["status"] == "SUCCESS"
        assert dla_index["connected_pharmacies_in_cluster"] == 2
        assert dla_index["privacy_compliance"]["tenant_isolation_preserved"] is True
        assert len(dla_index["category_indices"]) >= 1

        # Check Antimalarial category
        mal_cat = next(c for c in dla_index["category_indices"] if c["therapeutic_category"] == "Antimalarial")
        assert mal_cat["total_regional_stock_units"] == 50
        assert mal_cat["skus_evaluated"] == 2
        assert mal_cat["regional_availability_rate"] == 0.50  # 1 in stock, 1 stocked out
    finally:
        db.close()


def test_production_readiness_checklist():
    db = TestingSessionLocal()
    try:
        readiness = production_monitor.check_system_production_readiness(db)
        assert readiness["status"] == "PRODUCTION_READY"
        assert readiness["checks_passed"] >= 5
        assert readiness["total_checks"] >= 5
    finally:
        db.close()


def test_system_readiness_and_metrics_api():
    res_ready = client.get("/api/v1/system/readiness")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "PRODUCTION_READY"

    res_metrics = client.get("/api/v1/system/metrics")
    assert res_metrics.status_code == 200
    data = res_metrics.json()
    assert data["status"] == "OPERATIONAL"
    assert "agent_subsystems" in data
