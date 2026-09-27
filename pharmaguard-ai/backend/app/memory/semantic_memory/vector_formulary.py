from typing import List, Dict, Any, Optional

# Clinical Safety Rules & Therapeutic Equivalents
FORMULARY_KNOWLEDGE = {
    "Artemether + Lumefantrine": {
        "therapeutic_class": "First-line ACT Antimalarial",
        "standard_dosage": "20/120mg (6-dose regimen) or 80/480mg Forte",
        "brands": ["Coartem", "Lonart Forte", "Artefan", "Riamet"],
        "critical_priority": True,
        "storage": "Store below 30°C in dry conditions"
    },
    "Amoxicillin": {
        "therapeutic_class": "Broad-spectrum Beta-lactam Antibiotic",
        "standard_dosage": "500mg TDS or 1g BD",
        "brands": ["Amoxil", "Clamoxyl", "Hiconcil"],
        "critical_priority": True,
        "storage": "Room temperature"
    },
    "Human Insulin 30/70": {
        "therapeutic_class": "Biphasic Isophane Insulin (Diabetes Care)",
        "standard_dosage": "100 IU/ml",
        "brands": ["Insulin Mixtard 30", "Humulin 30/70", "Insuget 70/30"],
        "critical_priority": True,
        "storage": "Cold Chain Required: 2°C to 8°C"
    },
    "Paracetamol": {
        "therapeutic_class": "Analgesic & Antipyretic",
        "standard_dosage": "500mg - 1g 4-6 hourly",
        "brands": ["Efferalgan", "Doliprane", "Panadol", "Paracet"],
        "critical_priority": False,
        "storage": "Room temperature"
    }
}


class SemanticFormulary:
    """
    Tier 3: Semantic Knowledge Layer.
    Provides verified clinical guidelines, therapeutic classifications, and storage requirements.
    """
    @staticmethod
    def get_clinical_context(generic_molecule: str) -> Optional[Dict[str, Any]]:
        for mol, data in FORMULARY_KNOWLEDGE.items():
            if mol.lower() in generic_molecule.lower() or generic_molecule.lower() in mol.lower():
                return {"molecule": mol, **data}
        return None
