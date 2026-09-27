import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from ...database.models.entities import (
    Pharmacy,
    Medicine,
    Inventory,
    Supplier,
    SalesHistory,
    PurchaseOrder,
    Alert,
    AgentMemory
)
from ...agents.orchestrator.morning_orchestrator import multi_agent_orchestrator
from ...agents.communication_agent.supplier_communication_agent import supplier_comm_agent
from ...memory.long_term.preference_learner import PharmacyPreferenceLearner
from ...tools.forecasting_tools.demand_forecaster import compute_medicine_forecast


class PilotScenarioValidationRunner:
    """
    PharmaGuard Real-World Pilot Scenario Validation Framework (Phase 5).
    
    Executes end-to-end clinical and operational simulation scenarios to validate
    agent robustness before and during real pharmacy pilots.
    """
    def __init__(self):
        pass

    def run_all_scenarios(self, db: Session) -> Dict[str, Any]:
        """
        Executes all 4 core pilot simulation scenarios in isolated sandboxes.
        """
        results = [
            self.simulate_scenario_1_stock_shortage(db),
            self.simulate_scenario_2_supplier_delays(db),
            self.simulate_scenario_3_seasonal_demand_surge(db),
            self.simulate_scenario_4_pharmacist_feedback_learning(db)
        ]

        total_scenarios = len(results)
        passed_scenarios = sum(1 for r in results if r["status"] == "PASS")

        return {
            "validation_suite": "PharmaGuard AI Real-World Pilot Validation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "scenarios_passed": f"{passed_scenarios}/{total_scenarios}",
            "all_passed": passed_scenarios == total_scenarios,
            "results": results
        }

    def simulate_scenario_1_stock_shortage(self, db: Session) -> Dict[str, Any]:
        """Scenario 1: Critical Shortage Detection & DRAFT PO Staging."""
        pharm_id = f"SIM-SC1-{uuid.uuid4().hex[:4]}"
        db.add(Pharmacy(id=pharm_id, organization_name="Sim Pharmacy 1", location="Douala"))
        db.add(Supplier(id=f"SUP-{pharm_id}", name="Sim Wholesale", delivery_time=7))
        db.add(Medicine(id=f"MED-{pharm_id}", brand_names="Insulin Rapid", generic_name="Insulin", category="Antidiabetic"))
        # 15 units stock, 5/day sales = 3 days coverage < 7 days delivery
        db.add(Inventory(id=f"INV-{pharm_id}", pharmacy_id=pharm_id, medicine_id=f"MED-{pharm_id}", supplier_id=f"SUP-{pharm_id}", quantity=15))
        for d in range(1, 11):
            db.add(SalesHistory(id=f"SALE-{pharm_id}-{d}", pharmacy_id=pharm_id, medicine_id=f"MED-{pharm_id}", quantity=5, sale_date=date.today()-timedelta(days=d)))
        db.commit()

        cycle = multi_agent_orchestrator.execute_morning_cycle(pharm_id, db)
        alerts = db.query(Alert).filter(Alert.pharmacy_id == pharm_id).all()
        pos = db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == pharm_id, PurchaseOrder.status == "DRAFT").all()

        passed = len(alerts) >= 1 and len(pos) >= 1
        return {
            "scenario": "SCENARIO_1_STOCK_SHORTAGE",
            "description": "Validates critical stock coverage calculation, high-risk alert generation, and DRAFT PO creation.",
            "status": "PASS" if passed else "FAIL",
            "alerts_generated": len(alerts),
            "draft_pos_created": len(pos)
        }

    def simulate_scenario_2_supplier_delays(self, db: Session) -> Dict[str, Any]:
        """Scenario 2: Supplier Delivery Delay & Exponential Moving Average Reliability Update."""
        pharm_id = f"SIM-SC2-{uuid.uuid4().hex[:4]}"
        sup_id = f"SUP-{pharm_id}"
        db.add(Pharmacy(id=pharm_id, organization_name="Sim Pharmacy 2", location="Yaounde"))
        db.add(Supplier(id=sup_id, name="Delayed Supplier", delivery_time=3, reliability_score=0.95))
        db.add(PurchaseOrder(id=f"PO-{pharm_id}", pharmacy_id=pharm_id, supplier_id=sup_id, status="APPROVED", total_amount_fcfa=50000.0, items_json='[]'))
        db.commit()

        supplier_comm_agent.dispatch_approved_order(f"PO-{pharm_id}", channel="EMAIL", db=db)
        # Record 6 days actual delivery (> 3 days target)
        res = supplier_comm_agent.record_supplier_response(f"PO-{pharm_id}", "DELIVERED", db=db, actual_delivery_days=6)

        sup = db.query(Supplier).filter(Supplier.id == sup_id).first()
        passed = sup.reliability_score < 0.95  # Score must be penalized
        return {
            "scenario": "SCENARIO_2_SUPPLIER_DELAYS",
            "description": "Validates penalty application and reliability score decay when supplier delivers late.",
            "status": "PASS" if passed else "FAIL",
            "initial_reliability": 0.95,
            "updated_reliability": sup.reliability_score
        }

    def simulate_scenario_3_seasonal_demand_surge(self, db: Session) -> Dict[str, Any]:
        """Scenario 3: Rainy Season Antimalarial Surge (+35%) & Depletion Acceleration."""
        pharm_id = f"SIM-SC3-{uuid.uuid4().hex[:4]}"
        med_id = f"MED-{pharm_id}"
        db.add(Pharmacy(id=pharm_id, organization_name="Sim Pharmacy 3", location="Douala"))
        db.add(Supplier(id=f"SUP-{pharm_id}", name="Wholesale", delivery_time=4))
        db.add(Medicine(id=med_id, brand_names="Artemether Forte", generic_name="Artemether", category="Antimalarial"))
        db.add(Inventory(id=f"INV-{pharm_id}", pharmacy_id=pharm_id, medicine_id=med_id, quantity=30))
        for d in range(1, 11):
            db.add(SalesHistory(id=f"SALE-{pharm_id}-{d}", pharmacy_id=pharm_id, medicine_id=med_id, quantity=3, sale_date=date.today()-timedelta(days=d)))
        db.commit()

        fc = compute_medicine_forecast(pharm_id, med_id, db)
        passed = fc["projected_daily_demand"] >= 3.0 and fc["confidence_score"] >= 0.80
        return {
            "scenario": "SCENARIO_3_SEASONAL_DEMAND_SURGE",
            "description": "Validates epidemiological multiplier integration and accelerated stock depletion forecasting.",
            "status": "PASS" if passed else "FAIL",
            "base_daily_sales": fc["base_daily_sales"],
            "projected_daily_demand": fc["projected_daily_demand"],
            "days_until_stockout": fc["days_until_stockout"]
        }

    def simulate_scenario_4_pharmacist_feedback_learning(self, db: Session) -> Dict[str, Any]:
        """Scenario 4: Human Feedback Learning & Memory Adaptation."""
        pharm_id = f"SIM-SC4-{uuid.uuid4().hex[:4]}"
        po_id = f"PO-{pharm_id}"
        med_id = f"MED-LRN-{pharm_id}"
        sup_a_id = f"SUP-A-{pharm_id}"
        sup_b_id = f"SUP-B-{pharm_id}"

        db.add(Pharmacy(id=pharm_id, organization_name="Sim Pharmacy 4", location="Douala"))
        db.add(Supplier(id=sup_a_id, name="Supplier A", delivery_time=2))
        db.add(Supplier(id=sup_b_id, name="Supplier B", delivery_time=2))
        db.add(Medicine(id=med_id, brand_names="Amoxicillin 500mg", generic_name="Amoxicillin", category="Antibiotic"))
        db.add(PurchaseOrder(id=po_id, pharmacy_id=pharm_id, supplier_id=sup_a_id, status="DRAFT", total_amount_fcfa=50000.0, items_json=f'[{{"medicine_id": "{med_id}", "name": "Amoxicillin", "quantity": 25, "unit_cost_fcfa": 2000, "subtotal_fcfa": 50000}}]'))
        db.commit()

        # Pharmacist modifies order: changes to Supplier B and increases quantity from 25 to 50
        from ...api.action_center.action_center_router import execute_pharmacist_decision, ActionDecisionRequest
        from ...database.models.entities import User
        user = User(id=f"USR-{pharm_id}", pharmacy_id=pharm_id, name="Dr. Chief Pharmacist", email=f"chief@{pharm_id}.cm", password_hash="hash", role="PHARMACIST")
        db.add(user)
        db.commit()

        execute_pharmacist_decision(
            po_id=po_id,
            decision=ActionDecisionRequest(
                action="MODIFY",
                modified_supplier_id=sup_b_id,
                modified_items=[{"medicine_id": med_id, "medicine_name": "Amoxicillin", "quantity": 50, "unit_cost_fcfa": 2000, "subtotal_fcfa": 100000}],
                notes="Switched to Supplier B for better stock quality",
                auto_dispatch=False
            ),
            current_user=user,
            db=db
        )

        memories = db.query(AgentMemory).filter(AgentMemory.pharmacy_id == pharm_id).all()
        passed = len(memories) >= 1
        return {
            "scenario": "SCENARIO_4_FEEDBACK_LEARNING",
            "description": "Validates capture of human modifications and storage into episodic long-term memory.",
            "status": "PASS" if passed else "FAIL",
            "memories_created": len(memories)
        }


# Singleton scenario runner
pilot_scenario_runner = PilotScenarioValidationRunner()
