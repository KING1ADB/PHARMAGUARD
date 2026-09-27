from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

from ...database.database import get_db
from ...services.whatsapp_service import (
    WHATSAPP_VERIFY_TOKEN,
    verify_whatsapp_webhook_signature,
    process_inbound_whatsapp_message,
    send_whatsapp_message
)

router = APIRouter(prefix="/integrations/whatsapp", tags=["WhatsApp Business Integration"])


@router.get("/webhook", summary="Meta WhatsApp Webhook Verification Challenge")
def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Standard Meta Graph API Webhook verification handshake.
    """
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        return int(hub_challenge) if hub_challenge and hub_challenge.isdigit() else hub_challenge

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch."
    )


@router.post("/webhook", summary="Inbound WhatsApp Message & Action Handler")
async def receive_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Processes incoming messages from Meta WhatsApp Cloud API:
    - Verifies HMAC SHA-256 signature.
    - Extracts sender phone number & text body.
    - Executes authorized pharmacist actions (APPROVE, REJECT, REPORT).
    """
    body_bytes = await request.body()
    if not verify_whatsapp_webhook_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WhatsApp webhook signature."
        )

    try:
        data = await request.json()
    except Exception:
        return {"status": "INVALID_JSON"}

    # Extract Meta WhatsApp webhook message format
    entries = data.get("entry", [])
    processed_events = []

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                from_phone = msg.get("from")
                msg_type = msg.get("type")
                
                body_text = ""
                if msg_type == "text":
                    body_text = msg.get("text", {}).get("body", "")
                elif msg_type == "interactive":
                    # Button reply
                    btn_reply = msg.get("interactive", {}).get("button_reply", {})
                    body_text = btn_reply.get("id") or btn_reply.get("title", "")

                if from_phone and body_text:
                    res = process_inbound_whatsapp_message(
                        from_phone=from_phone,
                        message_text=body_text,
                        db=db
                    )
                    processed_events.append(res)

    return {"status": "SUCCESS", "events_processed": len(processed_events), "results": processed_events}
