import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...security.jwt_rbac import get_current_user, require_roles
from ...database.models.entities import User, Alert, PurchaseOrder, Pharmacy
from ...evaluation.agent_evaluator import agent_evaluator
from ...services.pilot.pilot_manager import pilot_manager

logger = logging.getLogger("PharmaGuard.DashboardRouter")
router = APIRouter(prefix="/dashboard", tags=["Agent Performance Dashboard"])


@router.get("/pilot-metrics")
def get_pilot_dashboard_metrics(
    pharmacy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the comprehensive Agent Performance Dashboard metrics:
    - Forecast Accuracy (%)
    - Alert Precision (%)
    - Procurement Acceptance Rate (%)
    - Trust Index (Composite 0 - 100%)
    - System Health & Data Quality Metrics
    - Action Center Queue Status (Pending Approvals, Active Alerts)
    """
    target_pharm_id = pharmacy_id or current_user.pharmacy_id
    if current_user.role not in ["OWNER", "AUDITOR"] and current_user.pharmacy_id != target_pharm_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot view performance dashboard of another pharmacy."
        )

    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == target_pharm_id).first()
    if not pharmacy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pharmacy {target_pharm_id} not found.")

    # 1. Agent Composite Performance Scorecard (Phase 4 Trust Layer)
    scorecard = agent_evaluator.generate_agent_scorecard(target_pharm_id, db)

    # 2. Pilot & Data Quality Health Metrics (Phase 5)
    pilot_status = pilot_manager.get_pharmacy_pilot_status(target_pharm_id, db)

    # 3. Operational Queue Snapshot
    pending_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.pharmacy_id == target_pharm_id,
        PurchaseOrder.status == "DRAFT"
    ).count()

    critical_alerts = db.query(Alert).filter(
        Alert.pharmacy_id == target_pharm_id,
        Alert.status == "ACTIVE",
        Alert.severity.in_(["HIGH", "CRITICAL"])
    ).count()

    return {
        "status": "SUCCESS",
        "pharmacy_id": target_pharm_id,
        "organization_name": pharmacy.organization_name,
        "pilot_tier": pharmacy.pilot_tier,
        "onboarding_status": pharmacy.onboarding_status,
        "agent_active": pharmacy.agent_active,
        "agent_performance": {
            "trust_index": scorecard.get("trust_index", "0.0%"),
            "forecast_accuracy": scorecard.get("metrics", {}).get("forecast_accuracy", {}).get("metric_value", "N/A"),
            "alert_precision": scorecard.get("metrics", {}).get("alert_precision", {}).get("metric_value", "N/A"),
            "procurement_acceptance_rate": scorecard.get("metrics", {}).get("procurement_acceptance_rate", {}).get("metric_value", "N/A"),
            "performance_rating": scorecard.get("overall_rating", "BASELINE")
        },
        "system_health": {
            "status": "HEALTHY",
            "data_quality_score": pilot_status.get("data_quality", {}).get("overall_data_quality_score", "0.0%"),
            "data_health_tier": pilot_status.get("data_quality", {}).get("data_health", "NEEDS_ATTENTION"),
            "active_skus_tracked": pilot_status.get("data_quality", {}).get("total_active_skus", 0),
            "scheduler_status": "RUNNING" if pharmacy.agent_active else "IDLE"
        },
        "action_queue": {
            "pending_purchase_orders_awaiting_approval": pending_pos,
            "active_critical_alerts": critical_alerts
        }
    }
