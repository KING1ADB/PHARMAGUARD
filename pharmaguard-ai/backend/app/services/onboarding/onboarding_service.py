import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ...database.models.entities import Pharmacy, User, Inventory, Medicine
from ...security.jwt_rbac import hash_password
from ...agents.orchestrator.morning_orchestrator import multi_agent_orchestrator
from ..connectors.csv_connector import import_pharmacy_inventory_csv


class PharmacyOnboardingService:
    """
    PharmaGuard Pharmacy Pilot Onboarding Service (Phase 5).
    
    Manages the 4-step pilot onboarding journey:
    Step 1: Pharmacy Registration & Regulatory Verification
    Step 2: Staff Account Setup with Role-Based Access Control
    Step 3: Initial Data Ingestion & POS Connection
    Step 4: Autonomous Agent Activation & Baseline Cycle Execution
    """
    def __init__(self):
        pass

    def register_pharmacy(
        self,
        organization_name: str,
        license_number: str,
        location: str,
        contact_email: str,
        db: Session,
        address: Optional[str] = None,
        phone: Optional[str] = None,
        pilot_tier: str = "STANDARD_PILOT"
    ) -> Dict[str, Any]:
        """
        Step 1: Registers a new pharmacy into PharmaGuard AI pilot network.
        """
        pharmacy_id = f"PHARM-{uuid.uuid4().hex[:6].upper()}"
        pharmacy = Pharmacy(
            id=pharmacy_id,
            organization_name=organization_name,
            location=location,
            address=address or location,
            contact_information=contact_email,
            onboarding_status="REGISTERED",
            pilot_tier=pilot_tier,
            agent_active=False
        )
        db.add(pharmacy)
        db.commit()

        return {
            "status": "SUCCESS",
            "step": "PHARMACY_REGISTERED",
            "pharmacy_id": pharmacy_id,
            "organization_name": organization_name,
            "onboarding_status": pharmacy.onboarding_status,
            "pilot_tier": pilot_tier
        }

    def setup_staff_account(
        self,
        pharmacy_id: str,
        name: str,
        email: str,
        password: str,
        role: str,
        db: Session,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 2: Provisions a verified staff account with RBAC permissions.
        """
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        if not pharmacy:
            return {"status": "ERROR", "message": f"Pharmacy {pharmacy_id} not found."}

        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            return {"status": "ERROR", "message": f"User with email {email} already exists."}

        valid_roles = ["OWNER", "PHARMACIST", "ASSISTANT", "AUDITOR"]
        role_clean = role.upper() if role.upper() in valid_roles else "PHARMACIST"

        user_id = f"USR-{uuid.uuid4().hex[:6].upper()}"
        user = User(
            id=user_id,
            pharmacy_id=pharmacy_id,
            name=name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role_clean
        )
        db.add(user)
        db.commit()

        return {
            "status": "SUCCESS",
            "step": "STAFF_ACCOUNT_PROVISIONED",
            "user_id": user_id,
            "name": name,
            "email": email,
            "role": role_clean,
            "pharmacy_id": pharmacy_id
        }

    def connect_initial_data(
        self,
        pharmacy_id: str,
        csv_bytes: bytes,
        filename: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Step 3: Connects initial inventory data and upgrades status to DATA_CONNECTED.
        """
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        if not pharmacy:
            return {"status": "ERROR", "message": f"Pharmacy {pharmacy_id} not found."}

        import_res = import_pharmacy_inventory_csv(csv_bytes, pharmacy_id, db, filename=filename)
        if import_res.get("status") == "ERROR":
            return import_res

        pharmacy.onboarding_status = "DATA_CONNECTED"
        db.commit()

        return {
            "status": "SUCCESS",
            "step": "DATA_CONNECTED",
            "pharmacy_id": pharmacy_id,
            "onboarding_status": pharmacy.onboarding_status,
            "items_imported": import_res.get("new_items_created", 0),
            "items_updated": import_res.get("existing_items_updated", 0)
        }

    def activate_pharmacy_agent(
        self,
        pharmacy_id: str,
        morning_run_time: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Step 4: Activates the autonomous Morning Intelligence Agent and executes baseline dry-run cycle.
        """
        pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
        if not pharmacy:
            return {"status": "ERROR", "message": f"Pharmacy {pharmacy_id} not found."}

        pharmacy.agent_active = True
        pharmacy.preferred_morning_run_time = morning_run_time
        pharmacy.onboarding_status = "PILOT_ACTIVE"
        db.commit()

        # Run initial baseline cycle
        baseline_cycle = multi_agent_orchestrator.execute_morning_cycle(pharmacy_id, db)

        return {
            "status": "SUCCESS",
            "step": "PILOT_ACTIVATED",
            "pharmacy_id": pharmacy_id,
            "onboarding_status": pharmacy.onboarding_status,
            "preferred_run_time": morning_run_time,
            "baseline_cycle_id": baseline_cycle.get("cycle_id"),
            "active_skus_evaluated": baseline_cycle.get("total_skus_evaluated"),
            "initial_alerts_count": len(baseline_cycle.get("report", {}).get("critical_alerts", []))
        }


# Singleton onboarding service
onboarding_service = PharmacyOnboardingService()
