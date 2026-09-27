from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...database.models.entities import (
    User,
    Alert,
    PurchaseOrder,
    AgentMemory,
    AgentActionLog,
    Pharmacy
)
from ...database.schemas.entities_schema import (
    AlertResponse,
    PurchaseOrderResponse,
    PurchaseOrderApprovalRequest,
    AgentMemoryResponse,
    AgentActionLogResponse,
    MorningIntelligenceReportResponse,
    MorningCycleTriggerResponse,
    DemandForecastDetail,
    ForecastingSummaryResponse
)
from ...security.jwt_rbac import get_current_active_user, require_role, UserRole
from ...agents.orchestrator.morning_orchestrator import multi_agent_orchestrator
from ...agents.forecasting_agent.forecasting_agent import forecasting_agent

router = APIRouter(prefix="/agent", tags=["Autonomous Pharmacy Agent"])


@router.post(
    "/morning-cycle",
    response_model=MorningCycleTriggerResponse,
    summary="Trigger Multi-Agent Morning Intelligence Cycle"
)
def trigger_morning_intelligence_cycle(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Executes the integrated 5-step Multi-Agent Morning Cycle:
    1. Inventory Agent analyzes current state (batches, expiries, current stock).
    2. Forecasting Agent predicts future state (demand curves, seasonal surges, depletion dates).
    3. Procurement Agent evaluates optimal actions (replenishment orders & supplier selection).
    4. Orchestrator unifies results into executive intelligence briefing & alerts.
    5. Human Pharmacist Authorization remains mandatory.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    if not target_pharmacy_id:
        first_pharmacy = db.query(Pharmacy).first()
        if not first_pharmacy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No pharmacy registered in the system."
            )
        target_pharmacy_id = first_pharmacy.id

    result = multi_agent_orchestrator.execute_morning_cycle(target_pharmacy_id, db)
    return result


@router.get(
    "/morning-report",
    response_model=MorningCycleTriggerResponse,
    summary="Get Latest Morning Intelligence Briefing"
)
def get_morning_intelligence_report(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Returns the latest unified morning intelligence briefing and operational recommendations.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    if not target_pharmacy_id:
        first_pharmacy = db.query(Pharmacy).first()
        if not first_pharmacy:
            raise HTTPException(status_code=404, detail="Pharmacy not found")
        target_pharmacy_id = first_pharmacy.id

    result = multi_agent_orchestrator.execute_morning_cycle(target_pharmacy_id, db)
    return result


@router.get(
    "/forecasts",
    response_model=ForecastingSummaryResponse,
    summary="Get Predictive Demand Forecasts & Depletion Analysis for All SKUs"
)
def get_all_demand_forecasts(
    horizon_days: int = Query(30, ge=7, le=90, description="Forecast horizon in days"),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Phase 2 Forecasting Intelligence:
    Returns multi-horizon demand projections, seasonal disease surge factors,
    and predicted stockout dates across the pharmacy catalog.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    if not target_pharmacy_id:
        first_pharmacy = db.query(Pharmacy).first()
        if not first_pharmacy:
            raise HTTPException(status_code=404, detail="Pharmacy not found")
        target_pharmacy_id = first_pharmacy.id

    forecast_data = forecasting_agent.analyze_future_state(
        pharmacy_id=target_pharmacy_id,
        db=db,
        horizon_days=horizon_days
    )
    return forecast_data


@router.get(
    "/forecasts/{medicine_id}",
    response_model=DemandForecastDetail,
    summary="Get Detailed Demand & Stockout Forecast for Single Medicine"
)
def get_single_medicine_forecast(
    medicine_id: str,
    horizon_days: int = Query(30, ge=7, le=90),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves deep-dive statistical and seasonal forecast for a specific medicine SKU.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    if not target_pharmacy_id:
        first_pharmacy = db.query(Pharmacy).first()
        if not first_pharmacy:
            raise HTTPException(status_code=404, detail="Pharmacy not found")
        target_pharmacy_id = first_pharmacy.id

    forecast = forecasting_agent.forecast_single_medicine(
        pharmacy_id=target_pharmacy_id,
        medicine_id=medicine_id,
        db=db,
        horizon_days=horizon_days
    )

    if forecast.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=forecast.get("message", "Forecast failed"))

    return forecast


@router.get(
    "/alerts",
    response_model=List[AlertResponse],
    summary="List Prioritized Agent Alerts"
)
def list_agent_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity (HIGH, MEDIUM, LOW)"),
    status: Optional[str] = Query("ACTIVE", description="Filter by status (ACTIVE, RESOLVED, DISMISSED)"),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves prioritized operational alerts generated autonomously by the agent.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    query = db.query(Alert)
    if target_pharmacy_id:
        query = query.filter(Alert.pharmacy_id == target_pharmacy_id)
    if severity:
        query = query.filter(Alert.severity == severity.upper())
    if status:
        query = query.filter(Alert.status == status.upper())

    return query.order_by(Alert.created_at.desc()).all()


@router.get(
    "/purchase-orders",
    response_model=List[PurchaseOrderResponse],
    summary="List Agent-Recommended Purchase Orders"
)
def list_purchase_orders(
    status: Optional[str] = Query(None, description="Filter by status (DRAFT, APPROVED, REJECTED, SENT)"),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves purchase orders generated autonomously by the agent.
    Draft orders are staged awaiting human pharmacist authorization.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    query = db.query(PurchaseOrder)
    if target_pharmacy_id:
        query = query.filter(PurchaseOrder.pharmacy_id == target_pharmacy_id)
    if status:
        query = query.filter(PurchaseOrder.status == status.upper())

    return query.order_by(PurchaseOrder.created_at.desc()).all()


@router.post(
    "/purchase-orders/{order_id}/approval",
    summary="Human-in-the-Loop Pharmacist Authorization & Memory Update"
)
def approve_or_reject_purchase_order(
    order_id: str,
    approval_req: PurchaseOrderApprovalRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Step 5 of Autonomous Multi-Agent Cycle:
    - Pharmacist authorizes (APPROVE) or rejects (REJECT) a draft purchase order.
    - Commits human decision into Episodic Long-Term Memory to continuously improve future agent reasoning.
    """
    if approval_req.action.upper() not in ["APPROVE", "REJECT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be either 'APPROVE' or 'REJECT'."
        )

    result = multi_agent_orchestrator.process_pharmacist_decision(
        po_id=order_id,
        action=approval_req.action,
        pharmacist_id=current_user.id,
        db=db,
        notes=approval_req.notes
    )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=result["message"])

    return result


@router.get(
    "/memory",
    response_model=List[AgentMemoryResponse],
    summary="View Learned Long-Term Episodic Memory"
)
def get_agent_memory(
    memory_type: Optional[str] = None,
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Inspects episodic knowledge and learned preferences stored by the agent across past human interactions.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    query = db.query(AgentMemory)
    if target_pharmacy_id:
        query = query.filter(AgentMemory.pharmacy_id == target_pharmacy_id)
    if memory_type:
        query = query.filter(AgentMemory.memory_type == memory_type)

    return query.order_by(AgentMemory.timestamp.desc()).all()


@router.get(
    "/audit-logs",
    response_model=List[AgentActionLogResponse],
    summary="View Agent Autonomous Action & Decision Logs"
)
def get_agent_audit_logs(
    limit: int = Query(50, le=200),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves full auditable trail of all agent reasoning steps, confidence scores, and actions.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    query = db.query(AgentActionLog)
    if target_pharmacy_id:
        query = query.filter(AgentActionLog.pharmacy_id == target_pharmacy_id)

    return query.order_by(AgentActionLog.timestamp.desc()).limit(limit).all()
