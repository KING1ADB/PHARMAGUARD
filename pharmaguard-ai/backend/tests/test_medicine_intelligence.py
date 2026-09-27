import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Medicine
from app.intelligence.medicine_knowledge import MedicineIntelligenceService

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def med_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Insulin
    db.add(Medicine(
        id="MED-INT-INS",
        brand_names="Mixtard 30 HM",
        generic_name="Human Insulin 100IU",
        category="Antidiabetic"
    ))

    # Antibiotic (Amoxicillin)
    db.add(Medicine(
        id="MED-INT-AUG",
        brand_names="Augmentin 1g",
        generic_name="Amoxicilline / Acide Clavulanique",
        category="Antibiotic"
    ))

    # Alternate brand of same generic in DB
    db.add(Medicine(
        id="MED-INT-CUR",
        brand_names="Curam 1g",
        generic_name="Amoxicilline / Acide Clavulanique",
        category="Antibiotic"
    ))

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_insulin_cold_chain_and_regulatory_intelligence(med_db):
    intel = MedicineIntelligenceService.get_medicine_intelligence("MED-INT-INS", med_db)
    assert intel["status"] == "SUCCESS"
    assert intel["brand_name"] == "Mixtard 30 HM"
    
    # Cold chain requirement
    storage = intel["storage_intelligence"]
    assert storage["requires_cold_chain"] is True
    assert "2°C to 8°C" in storage["temperature"]
    
    # Regulatory info
    reg = intel["regulatory_intelligence"]
    assert "List I" in reg["schedule"]
    assert reg["who_essential_list"] is True

    # Safety Guardrail
    assert intel["safety_guardrail"]["compliant"] is True
    assert "restricted to operational logistics" in intel["safety_guardrail"]["disclaimer"].lower()


def test_brand_generic_equivalence_mapping(med_db):
    intel = MedicineIntelligenceService.get_medicine_intelligence("MED-INT-AUG", med_db)
    assert intel["status"] == "SUCCESS"
    
    therapeutics = intel["therapeutic_equivalents"]
    assert "Amoxicillin" in therapeutics["dci"] or "Amoxicilline" in therapeutics["dci"]
    # Should include both catalog profile and DB alternate brand (Curam)
    assert "Augmentin" in therapeutics["equivalent_brands"]
    assert "Curam" in therapeutics["equivalent_brands"]
    assert therapeutics["equivalent_count"] >= 2
