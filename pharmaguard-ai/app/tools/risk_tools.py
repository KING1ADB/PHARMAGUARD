from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..database.models import Medicine, Supplier
from ..services.analysis import get_medicine_risk_profile


def calculate_expiry_risks(db: Session, pharmacy_id: str) -> Dict[str, Any]:
    """
    Tool: Flags medicines facing expiration and recommends proactive mitigation actions.
    """
    medicines = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).all()
    
    expired = []
    critical_30 = []
    warning_60 = []
    notice_90 = []

    for med in medicines:
        profile = get_medicine_risk_profile(db, med)
        status = profile["expiry_status"]
        if status == "EXPIRED":
            profile["action_recommendation"] = "Quarantine & Safe Disposal / Log Defect"
            expired.append(profile)
        elif status == "CRITICAL":
            profile["action_recommendation"] = "Immediate 40-50% Clearance Discount or Supplier Return"
            critical_30.append(profile)
        elif status == "WARNING":
            profile["action_recommendation"] = "Apply 20-30% Fast-Movement Promotion or Prioritize Dispensing"
            warning_60.append(profile)
        elif status == "NOTICE":
            profile["action_recommendation"] = "FEFO (First-Expired, First-Out) Priority Protocol"
            notice_90.append(profile)

    capital_loss_threat = sum(
        p["quantity_in_stock"] * p["unit_cost_fcfa"] for p in expired + critical_30 + warning_60
    )

    return {
        "total_at_risk_skus": len(expired) + len(critical_30) + len(warning_60),
        "capital_loss_threat_fcfa": round(capital_loss_threat, 2),
        "expired_items": expired,
        "critical_30_days": critical_30,
        "warning_60_days": warning_60,
        "notice_90_days": notice_90
    }


def detect_supply_chain_vulnerabilities(db: Session, pharmacy_id: str) -> List[Dict[str, Any]]:
    """
    Tool: Analyzes supplier reliability, lead times, and single-source bottlenecks.
    """
    medicines = db.query(Medicine).filter(Medicine.pharmacy_id == pharmacy_id).all()
    suppliers = {s.id: s for s in db.query(Supplier).all()}

    vulnerabilities = []
    for med in medicines:
        profile = get_medicine_risk_profile(db, med)
        supplier = suppliers.get(med.supplier_id)
        
        # Flag if item is critical stock and supplier lead time > 2 days or reliability < 0.90
        if profile["stockout_risk_level"] in ["CRITICAL", "HIGH"] and supplier:
            if supplier.lead_time_days >= 3 or supplier.reliability_score < 0.90:
                vulnerabilities.append({
                    "medicine_id": med.id,
                    "medicine_name": med.name,
                    "current_stock": med.quantity_in_stock,
                    "days_remaining": profile["days_of_stock_remaining"],
                    "supplier_name": supplier.name,
                    "supplier_lead_time_days": supplier.lead_time_days,
                    "supplier_reliability": supplier.reliability_score,
                    "risk_assessment": f"Long lead time ({supplier.lead_time_days}d) exceeds safe stock window!"
                })

    return vulnerabilities
