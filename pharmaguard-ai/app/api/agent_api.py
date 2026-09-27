import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Alert, PurchaseOrder, AgentAction
from ..database.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentDecisionCycleResponse,
    DailyBriefingResponse,
    AlertResponse,
    PurchaseOrderResponse
)
from ..agent.orchestrator import orchestrator
from ..tools.notification_tools import generate_daily_report

router = APIRouter(prefix="/agent", tags=["AI Operations Agent"])


@router.post("/cycle", response_model=AgentDecisionCycleResponse)
def trigger_agent_decision_cycle(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """
    Triggers the autonomous 5-stage decision cycle:
    Observe -> Analyze -> Reason -> Recommend -> Request Approval -> Act -> Learn.
    """
    result = orchestrator.run_autonomous_cycle(db, pharmacy_id)
    return result


@router.post("/query", response_model=AgentQueryResponse)
def interact_with_agent(
    request: AgentQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Interactive endpoint for queries like "Analyze this pharmacy" or "Check stock of Insulin".
    """
    pharmacy_id = request.pharmacy_id or "PHARM-DLA-001"
    response_data = orchestrator.handle_user_query(
        db, pharmacy_id, request.query, channel=request.channel
    )
    return response_data


@router.get("/report", response_model=DailyBriefingResponse)
def get_daily_operational_report(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """
    Returns the daily operational intelligence report with critical alerts and recommendations.
    """
    report = generate_daily_report(pharmacy_id, db)
    
    draft_orders_count = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.pharmacy_id == pharmacy_id, PurchaseOrder.status == "DRAFT")
        .count()
    )

    return {
        "pharmacy_name": report["pharmacy_name"],
        "date": report["date"],
        "critical_stockouts_count": report["critical_alerts_count"],
        "expiring_soon_count": len(report["critical_alerts"]),
        "total_inventory_value_fcfa": report["capital_at_expiry_risk_fcfa"],
        "briefing_markdown": report["report_markdown"],
        "draft_purchase_orders_count": draft_orders_count
    }


@router.get("/alerts", response_model=List[AlertResponse])
def list_active_alerts(
    pharmacy_id: str = "PHARM-DLA-001",
    status: str = "ACTIVE",
    db: Session = Depends(get_db)
):
    """Lists real-time inventory and supply chain risk alerts."""
    alerts = (
        db.query(Alert)
        .filter(Alert.pharmacy_id == pharmacy_id, Alert.status == status)
        .order_by(Alert.created_at.desc())
        .all()
    )
    return alerts


@router.get("/purchase-orders", response_model=List[PurchaseOrderResponse])
def list_purchase_orders(
    pharmacy_id: str = "PHARM-DLA-001",
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lists draft and approved supplier purchase orders."""
    query = db.query(PurchaseOrder).filter(PurchaseOrder.pharmacy_id == pharmacy_id)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    orders = query.order_by(PurchaseOrder.created_at.desc()).all()

    formatted_orders = []
    for o in orders:
        items = json.loads(o.items_json) if isinstance(o.items_json, str) else o.items_json
        formatted_orders.append({
            "id": o.id,
            "pharmacy_id": o.pharmacy_id,
            "supplier_id": o.supplier_id,
            "status": o.status,
            "total_amount_fcfa": o.total_amount_fcfa,
            "items": items,
            "reasoning": o.reasoning,
            "created_at": o.created_at,
            "approved_at": o.approved_at
        })
    return formatted_orders


@router.post("/purchase-orders/{po_id}/approve")
def approve_draft_purchase_order(
    po_id: str,
    db: Session = Depends(get_db)
):
    """
    Human-in-the-Loop Approval: Pharmacist authorizes a pre-drafted purchase order.
    """
    result = orchestrator.approve_purchase_order(db, po_id)
    if result.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/audit-logs")
def get_agent_audit_logs(
    pharmacy_id: str = "PHARM-DLA-001",
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Returns auditable AgentAction logs for transparency and compliance."""
    actions = (
        db.query(AgentAction)
        .filter(AgentAction.pharmacy_id == pharmacy_id)
        .order_by(AgentAction.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "agent_name": a.agent_name,
            "action_type": a.action_type,
            "reasoning": a.reasoning,
            "confidence_score": a.confidence_score,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None
        }
        for a in actions
    ]
