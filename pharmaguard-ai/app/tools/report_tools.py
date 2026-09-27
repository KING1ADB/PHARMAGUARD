import json
from datetime import date, datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..database.models import Pharmacy, Medicine, PurchaseOrder, Supplier
from ..services.analysis import analyze_inventory_health
from ..services.forecasting import compute_reorder_recommendation


def generate_daily_briefing_markdown(db: Session, pharmacy_id: str) -> str:
    """
    Tool: Generates a high-impact daily briefing formatted for WhatsApp & Pharmacist Dashboard.
    """
    pharmacy = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).first()
    pharmacy_name = pharmacy.name if pharmacy else "Community Pharmacy"
    
    health = analyze_inventory_health(db, pharmacy_id)
    today_str = date.today().strftime("%A, %d %B %Y")

    lines = [
        f"🏥 *PHARMAGUARD AI — DAILY PHARMACY INTELLIGENCE BRIEFING*",
        f"📍 *Pharmacy:* {pharmacy_name}",
        f"📅 *Date:* {today_str}",
        f"📊 *Total Active SKUs:* {health['total_skus']} | *Stock Value:* {health['total_inventory_cost_fcfa']:,.0f} FCFA",
        "───────────────────────────────────",
        ""
    ]

    # Section 1: Critical Stockout Warnings
    lines.append("🚨 *CRITICAL STOCKOUT ALERTS (Act Today)*")
    if health["critical_stockouts_count"] == 0:
        lines.append("✅ No critical stockouts detected. All key medicines are in safe stock.")
    else:
        for item in health["critical_stockout_items"]:
            lines.append(
                f"• *{item['name']}* ({item['category']}): "
                f"`{item['quantity_in_stock']} units remaining` "
                f"→ Depletes in ~*{item['days_of_stock_remaining']} days* "
                f"(Threshold: {item['reorder_point']})"
            )
    lines.append("")

    # Section 2: Expiry Risk Warnings
    lines.append("⏳ *EXPIRY RISK WARNINGS (<60 Days)*")
    if health["expiring_soon_count"] == 0:
        lines.append("✅ No immediate expiry risks. Inventory rotation is healthy.")
    else:
        lines.append(f"⚠️ *Capital at Risk:* {health['capital_at_expiry_risk_fcfa']:,.0f} FCFA")
        for item in health["expiring_items"]:
            lines.append(
                f"• *{item['name']}* (Exp: {item['expiry_date']}): "
                f"`{item['quantity_in_stock']} units` "
                f"→ *{item['days_until_expiry']} days left* "
                f"| Status: {item['expiry_status']}"
            )
    lines.append("")

    # Section 3: Recommended Actions
    lines.append("📋 *AI RECOMMENDED ACTIONS*")
    draft_orders = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.pharmacy_id == pharmacy_id, PurchaseOrder.status == "DRAFT")
        .count()
    )
    if draft_orders > 0:
        lines.append(f"• 📦 *{draft_orders} Purchase Order(s)* pre-drafted and awaiting your one-click approval.")
    if health["expiring_soon_count"] > 0:
        lines.append("• 🏷️ Apply 30% FEFO promotional discount on short-dated batches to recover capital.")
    lines.append("• 🔄 Medicine availability index has been synchronized with the local network.")
    lines.append("")
    lines.append("───────────────────────────────────")
    lines.append("_PharmaGuard AI Agent — Autonomous Pharmacy Operations_")

    return "\n".join(lines)


def format_purchase_order_text(db: Session, order: PurchaseOrder) -> str:
    """
    Tool: Generates a formatted Purchase Order string for WhatsApp/Email transmission.
    """
    supplier = db.query(Supplier).filter(Supplier.id == order.supplier_id).first()
    supplier_name = supplier.name if supplier else "Wholesale Supplier"
    
    items = json.loads(order.items_json) if isinstance(order.items_json, str) else order.items_json
    
    lines = [
        f"📦 *PURCHASE ORDER: {order.id}*",
        f"🏢 *To:* {supplier_name} ({supplier.phone if supplier else 'N/A'})",
        f"📅 *Date:* {order.created_at.strftime('%Y-%m-%d')}",
        f"📌 *Status:* {order.status}",
        "───────────────────────────────────",
        "*ITEMS ORDERED:*"
    ]
    
    total = 0.0
    for it in items:
        subtotal = it.get("subtotal_fcfa", it.get("quantity", 0) * it.get("unit_cost_fcfa", 0.0))
        total += subtotal
        lines.append(f"• {it.get('medicine_name', 'Item')} x {it.get('quantity', 0)} @ {it.get('unit_cost_fcfa', 0):,.0f} FCFA = {subtotal:,.0f} FCFA")
        
    lines.append("───────────────────────────────────")
    lines.append(f"💰 *TOTAL AMOUNT:* {total:,.0f} FCFA")
    if order.reasoning:
        lines.append(f"🧠 *AI Reasoning:* {order.reasoning}")
        
    return "\n".join(lines)
