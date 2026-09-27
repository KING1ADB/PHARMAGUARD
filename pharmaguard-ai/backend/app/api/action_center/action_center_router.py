import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...database.models.entities import (
    User,
    PurchaseOrder,
    Supplier,
    Pharmacy,
    AgentActionLog,
    AgentMemory
)
from ...database.schemas.entities_schema import (
    PurchaseOrderResponse,
    ActionDecisionRequest,
    ActionExecutionResponse
)
from ...security.jwt_rbac import get_current_active_user, require_role, UserRole
from ...agents.communication_agent.supplier_communication_agent import supplier_comm_agent
from ...memory.long_term.episodic_memory import EpisodicMemoryManager

router = APIRouter(prefix="/action-center", tags=["AI Action Center"])


@router.get("/pending", response_model=List[PurchaseOrderResponse], summary="Get Pending AI Recommendations")
def get_pending_recommendations(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves all staged DRAFT purchase orders generated autonomously by PharmaGuard AI agents.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    query = db.query(PurchaseOrder).filter(PurchaseOrder.status == "DRAFT")
    if target_pharmacy_id:
        query = query.filter(PurchaseOrder.pharmacy_id == target_pharmacy_id)

    return query.order_by(PurchaseOrder.created_at.desc()).all()


@router.get("/queue", response_model=List[PurchaseOrderResponse], summary="Get Action Approval Queue")
def get_action_approval_queue(
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Alias for the pharmacist review and decision queue.
    """
    return get_pending_recommendations(pharmacy_id=pharmacy_id, current_user=current_user, db=db)


@router.post("/decide/{po_id}", response_model=Dict[str, Any], summary="Execute Pharmacist Decision (APPROVE / MODIFY / REJECT)")
def execute_pharmacist_decision(
    po_id: str,
    decision: ActionDecisionRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Pharmacist Human-in-the-Loop Decision Gate:
    - APPROVE: Marks order APPROVED, optionally dispatches immediately to distributor.
    - MODIFY: Updates quantities/supplier/lines based on human adjustments, approves, and records learning.
    - REJECT: Cancels order, records rationale into episodic memory.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
    if not po:
        raise HTTPException(status_code=404, detail=f"Purchase order {po_id} not found.")

    act = decision.action.upper()
    if act not in ["APPROVE", "MODIFY", "REJECT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be APPROVE, MODIFY, or REJECT."
        )

    # 1. Handle Modifications
    if act == "MODIFY":
        if decision.modified_supplier_id:
            po.supplier_id = decision.modified_supplier_id
        if decision.modified_items:
            items_dict = [it.model_dump() for it in decision.modified_items]
            po.items_json = json.dumps(items_dict)
            po.total_amount_fcfa = sum(it.get("subtotal_fcfa", it.get("quantity", 1) * it.get("unit_cost_fcfa", 0)) for it in items_dict)

        po.status = "APPROVED"
        po.approved_by = current_user.id
        po.approved_at = datetime.now(timezone.utc)
        
        # Enhanced Memory Learning: Store human adjustment pattern
        EpisodicMemoryManager.record_decision_feedback(
            pharmacy_id=po.pharmacy_id,
            memory_type="ORDER_MODIFICATION_LEARNING",
            feedback_data={
                "po_id": po.id,
                "action": "MODIFIED_AND_APPROVED",
                "pharmacist_id": current_user.id,
                "notes": decision.notes or "Adjusted quantities/supplier before authorization",
                "new_total_fcfa": po.total_amount_fcfa
            },
            confidence=1.0,
            db=db
        )

    elif act == "APPROVE":
        po.status = "APPROVED"
        po.approved_by = current_user.id
        po.approved_at = datetime.now(timezone.utc)

        # Store approval learning
        EpisodicMemoryManager.record_decision_feedback(
            pharmacy_id=po.pharmacy_id,
            memory_type="ORDER_AUTHORIZATION_FEEDBACK",
            feedback_data={
                "po_id": po.id,
                "action": "APPROVED",
                "pharmacist_id": current_user.id,
                "notes": decision.notes or "Authorized standard replenishment"
            },
            confidence=1.0,
            db=db
        )

    elif act == "REJECT":
        po.status = "REJECTED"
        po.approved_by = current_user.id
        po.approved_at = datetime.now(timezone.utc)

        # Store rejection learning
        EpisodicMemoryManager.record_decision_feedback(
            pharmacy_id=po.pharmacy_id,
            memory_type="ORDER_REJECTION_FEEDBACK",
            feedback_data={
                "po_id": po.id,
                "action": "REJECTED",
                "pharmacist_id": current_user.id,
                "notes": decision.notes or "Rejected recommendation"
            },
            confidence=1.0,
            db=db
        )

    db.commit()

    # 2. Auto-dispatch if requested and approved
    dispatch_info = None
    if po.status == "APPROVED" and decision.auto_dispatch:
        dispatch_res = supplier_comm_agent.dispatch_approved_order(
            po_id=po.id,
            channel=decision.dispatch_channel,
            db=db
        )
        dispatch_info = dispatch_res

    return {
        "status": "SUCCESS",
        "po_id": po.id,
        "decision": act,
        "order_status": po.status,
        "approved_by": current_user.id,
        "timestamp": po.approved_at.isoformat() if po.approved_at else None,
        "dispatch": dispatch_info,
        "learning_logged": True
    }


@router.get("/executions", response_model=List[ActionExecutionResponse], summary="Track Real-World Order Executions")
def track_action_executions(
    status: Optional[str] = Query(None, description="Filter by status (DISPATCHED, CONFIRMED, DELIVERED)"),
    pharmacy_id: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Tracks lifecycle of dispatched distributor orders:
    - Dispatch channel & timestamp.
    - Distributor tracking reference & acknowledgment status.
    - Delivery reception and stock update status.
    """
    target_pharmacy_id = pharmacy_id or current_user.pharmacy_id
    query = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(["APPROVED", "DISPATCHED", "CONFIRMED", "DELIVERED"]))
    if target_pharmacy_id:
        query = query.filter(PurchaseOrder.pharmacy_id == target_pharmacy_id)
    if status:
        query = query.filter(PurchaseOrder.status == status.upper())

    return query.order_by(PurchaseOrder.created_at.desc()).all()


@router.post("/executions/{po_id}/supplier-response", summary="Record Distributor Response Acknowledgment")
def record_supplier_response_ack(
    po_id: str,
    response_status: str = Query(..., description="CONFIRMED, OUT_OF_STOCK, PARTIAL_DELIVERY, DELIVERED"),
    actual_delivery_days: Optional[int] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.PHARMACIST])),
    db: Session = Depends(get_db)
):
    """
    Ingests supplier confirmation/delivery events and auto-recalculates supplier reliability scoring.
    """
    result = supplier_comm_agent.record_supplier_response(
        po_id=po_id,
        response_status=response_status,
        db=db,
        actual_delivery_days=actual_delivery_days,
        notes=notes
    )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result
