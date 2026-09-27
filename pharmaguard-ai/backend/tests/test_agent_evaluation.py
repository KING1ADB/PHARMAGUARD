import pytest
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.entities import Base, Pharmacy, Medicine, Inventory, Supplier, SalesHistory, PurchaseOrder, Alert
from app.evaluation.agent_evaluator import agent_evaluator

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def eval_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    pharmacy = Pharmacy(
        id="PHARM-EVAL-01",
        organization_name="Pharmacie de l'Évaluation",
        location="Douala, Cameroon"
    )
    db.add(pharmacy)

    supplier = Supplier(
        id="SUP-EVAL-01",
        name="Laborex Cameroun",
        delivery_time=2,
        reliability_score=0.95
    )
    db.add(supplier)

    med = Medicine(
        id="MED-EVAL-01",
        brand_name="Glucophage 500mg",
        generic_name="Metformin HCl",
        category="Antidiabetic"
    )
    db.add(med)

    inv = Inventory(
        id="INV-EVAL-01",
        pharmacy_id="PHARM-EVAL-01",
        medicine_id="MED-EVAL-01",
        quantity=80,
        unit_cost_fcfa=1200.0,
        selling_price_fcfa=1800.0,
        expiry_date=date.today() + timedelta(days=400)
    )
    db.add(inv)

    # 10 days sales (4 units/day)
    for i in range(1, 11):
        db.add(SalesHistory(
            id=f"SALE-EVAL-{i}",
            pharmacy_id="PHARM-EVAL-01",
            medicine_id="MED-EVAL-01",
            quantity=4,
            sale_date=date.today() - timedelta(days=15-i),
            unit_price_fcfa=1800.0,
            total_amount_fcfa=7200.0
        ))

    # Purchase Orders (1 Approved, 1 Dispatched)
    db.add(PurchaseOrder(
        id="PO-EVAL-01",
        pharmacy_id="PHARM-EVAL-01",
        supplier_id="SUP-EVAL-01",
        status="APPROVED",
        total_amount_fcfa=48000.0,
        items_json='[]'
    ))
    db.add(PurchaseOrder(
        id="PO-EVAL-02",
        pharmacy_id="PHARM-EVAL-01",
        supplier_id="SUP-EVAL-01",
        status="DISPATCHED",
        total_amount_fcfa=96000.0,
        items_json='[]'
    ))

    # Alerts (1 active valid alert)
    db.add(Alert(
        id="ALT-EVAL-01",
        pharmacy_id="PHARM-EVAL-01",
        medicine_id="MED-EVAL-01",
        alert_type="SHORTAGE_RISK",
        severity="MEDIUM",
        title="Stock monitor",
        message="Stock level monitored",
        status="ACTIVE"
    ))

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def test_evaluate_forecast_accuracy(eval_db):
    res = agent_evaluator.evaluate_forecast_accuracy("PHARM-EVAL-01", eval_db)
    assert res["status"] == "SUCCESS"
    assert res["sample_size"] == 1
    assert res["forecast_accuracy_score"] >= 0.85
    assert res["benchmark_met"] is True


def test_evaluate_procurement_success_rate(eval_db):
    res = agent_evaluator.evaluate_procurement_success_rate("PHARM-EVAL-01", eval_db)
    assert res["status"] == "SUCCESS"
    assert res["total_recommendations"] == 2
    assert res["approval_rate"] == 1.0  # Both are approved/dispatched
    assert res["procurement_success_score"] >= 0.90


def test_evaluate_alert_precision(eval_db):
    res = agent_evaluator.evaluate_alert_precision("PHARM-EVAL-01", eval_db)
    assert res["status"] == "SUCCESS"
    assert res["total_alerts_generated"] == 1
    assert res["alert_precision_score"] == 1.0
    assert res["false_alert_rate"] == 0.0


def test_generate_composite_agent_scorecard(eval_db):
    scorecard = agent_evaluator.generate_agent_scorecard("PHARM-EVAL-01", eval_db)
    assert scorecard["status"] == "SUCCESS"
    assert scorecard["composite_trust_index"] >= 0.85
    assert "TIER" in scorecard["trust_grade"]
    assert "breakdown" in scorecard
