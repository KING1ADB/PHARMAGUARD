from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from ..database.models.entities import Medicine


# Curated, verified pharmaceutical intelligence catalog
MEDICINE_CLINICAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "Insulin": {
        "dci": "Human Insulin / Insulin Analog",
        "category": "Antidiabetic",
        "storage_temperature": "2°C to 8°C (Strict Cold Chain - Do Not Freeze)",
        "storage_conditions": "Protect from direct sunlight and heat. Once opened, in-use vials can be kept at room temperature <25°C for 28 days.",
        "regulatory_schedule": "List I (Prescription Required)",
        "atc_code": "A10A",
        "who_essential": True,
        "generic_equivalents": ["Insulatard HM", "Mixtard 30 HM", "Actrapid", "Humulin N", "Novolin"],
        "handling_notes": "Requires unbroken temperature monitoring during transit and dedicated pharmacy refrigerator storage."
    },
    "Artemether / Lumefantrine": {
        "dci": "Artemether + Lumefantrine",
        "category": "Antimalarial",
        "storage_temperature": "15°C to 30°C (Controlled Room Temperature)",
        "storage_conditions": "Store in original blister pack to protect from moisture and light.",
        "regulatory_schedule": "List I / Over-The-Counter for first-line malaria management in endemic zones",
        "atc_code": "P01BF01",
        "who_essential": True,
        "generic_equivalents": ["Coartem", "Riamet", "Lumartem", "Artefan", "Co-Arinate"],
        "handling_notes": "First-line Artemisinin-based Combination Therapy (ACT) recommended by WHO."
    },
    "Amoxicilline / Acide Clavulanique": {
        "dci": "Amoxicillin + Clavulanic Acid",
        "category": "Antibiotic (Beta-lactam / Penicillin)",
        "storage_temperature": "15°C to 25°C (Tablets) / 2°C to 8°C (Reconstituted Oral Suspensions)",
        "storage_conditions": "Reconstituted oral liquid suspensions must be refrigerated and discarded after 7-10 days.",
        "regulatory_schedule": "List I (Prescription Only - Rx)",
        "atc_code": "J01CR02",
        "who_essential": True,
        "generic_equivalents": ["Augmentin", "Curam", "Clamentin", "Amoksiklav", "Biomox"],
        "handling_notes": "High humidity sensitivity; blisters should not be compromised prior to dispensing."
    },
    "Metformine": {
        "dci": "Metformin Hydrochloride",
        "category": "Antidiabetic (Biguanide)",
        "storage_temperature": "15°C to 25°C",
        "storage_conditions": "Store in tight, light-resistant containers away from excessive moisture.",
        "regulatory_schedule": "List I (Prescription Required)",
        "atc_code": "A10BA02",
        "who_essential": True,
        "generic_equivalents": ["Glucophage", "Metfor", "Diaformin", "Glucomin", "Siofor"],
        "handling_notes": "First-line oral pharmacotherapy for Type 2 Diabetes Mellitus."
    },
    "Paracetamol": {
        "dci": "Paracetamol (Acetaminophen)",
        "category": "Analgesic / Antipyretic",
        "storage_temperature": "15°C to 25°C",
        "storage_conditions": "Protect from excessive heat and direct moisture.",
        "regulatory_schedule": "Over-The-Counter (OTC)",
        "atc_code": "N02BE01",
        "who_essential": True,
        "generic_equivalents": ["Doliprane", "Efferalgan", "Panadol", "Paralyoc", "Perfalgan"],
        "handling_notes": "Standard first-line analgesic and antipyretic."
    }
}


class MedicineIntelligenceService:
    """
    PharmaGuard Verified Medicine Intelligence Layer (Phase 4).
    
    Provides verified clinical, regulatory, storage, and brand/generic mappings.
    
    ===========================================================================
    STRICT CLINICAL BOUNDARY & SAFETY COMPLIANCE:
    PharmaGuard AI is an operational pharmacy inventory employee.
    The system DOES NOT diagnose patient conditions, prescribe medication,
    or replace licensed human pharmacists under any circumstances.
    ===========================================================================
    """
    SAFETY_DISCLAIMER = (
        "PharmaGuard AI Medicine Intelligence is restricted to operational logistics, "
        "storage compliance, and generic equivalence mapping. It does NOT provide clinical "
        "diagnoses, medical prescriptions, or patient-specific treatment advice."
    )

    @classmethod
    def get_medicine_intelligence(
        cls,
        medicine_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Retrieves verified storage conditions, regulatory status, and brand/generic mappings for a medicine.
        """
        med = db.query(Medicine).filter(Medicine.id == medicine_id).first()
        if not med:
            return {"status": "NOT_FOUND", "message": f"Medicine {medicine_id} not found."}

        # Search curated clinical profile
        matched_profile = None
        for key, prof in MEDICINE_CLINICAL_PROFILES.items():
            if (
                key.lower() in med.generic_name.lower()
                or key.lower() in med.brand_names.lower()
                or (med.category and key.lower() in med.category.lower())
            ):
                matched_profile = prof
                break

        if not matched_profile:
            # Fallback to database columns
            matched_profile = {
                "dci": med.generic_name,
                "category": med.category or "General Medicine",
                "storage_temperature": med.storage_temperature or "15°C to 25°C",
                "storage_conditions": med.storage_conditions or "Store in dry place away from heat",
                "regulatory_schedule": med.regulatory_schedule or "Prescription Required (Rx)",
                "atc_code": med.atc_code or "N/A",
                "who_essential": med.is_essential if med.is_essential is not None else True,
                "generic_equivalents": [med.brand_names],
                "handling_notes": "Standard pharmaceutical handling protocols."
            }

        # Find brand equivalents in database
        brand_equivalents_in_db = (
            db.query(Medicine)
            .filter(Medicine.generic_name == med.generic_name, Medicine.id != med.id)
            .all()
        )
        db_brand_names = [m.brand_names for m in brand_equivalents_in_db]

        all_equivalents = list(set(matched_profile["generic_equivalents"] + db_brand_names))

        return {
            "status": "SUCCESS",
            "medicine_id": med.id,
            "brand_name": med.brand_names,
            "generic_name": med.generic_name,
            "category": med.category,
            "dosage_form": med.dosage_form,
            "barcode": med.barcode,
            "storage_intelligence": {
                "temperature": matched_profile["storage_temperature"],
                "conditions": matched_profile["storage_conditions"],
                "handling_notes": matched_profile["handling_notes"],
                "requires_cold_chain": "2°C" in matched_profile["storage_temperature"]
            },
            "regulatory_intelligence": {
                "schedule": matched_profile["regulatory_schedule"],
                "atc_code": matched_profile["atc_code"],
                "who_essential_list": matched_profile["who_essential"]
            },
            "therapeutic_equivalents": {
                "dci": matched_profile["dci"],
                "equivalent_brands": all_equivalents,
                "equivalent_count": len(all_equivalents)
            },
            "safety_guardrail": {
                "compliant": True,
                "disclaimer": cls.SAFETY_DISCLAIMER
            }
        }
