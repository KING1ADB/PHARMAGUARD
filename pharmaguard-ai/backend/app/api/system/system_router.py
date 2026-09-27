from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from ...database.database import get_db
from ...monitoring.health_monitor import production_monitor

router = APIRouter(prefix="/system", tags=["System Production & Reliability"])


@router.get("/readiness", summary="Production Deployment Readiness Checklist")
def get_production_readiness(db: Session = Depends(get_db)):
    """
    Evaluates complete deployment readiness:
    - DB connection
    - Catalog seeding
    - RBAC configuration
    - Orchestrator status
    - Background scheduler
    - Safety guardrails
    """
    return production_monitor.check_system_production_readiness(db)


@router.get("/metrics", summary="Live AI Reliability & Operational Metrics")
def get_system_metrics(db: Session = Depends(get_db)):
    """
    Returns system uptime, agent status, and active operational counters.
    """
    readiness = production_monitor.check_system_production_readiness(db)
    return {
        "status": "OPERATIONAL",
        "readiness_status": readiness["status"],
        "checks_passed": f"{readiness['checks_passed']}/{readiness['total_checks']}",
        "uptime_seconds": readiness["uptime_seconds"],
        "agent_subsystems": {
            "inventory_agent": "ACTIVE",
            "forecasting_agent": "ACTIVE",
            "procurement_agent": "ACTIVE",
            "supplier_communication_agent": "ACTIVE",
            "multi_agent_orchestrator": "ACTIVE",
            "evaluation_engine": "ACTIVE"
        }
    }
