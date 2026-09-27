from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# ----------------------
# Pharmacy Schemas
# ----------------------
class PharmacyBase(BaseModel):
    name: str
    city: str = "Douala"
    country: str = "Cameroon"
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_connected_to_network: bool = True


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
    dosage_form: str
    strength: str
    batch_number: str
    quantity_in_stock: int
    unit_cost_fcfa: float
    selling_price_fcfa: float
    reorder_point: int
    expiry_date: date
    supplier_id: Optional[str] = None
    location_shelf: Optional[str] = "General Shelf"


class MedicineCreate(MedicineBase):
    id: str
    pharmacy_id: Optional[str] = None


class MedicineUpdate(BaseModel):
    quantity_in_stock: Optional[int] = None
    unit_cost_fcfa: Optional[float] = None
    selling_price_fcfa: Optional[float] = None
    reorder_point: Optional[int] = None
    expiry_date: Optional[date] = None
    location_shelf: Optional[str] = None


class MedicineResponse(MedicineBase):
    id: str
    pharmacy_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MedicineRiskDetail(BaseModel):
    medicine_id: str
    name: str
    generic_name: str
    category: str
    quantity_in_stock: int
    reorder_point: int
    unit_cost_fcfa: float
    selling_price_fcfa: float
    expiry_date: str
    days_until_expiry: int
    expiry_status: str  # EXPIRED, CRITICAL (<30d), WARNING (<60d), NOTICE (<90d), OK
    daily_sales_velocity: float
    days_of_stock_remaining: float
    stockout_risk_level: str  # CRITICAL, HIGH, MEDIUM, LOW, SAFE
    supplier_id: Optional[str] = None
    location_shelf: Optional[str] = "General Shelf"
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Supplier Schemas
# ----------------------
class SupplierBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: str = "Douala"
    address: Optional[str] = None
    lead_time_days: int = 2
    minimum_order_value_fcfa: float = 50000.0
    reliability_score: float = 0.90
    payment_terms: str = "30 Days Net"


class SupplierCreate(SupplierBase):
    id: str


class SupplierResponse(SupplierBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Sale Schemas
# ----------------------
class SaleRecordBase(BaseModel):
    medicine_id: str
    date: date
    quantity_sold: int
    unit_price_fcfa: float
    total_amount_fcfa: float
    customer_type: str = "Walk-in Patient"


class SaleRecordCreate(SaleRecordBase):
    id: Optional[str] = None
    pharmacy_id: Optional[str] = None


class SaleRecordResponse(SaleRecordBase):
    id: str
    pharmacy_id: str
    created_at: datetime
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
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Agent Interaction Schemas
# ----------------------
class AgentQueryRequest(BaseModel):
    pharmacy_id: Optional[str] = None
    query: str
    channel: str = "web"  # web, whatsapp, api


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
