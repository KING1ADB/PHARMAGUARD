import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.database import get_db
from ..database.models import Alert, PurchaseOrder, AgentLog
from ..database.schemas import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentDecisionCycleResponse,
    DailyBriefingResponse,
    AlertResponse,
    PurchaseOrderResponse
)
from ..agent.orchestrator import orchestrator
from ..tools.report_tools import generate_daily_briefing_markdown
from ..services.analysis import analyze_inventory_health

router = APIRouter(prefix="/agent", tags=["AI Operations Agent"])


@router.post("/cycle", response_model=AgentDecisionCycleResponse)
def trigger_agent_decision_cycle(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """
    Triggers the autonomous 5-stage decision cycle:
    Observe -> Analyze -> Plan -> Act -> Learn.
    """
    result = orchestrator.run_autonomous_cycle(db, pharmacy_id)
    return result


@router.post("/query", response_model=AgentQueryResponse)
def interact_with_agent(
    request: AgentQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Interactive conversational endpoint for Pharmacists and Patients (Web & WhatsApp).
    """
    pharmacy_id = request.pharmacy_id or "PHARM-DLA-001"
    response_data = orchestrator.handle_user_query(
        db, pharmacy_id, request.query, channel=request.channel
    )
    return response_data


@router.get("/briefing", response_model=DailyBriefingResponse)
def get_daily_operational_briefing(
    pharmacy_id: str = "PHARM-DLA-001",
    db: Session = Depends(get_db)
):
    """
    Returns the daily operational intelligence briefing formatted for WhatsApp.
    """
    health = analyze_inventory_health(db, pharmacy_id)
    briefing_md = generate_daily_briefing_markdown(db, pharmacy_id)
    
    draft_orders_count = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.pharmacy_id == pharmacy_id, PurchaseOrder.status == "DRAFT")
        .count()
    )

    return {
        "pharmacy_name": "Pharmacie du Centre - Douala",
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "critical_stockouts_count": health["critical_stockouts_count"],
        "expiring_soon_count": health["expiring_soon_count"],
        "total_inventory_value_fcfa": health["total_inventory_cost_fcfa"],
        "briefing_markdown": briefing_md,
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
    """Lists draft and approved automated supplier purchase orders."""
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


@router.get("/logs")
def get_agent_decision_logs(
    pharmacy_id: str = "PHARM-DLA-001",
    limit: int = 30,
    db: Session = Depends(get_db)
):
    """Returns chronological execution logs of the AI agent decision loop."""
    logs = (
        db.query(AgentLog)
        .filter(AgentLog.pharmacy_id == pharmacy_id)
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id,
            "cycle_id": l.cycle_id,
            "phase": l.phase,
            "agent_name": l.agent_name,
            "summary": l.summary,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]
