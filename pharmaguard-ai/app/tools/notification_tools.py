import json
from datetime import date
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..database.models import Pharmacy, Inventory, Medicine, Supplier, PurchaseOrder
from .risk_tools import calculate_all_inventory_risks, calculate_expiry_risks


def generate_daily_report(pharmacy_id: str, db: Session) -> Dict[str, Any]:
    """
    Tool: Generates daily operational report containing critical alerts, explanations, and recommendations.
    """
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    pharmacy_name = pharmacy.name if pharmacy else "Community Pharmacy"

    # Analyze risks
    stock_risks = calculate_all_inventory_risks(pharmacy_id, db)
    high_risks = [r for r in stock_risks if r.get("risk_level") in ["HIGH", "CRITICAL_STOCKOUT"]]
    
    expiry_info = calculate_expiry_risks(pharmacy_id, db)
    
    # Formulate report
    critical_alerts = []
    for r in high_risks:
        critical_alerts.append({
            "medicine_id": r["medicine_id"],
            "title": f"High Shortage Risk: {r['name']}",
            "reasoning": r["reasoning"],
            "confidence": f"{int(r['confidence_score'] * 100)}%",
            "recommendation": r["recommendation"]
        })

    recommendations = []
    if high_risks:
        recommendations.append(f"Review and authorize automated replenishment for {len(high_risks)} high-risk medicines.")
    if expiry_info["critical_30_days"]:
        recommendations.append(f"Apply 40% FEFO discount on {len(expiry_info['critical_30_days'])} items expiring in <30 days.")
    if not recommendations:
        recommendations.append("All stock levels healthy. Continue standard dispensing operations.")

    # Formatted Markdown summary
    lines = [
        f"🏥 *PHARMAGUARD AI — OPERATIONAL INTELLIGENCE REPORT*",
        f"📍 *Pharmacy:* {pharmacy_name}",
        f"📅 *Date:* {date.today().strftime('%Y-%m-%d')}",
        "───────────────────────────────────",
        f"🚨 *CRITICAL SHORTAGE ALERTS ({len(high_risks)} items):*"
    ]
    if not high_risks:
        lines.append("✅ No critical shortages detected.")
    else:
        for a in critical_alerts:
            lines.append(f"• *{a['title']}* (Confidence: {a['confidence']})\n  _{a['reasoning']}_")

    lines.append("")
    lines.append(f"⏳ *EXPIRY CAPITAL AT RISK:* {expiry_info['capital_at_risk_fcfa']:,.0f} FCFA")
    lines.append("")
    lines.append("📋 *RECOMMENDATIONS:*")
    for rec in recommendations:
        lines.append(f"• {rec}")
    lines.append("───────────────────────────────────")

    return {
        "pharmacy_id": pharmacy_id,
        "pharmacy_name": pharmacy_name,
        "date": date.today().isoformat(),
        "critical_alerts_count": len(high_risks),
        "critical_alerts": critical_alerts,
        "capital_at_expiry_risk_fcfa": expiry_info["capital_at_risk_fcfa"],
        "recommendations": recommendations,
        "report_markdown": "\n".join(lines)
    }


def send_notification(recipient: str, message: str, channel: str = "whatsapp") -> Dict[str, Any]:
    """
    Tool: Dispatches or queues an alert notification for the pharmacist.
    """
    # In production, integrates with WhatsApp Business API / Twilio / SMS Gateway
    return {
        "status": "SENT",
        "channel": channel,
        "recipient": recipient,
        "timestamp": date.today().isoformat(),
        "preview": message[:100] + "..." if len(message) > 100 else message
    }
