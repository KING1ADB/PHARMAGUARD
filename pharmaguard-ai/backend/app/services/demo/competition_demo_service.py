import uuid
import json
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import (
    Pharmacy,
    Medicine,
    Inventory,
    Supplier,
    SalesHistory,
    PurchaseOrder,
    Alert,
    AgentActionLog,
    AgentMemory,
    User
)
from ...agents.orchestrator.morning_orchestrator import multi_agent_orchestrator
from ...agents.communication_agent.supplier_communication_agent import supplier_comm_agent
from ...memory.long_term.preference_learner import preference_learner
from ...evaluation.agent_evaluator import agent_evaluator
from ..command_center.command_center_service import command_center_service


class CompetitionDemonstrationService:
    """
    PharmaGuard AI Competition Demonstration Engine (Phase 6).
    
    Provides a controlled, high-fidelity live demonstration environment exposing
    real production multi-agent capabilities across 5 distinct phases:
    1. Autonomous Morning Cycle Trigger
    2. Multi-Agent Risk Detection (Cold-chain stockout & seasonal surges)
    3. Explainable Reasoning Generation
    4. Human-in-the-Loop Review & Decision Execution
    5. Real-Time Memory Update & Feedback Adaptation
    """
    def __init__(self):
        pass

    def run_live_competition_demo(self, db: Session) -> Dict[str, Any]:
        """
        Executes an end-to-end live demonstration sequence showcasing production AI agent intelligence.
        """
        demo_id = f"DEMO-{uuid.uuid4().hex[:6].upper()}"
        pharmacy_id = f"PHARM-{demo_id}"

        # -------------------------------------------------------------
        # 0. SETUP LIVE DEMO PHARMACY SANDBOX
        # -------------------------------------------------------------
        pharmacy = Pharmacy(
            id=pharmacy_id,
            organization_name="Pharmacie Grand Centre — Live Pilot Demo",
            location="Douala, Cameroon",
            address="Rue Joss, Bonanjo",
            contact_information="pilot-demo@pharmaguard.ai",
            onboarding_status="PILOT_ACTIVE",
            pilot_tier="ENTERPRISE_PILOT",
            agent_active=True,
            preferred_morning_run_time="07:30"
        )
        db.add(pharmacy)

        # Create Pharmacist User
        pharmacist_user = User(
            id=f"USR-{demo_id}",
            pharmacy_id=pharmacy_id,
            name="Dr. Marie-Claire Ndongo",
            email=f"dr.ndongo@{demo_id.lower()}.cm",
            password_hash="demo_hash",
            role="PHARMACIST"
        )
        db.add(pharmacist_user)

        # Primary and Alternative Suppliers
        sup_laborex = Supplier(
            id=f"SUP-LAB-{demo_id}",
            name="Laborex Cameroon (Primary)",
            delivery_time=5,
            reliability_score=0.96,
            contact_person="M. Emmanuel Eboa",
            email="commandes@laborex-cm.com",
            phone="+237699112233"
        )
        sup_ubipharm = Supplier(
            id=f"SUP-UBI-{demo_id}",
            name="Ubipharm Littoral",
            delivery_time=6,
            reliability_score=0.91,
            contact_person="Mme. Sophie Kamga",
            email="sales@ubipharm.cm",
            phone="+237677445566"
        )
        db.add_all([sup_laborex, sup_ubipharm])

        # Core Demo Medicines
        med_insulin = Medicine(
            id=f"MED-INS-{demo_id}",
            brand_names="Insulin Mixtard 100IU/ml",
            generic_name="Human Insulin",
            category="Antidiabetic",
            strength="100IU/ml 10ml",
            dosage_form="Vial / Injectable",
            storage_temperature="2-8°C (Cold-chain Required)",
            storage_conditions="Refrigerate between 2°C and 8°C. Protect from freezing.",
            regulatory_schedule="Prescription Required (Rx)",
            is_essential=True
        )
        med_coartem = Medicine(
            id=f"MED-COA-{demo_id}",
            brand_names="Coartem 20/120mg",
            generic_name="Artemether/Lumefantrine",
            category="Antimalarial",
            strength="20mg/120mg",
            dosage_form="Tablet",
            storage_temperature="15-25°C",
            regulatory_schedule="OTC Essential",
            is_essential=True
        )
        db.add_all([med_insulin, med_coartem])

        # Inventory Setup (Insulin: 6 vials / 2 daily = 3 days coverage < 5 days lead time)
        inv_insulin = Inventory(
            id=f"INV-INS-{demo_id}",
            pharmacy_id=pharmacy_id,
            medicine_id=med_insulin.id,
            supplier_id=sup_laborex.id,
            quantity=6,  # 3 days coverage < 5 days lead time -> HIGH RISK
            reorder_level=20,
            unit_cost_fcfa=6500.0,
            unit_sale_price_fcfa=8500.0,
            expiry_date=date.today() + timedelta(days=240),
            batch_number="LOT-INS-2026-X1"
        )
        inv_coartem = Inventory(
            id=f"INV-COA-{demo_id}",
            pharmacy_id=pharmacy_id,
            medicine_id=med_coartem.id,
            supplier_id=sup_laborex.id,
            quantity=18,  # 18 boxes / 6 daily = 3 days coverage < 5 days lead time -> HIGH RISK
            reorder_level=25,
            unit_cost_fcfa=2200.0,
            unit_sale_price_fcfa=3200.0,
            expiry_date=date.today() + timedelta(days=360),
            batch_number="LOT-COA-2026-Y4"
        )
        db.add_all([inv_insulin, inv_coartem])

        # Seed 14-day sales history
        for d in range(1, 15):
            s_date = date.today() - timedelta(days=d)
            db.add(SalesHistory(id=f"SALE-INS-{demo_id}-{d}", pharmacy_id=pharmacy_id, medicine_id=med_insulin.id, quantity=2, sale_date=s_date))
            db.add(SalesHistory(id=f"SALE-COA-{demo_id}-{d}", pharmacy_id=pharmacy_id, medicine_id=med_coartem.id, quantity=6, sale_date=s_date))
        db.commit()

        # -------------------------------------------------------------
        # STEP 1: AUTONOMOUS MORNING CYCLE TRIGGER
        # -------------------------------------------------------------
        cycle_result = multi_agent_orchestrator.execute_morning_cycle(pharmacy_id, db)

        # -------------------------------------------------------------
        # STEP 2: MULTI-AGENT RISK DETECTION
        # -------------------------------------------------------------
        active_alerts = db.query(Alert).filter(Alert.pharmacy_id == pharmacy_id).all()
        draft_pos = db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == pharmacy_id, PurchaseOrder.status == "DRAFT").all()

        # -------------------------------------------------------------
        # STEP 3: EXPLAINABLE REASONING GENERATION
        # -------------------------------------------------------------
        reasoning_details = []
        if active_alerts:
            reasoning_details.append(command_center_service.explain_agent_reasoning(pharmacy_id, active_alerts[0].id, db))
        if draft_pos:
            reasoning_details.append(command_center_service.explain_agent_reasoning(pharmacy_id, draft_pos[0].id, db))

        # -------------------------------------------------------------
        # STEP 4: HUMAN-IN-THE-LOOP APPROVAL & DISPATCH
        # -------------------------------------------------------------
        approved_orders = []
        if draft_pos:
            target_po = draft_pos[0]
            # Pharmacist reviews and authorizes order
            target_po.status = "APPROVED"
            db.commit()
            dispatch_res = supplier_comm_agent.dispatch_approved_order(target_po.id, channel="EMAIL", db=db)
            approved_orders.append({
                "po_id": target_po.id,
                "status": target_po.status,
                "dispatch_channel": "EMAIL",
                "dispatch_result": dispatch_res
            })

        # -------------------------------------------------------------
        # STEP 5: REAL-TIME MEMORY UPDATE & AGENT LEARNING
        # -------------------------------------------------------------
        # Pharmacist records preference: "Prioritize Laborex for cold-chain insulin due to validated refrigerated logistics"
        pref_res = preference_learner.record_preference(
            pharmacy_id=pharmacy_id,
            preference_key="preferred_cold_chain_supplier",
            preference_value=sup_laborex.id,
            confidence_score=0.98,
            source="PHARMACIST_DEMO_INTERACTION",
            db=db
        )

        memories = db.query(AgentMemory).filter(AgentMemory.pharmacy_id == pharmacy_id).all()
        scorecard = agent_evaluator.generate_agent_scorecard(pharmacy_id, db)

        return {
            "status": "SUCCESS",
            "demo_id": demo_id,
            "pharmacy_name": pharmacy.organization_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "demonstration_phases": {
                "phase_1_morning_trigger": {
                    "cycle_id": cycle_result.get("cycle_id"),
                    "status": "EXECUTED_AUTONOMOUSLY",
                    "skus_evaluated": cycle_result.get("total_skus_evaluated")
                },
                "phase_2_risk_detection": {
                    "alerts_triggered_count": len(active_alerts),
                    "critical_alerts": [a.message for a in active_alerts],
                    "draft_orders_staged": len(draft_pos)
                },
                "phase_3_reasoning_explanation": {
                    "transparency": "FULL_CHAIN_OF_THOUGHT",
                    "reasoning_breakdown": reasoning_details
                },
                "phase_4_human_approval": {
                    "action": "PHARMACIST_ONE_CLICK_APPROVAL",
                    "approved_by": pharmacist_user.name,
                    "orders_dispatched": approved_orders
                },
                "phase_5_memory_learning": {
                    "preference_stored": pref_res,
                    "active_memories_count": len(memories),
                    "updated_trust_index": scorecard.get("trust_index")
                }
            }
        }


# Singleton demo service
competition_demo_service = CompetitionDemonstrationService()
