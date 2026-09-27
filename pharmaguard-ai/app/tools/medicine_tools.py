from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from ..database.models import Medicine


def get_medicine_info(db: Session, medicine_id: str) -> Optional[Dict[str, Any]]:
    """
    Tool: Retrieves official catalog details and clinical metadata for a medicine.
    """
    med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not med:
        return None
    return {
        "id": med.id,
        "name": med.name,
        "generic_name": med.generic_name,
        "category": med.category,
        "strength": med.strength,
        "form": med.form
    }


def search_medicine_catalog(db: Session, query: str) -> List[Dict[str, Any]]:
    """
    Tool: Searches medicine master catalog by name or generic molecule.
    """
    search_term = f"%{query.strip()}%"
    meds = (
        db.query(Medicine)
        .filter(
            or_(
                Medicine.name.ilike(search_term),
                Medicine.generic_name.ilike(search_term),
                Medicine.category.ilike(search_term)
            )
        )
        .all()
    )
    return [
        {
            "id": m.id,
            "name": m.name,
            "generic_name": m.generic_name,
            "category": m.category,
            "strength": m.strength,
            "form": m.form
        }
        for m in meds
    ]


def get_generic_substitutes(db: Session, generic_name: str) -> List[Dict[str, Any]]:
    """
    Tool: Finds therapeutic equivalent brands with identical generic molecule.
    """
    meds = db.query(Medicine).filter(Medicine.generic_name.ilike(f"%{generic_name.strip()}%")).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "generic_name": m.generic_name,
            "strength": m.strength,
            "form": m.form
        }
        for m in meds
    ]
