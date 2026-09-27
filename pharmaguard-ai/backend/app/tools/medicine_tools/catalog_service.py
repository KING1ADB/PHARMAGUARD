from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ...database.models.entities import Medicine


def search_medicine(query: str, db: Session) -> List[Dict[str, Any]]:
    """
    Tool: Search medicine catalog by generic molecule, brand name, or therapeutic category.
    """
    search_term = f"%{query.strip()}%"
    meds = (
        db.query(Medicine)
        .filter(
            or_(
                Medicine.brand_names.ilike(search_term),
                Medicine.generic_name.ilike(search_term),
                Medicine.category.ilike(search_term)
            )
        )
        .all()
    )
    return [
        {
            "id": m.id,
            "brand_names": m.brand_names,
            "generic_name": m.generic_name,
            "category": m.category,
            "strength": m.strength,
            "dosage_form": m.dosage_form
        }
        for m in meds
    ]


def identify_medicine(query_name: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Tool: Identifies the exact medicine entity from a user prompt or text mention.
    """
    matches = search_medicine(query_name, db)
    return matches[0] if matches else None


def retrieve_medicine_information(medicine_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Tool: Retrieves official catalog specifications and clinical metadata for a medicine ID.
    """
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not med:
        return None
    return {
        "id": med.id,
        "brand_names": med.brand_names,
        "generic_name": med.generic_name,
        "category": med.category,
        "strength": med.strength,
        "dosage_form": med.dosage_form
    }
