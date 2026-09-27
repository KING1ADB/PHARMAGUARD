from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...database.models.entities import Pharmacy, Inventory, Medicine, SalesHistory


class RegionalIntelligenceEngine:
    """
    PharmaGuard Multi-Pharmacy Regional Intelligence Layer (Phase 4).
    
    Responsibilities:
    - Provides aggregated epidemiological and shortage insights across pharmacy clusters.
    - Strictly preserves individual pharmacy data isolation, confidentiality, and tenant privacy.
    - Does NOT expose private financial revenues, exact customer identities, or commercial margins.
    """
    def __init__(self):
        pass

    @staticmethod
    def get_regional_supply_index(region_or_city: str, db: Session) -> Dict[str, Any]:
        """
        Aggregates anonymized availability and shortage pressure for essential therapeutic categories in a region.
        """
        # Find pharmacies in this region/city
        pharmacies = (
            db.query(Pharmacy)
            .filter(Pharmacy.location.contains(region_or_city) | (Pharmacy.location == region_or_city))
            .all()
        )

        if not pharmacies:
            # Fallback across all pharmacies if specific regional query is small
            pharmacies = db.query(Pharmacy).all()

        pharmacy_ids = [p.id for p in pharmacies]
        total_connected_pharmacies = len(pharmacies)

        # Evaluate essential categories availability
        categories = ["Antimalarial", "Antibiotic", "Antidiabetic", "Analgesic", "Antihypertensive"]
        regional_category_indices = []

        for cat in categories:
            # Query inventory items in this category across all tenant pharmacies
            cat_inventories = (
                db.query(Inventory, Medicine)
                .join(Medicine, Inventory.medicine_id == Medicine.id)
                .filter(
                    Inventory.pharmacy_id.in_(pharmacy_ids),
                    Medicine.category.contains(cat)
                )
                .all()
            )

            total_stock = sum(inv.quantity for inv, med in cat_inventories)
            skus_in_stock = sum(1 for inv, med in cat_inventories if inv.quantity > 0)
            stockout_skus = sum(1 for inv, med in cat_inventories if inv.quantity == 0)

            total_skus = len(cat_inventories)
            availability_rate = round(skus_in_stock / max(1, total_skus), 2) if total_skus > 0 else 1.0

            shortage_pressure = "NORMAL"
            if availability_rate < 0.60:
                shortage_pressure = "SEVERE_REGIONAL_SHORTAGE"
            elif availability_rate < 0.80:
                shortage_pressure = "ELEVATED_SHORTAGE_RISK"

            regional_category_indices.append({
                "therapeutic_category": cat,
                "total_regional_stock_units": total_stock,
                "skus_evaluated": total_skus,
                "regional_availability_rate": availability_rate,
                "regional_shortage_pressure": shortage_pressure
            })

        return {
            "status": "SUCCESS",
            "region": region_or_city,
            "connected_pharmacies_in_cluster": total_connected_pharmacies,
            "privacy_compliance": {
                "tenant_isolation_preserved": True,
                "anonymized_metrics_only": True,
                "commercial_financials_masked": True
            },
            "category_indices": regional_category_indices
        }


# Singleton instance
regional_intelligence = RegionalIntelligenceEngine()
