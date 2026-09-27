from datetime import date, datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ----------------------
# Pharmacy Schemas
# ----------------------
class PharmacyBase(BaseModel):
    name: str
    location: str = "Douala, Cameroon"
    contact: Optional[str] = None


class PharmacyCreate(PharmacyBase):
    id: str


class PharmacyResponse(PharmacyBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Medicine / Inventory Schemas
# ----------------------
class MedicineBase(BaseModel):
    name: str
    generic_name: str
    category: str
    strength: Optional[str] = None
    form: Optional[str] = "Tablet"


class MedicineCreate(MedicineBase):
    id: str


class MedicineResponse(MedicineBase):
    id: str
    model_config = ConfigDict(from_attributes=True)


class MedicineRiskDetail(BaseModel):
    medicine_id: str
    name: str
    generic_name: str
    current_quantity: int
    average_daily_sales: float
    stock_coverage_days: float
    supplier_delivery_days: int
    supplier_name: Optional[str] = "Default Wholesale"
    risk_level: str  # HIGH, MEDIUM, SAFE, CRITICAL_STOCKOUT
    confidence_score: float
    reasoning: str
    recommendation: str
    model_config = ConfigDict(from_attributes=True)


class MedicineUpdate(BaseModel):
    quantity: Optional[int] = None
    unit_cost_fcfa: Optional[float] = None
    selling_price_fcfa: Optional[float] = None
    reorder_point: Optional[int] = None
    expiry_date: Optional[date] = None


# ----------------------
# Supplier Schemas
# ----------------------
class SupplierBase(BaseModel):
    name: str
    delivery_time: int = 2
    reliability_score: float = 0.90
    contact: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    location: str = "Douala, Cameroon"
    minimum_order_value_fcfa: float = 50000.0
    payment_terms: str = "30 Days Net"


class SupplierCreate(SupplierBase):
    id: str


class SupplierResponse(SupplierBase):
    id: str
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Sale Schemas
# ----------------------
class SaleRecordBase(BaseModel):
    medicine_id: str
    date: date
    quantity_sold: int
    unit_price_fcfa: float = 0.0
    total_amount_fcfa: float = 0.0
    customer_type: str = "Walk-in Patient"


class SaleRecordCreate(SaleRecordBase):
    id: Optional[str] = None
    pharmacy_id: Optional[str] = None


class SaleRecordResponse(SaleRecordBase):
    id: str
    pharmacy_id: str
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Purchase Order Schemas
# ----------------------
class OrderItem(BaseModel):
    medicine_id: str
    medicine_name: str
    quantity: int
    unit_cost_fcfa: float
    subtotal_fcfa: float


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    items: List[OrderItem]
    reasoning: Optional[str] = None


class PurchaseOrderResponse(BaseModel):
    id: str
    pharmacy_id: str
    supplier_id: str
    status: str
    total_amount_fcfa: float
    items: List[OrderItem]
    reasoning: Optional[str] = None
    confidence_score: float = 0.90
    created_at: datetime
    approved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Alert Schemas
# ----------------------
class AlertResponse(BaseModel):
    id: str
    pharmacy_id: str
    alert_type: str
    severity: str
    medicine_id: Optional[str] = None
    title: str
    message: str
    suggested_action: Optional[str] = None
    confidence_score: float = 0.90
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Agent Interaction Schemas
# ----------------------
class AgentQueryRequest(BaseModel):
    pharmacy_id: Optional[str] = None
    query: str
    channel: str = "web"


class AgentQueryResponse(BaseModel):
    response: str
    suggested_actions: List[str] = []
    data: Optional[Dict[str, Any]] = None


class AgentDecisionCycleResponse(BaseModel):
    cycle_id: str
    pharmacy_id: str
    timestamp: datetime
    phase_results: Dict[str, Any]
    active_alerts_count: int
    recommended_orders: List[Dict[str, Any]]
    briefing_text: str


class DailyBriefingResponse(BaseModel):
    pharmacy_name: str
    date: str
    critical_stockouts_count: int
    expiring_soon_count: int
    total_inventory_value_fcfa: float
    briefing_markdown: str
    draft_purchase_orders_count: int
