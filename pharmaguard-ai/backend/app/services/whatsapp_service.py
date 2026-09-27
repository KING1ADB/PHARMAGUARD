import os
import hmac
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx
from sqlalchemy.orm import Session

from ..database.models.entities import User, PurchaseOrder, Pharmacy
from ..agents.orchestrator.morning_orchestrator import multi_agent_orchestrator
from ..agents.communication_agent.supplier_communication_agent import supplier_comm_agent

logger = logging.getLogger("WhatsAppService")

WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "mock_whatsapp_token_for_dev")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "100000000000000")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "pharmaguard_webhook_verification_token_2026")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "pharmaguard_meta_app_secret")


def verify_whatsapp_webhook_signature(payload_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verifies Meta X-Hub-Signature-256 header using the Meta App Secret.
    """
    if not signature_header:
        # Permissive in dev if secret not configured
        if WHATSAPP_APP_SECRET == "pharmaguard_meta_app_secret":
            return True
        return False

    expected_sig = "sha256=" + hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature_header)


def send_whatsapp_message(to_phone: str, message_text: str) -> Dict[str, Any]:
    """
    Transmits an outbound message or morning intelligence report via WhatsApp Cloud API.
    """
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone.replace("+", "").replace(" ", ""),
        "type": "text",
        "text": {"body": message_text}
    }

    try:
        # In real runtime, if no live Meta token is configured, log cleanly and return structured success
        if WHATSAPP_API_TOKEN == "mock_whatsapp_token_for_dev":
            logger.info(f"[WhatsApp Outbound -> {to_phone}]:\n{message_text}")
            return {"status": "DELIVERED_DEV_MODE", "recipient": to_phone, "length": len(message_text)}

        with httpx.Client(timeout=10.0) as client:
            res = client.post(url, headers=headers, json=payload)
            return res.json()
    except Exception as e:
        logger.error(f"WhatsApp dispatch failed: {str(e)}")
        return {"status": "ERROR", "message": str(e)}


def process_inbound_whatsapp_message(
    from_phone: str,
    message_text: str,
    db: Session
) -> Dict[str, Any]:
    """
    Parses incoming WhatsApp commands from authenticated pharmacists:
    - 'REPORT' or 'BRIEFING' -> Executes and returns live morning intelligence.
    - 'APPROVE <PO_ID>' -> Authorizes draft purchase order & triggers supplier communication dispatch.
    - 'REJECT <PO_ID>' -> Rejects draft purchase order & records feedback.
    - 'HELP' -> Returns available commands.
    """
    # 1. Authenticate Pharmacist by Phone Number
    clean_phone = from_phone.replace("+", "").replace(" ", "")
    user = (
        db.query(User)
        .filter(User.phone.contains(clean_phone[-8:]) | (User.phone == clean_phone))
        .first()
    )

    if not user or user.role not in ["PHARMACIST", "OWNER"]:
        return {
            "status": "UNAUTHORIZED",
            "reply_text": "⚠️ Access Denied: Phone number is not registered as an authorized pharmacist on PharmaGuard AI."
        }

    text_upper = message_text.strip().upper()

    # 2. Command: MORNING REPORT
    if text_upper in ["REPORT", "BRIEFING", "STATUS", "MORNING"]:
        cycle_res = multi_agent_orchestrator.execute_morning_cycle(user.pharmacy_id, db)
        markdown_rep = cycle_res["report"]["report_markdown"]
        reply_msg = f"🏥 *PHARMAGUARD AI INTELLIGENCE BRIEFING*\n\n{markdown_rep}"
        send_whatsapp_message(from_phone, reply_msg)
        return {"status": "REPORT_SENT", "user": user.name, "reply_text": reply_msg}

    # 3. Command: APPROVE PO
    if text_upper.startswith("APPROVE") or text_upper.startswith("CONFIRM"):
        parts = text_upper.split()
        if len(parts) < 2:
            return {
                "status": "INVALID_SYNTAX",
                "reply_text": "❓ Please specify the Order ID. Example: `APPROVE PO-20260927-ABC123`"
            }

        target_po_id = parts[1].strip()
        # Authorize order
        approval_res = multi_agent_orchestrator.process_pharmacist_decision(
            po_id=target_po_id,
            action="APPROVE",
            pharmacist_id=user.id,
            db=db,
            notes="Authorized via WhatsApp Business Interaction"
        )

        if approval_res.get("status") == "ERROR":
            reply_msg = f"❌ Error: {approval_res.get('message', 'Order not found')}"
        else:
            # Autonomously dispatch to supplier via Supplier Communication Agent
            dispatch_res = supplier_comm_agent.dispatch_approved_order(
                po_id=target_po_id,
                channel="EMAIL",
                db=db
            )
            reply_msg = (
                f"✅ *PURCHASE ORDER {target_po_id} APPROVED*\n"
                f"Authorized by: {user.name}\n"
                f"Dispatched via: {dispatch_res.get('channel', 'EMAIL')}\n"
                f"Tracking Ref: `{dispatch_res.get('tracking_reference', 'TRK-N/A')}`\n"
                f"Distributor has been officially notified."
            )

        send_whatsapp_message(from_phone, reply_msg)
        return {"status": "PO_APPROVED_AND_DISPATCHED", "po_id": target_po_id, "reply_text": reply_msg}

    # 4. Command: REJECT PO
    if text_upper.startswith("REJECT") or text_upper.startswith("CANCEL"):
        parts = text_upper.split()
        if len(parts) < 2:
            return {
                "status": "INVALID_SYNTAX",
                "reply_text": "❓ Please specify the Order ID. Example: `REJECT PO-20260927-ABC123`"
            }

        target_po_id = parts[1].strip()
        reject_res = multi_agent_orchestrator.process_pharmacist_decision(
            po_id=target_po_id,
            action="REJECT",
            pharmacist_id=user.id,
            db=db,
            notes="Rejected via WhatsApp Business Interaction"
        )

        reply_msg = f"🚫 *PURCHASE ORDER {target_po_id} REJECTED*\nDecision recorded into PharmaGuard memory."
        send_whatsapp_message(from_phone, reply_msg)
        return {"status": "PO_REJECTED", "po_id": target_po_id, "reply_text": reply_msg}

    # Default Help
    help_text = (
        f"👋 Hello {user.name},\n\n"
        f"*PharmaGuard AI WhatsApp Assistant Commands:*\n"
        f"• Send *REPORT* to get current morning intelligence briefing.\n"
        f"• Send *APPROVE <PO_ID>* to authorize & dispatch a draft order.\n"
        f"• Send *REJECT <PO_ID>* to reject an order.\n"
        f"• Send *HELP* for command assistance."
    )
    send_whatsapp_message(from_phone, help_text)
    return {"status": "HELP_SENT", "reply_text": help_text}
