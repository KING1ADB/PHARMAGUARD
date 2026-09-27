from datetime import datetime, timezone
from typing import Dict, Any, Optional


def create_message(title: str, body: str, severity: str = "INFO") -> Dict[str, Any]:
    """
    Tool: Constructs a structured operational message.
    """
    return {
        "title": title,
        "body": body,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def send_notification(recipient: str, message: str, channel: str = "whatsapp") -> Dict[str, Any]:
    """
    Tool: Formats and queues a notification for transmission to the pharmacist.
    """
    return {
        "status": "QUEUED_FOR_DISPATCH",
        "channel": channel,
        "recipient": recipient,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "preview": message[:120] + "..." if len(message) > 120 else message
    }
