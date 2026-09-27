from datetime import date, datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, ConfigDict, Field


# ----------------------
# Authentication Schemas
# ----------------------
class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    role: str
    pharmacy_id: str


class UserCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: str
    role: str = "PHARMACIST"
    pharmacy_id: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    pharmacy_id: str
    name: str
    email: str
    phone: Optional[str] = None
    role: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Pharmacy Schemas
# ----------------------
class PharmacyBase(BaseModel):
    organization_name: str
    address: Optional[str] = None
    location: str = "Douala, Cameroon"
    contact_information: Optional[str] = None
    verification_status: str = "VERIFIED"


class PharmacyCreate(PharmacyBase):
    id: str


class PharmacyResponse(PharmacyBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Medicine Catalog Schemas
# ----------------------
class MedicineBase(BaseModel):
    generic_name: str
    brand_names: str
    category: str
    strength: Optional[str] = None
    dosage_form: Optional[str] = "Tablet"


class MedicineCreate(MedicineBase):
    id: str


class MedicineResponse(MedicineBase):
    id: str
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Inventory & Risk Schemas
# ----------------------
class MedicineRiskDetail(BaseModel):
    medicine_id: str
    name: str
    generic_name: str
    category: str
    current_quantity: int
    average_daily_sales: float
    stock_coverage_days: float
    supplier_delivery_days: int
    supplier_name: Optional[str] = "Default Wholesale"
    risk_level: str  # HIGH, MEDIUM, SAFE, CRITICAL_STOCKOUT
    confidence_score: float
    reasoning: str
    recommendation: str
    unit_cost_fcfa: float
    selling_price_fcfa: float
    expiry_date: str
    days_until_expiry: int
    expiry_status: str  # EXPIRED, CRITICAL, WARNING, NOTICE, OK
    model_config = ConfigDict(from_attributes=True)


class InventoryCreate(BaseModel):
    medicine_id: str
    quantity: int
    expiry_date: date
    unit_cost_fcfa: float
    selling_price_fcfa: float
    supplier_id: Optional[str] = None
    reorder_threshold: int = 15
    batch_number: Optional[str] = "BATCH-DEFAULT"
    location_shelf: Optional[str] = "General Shelf"


class InventoryUpdate(BaseModel):
    quantity: Optional[int] = None
    unit_cost_fcfa: Optional[float] = None
    selling_price_fcfa: Optional[float] = None
    reorder_threshold: Optional[int] = None
    expiry_date: Optional[date] = None
    location_shelf: Optional[str] = None


# ----------------------
# Supplier Schemas
# ----------------------
class SupplierBase(BaseModel):
    name: str
    contact: Optional[str] = None
    delivery_time: int = 2
    reliability_score: float = 0.90
    minimum_order_value_fcfa: float = 50000.0
    payment_terms: str = "30 Days Net"
    phone: Optional[str] = None
    email: Optional[str] = None
    location: str = "Douala, Cameroon"


class SupplierCreate(SupplierBase):
    id: str


class SupplierResponse(SupplierBase):
    id: str
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
    status: str  # DRAFT, APPROVED, REJECTED, ORDERED
    total_amount_fcfa: float
    items: List[OrderItem]
    reasoning: Optional[str] = None
    confidence_score: float = 0.90
    approved_by: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderApprovalRequest(BaseModel):
    action: str = "APPROVE"  # APPROVE or REJECT
    notes: Optional[str] = None


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
# Morning Intelligence Report Schemas
# ----------------------
class MorningAlertDetail(BaseModel):
    medicine_id: str
    title: str
    severity: str
    reasoning: str
    confidence: str
    recommendation: str


class MorningIntelligenceReportResponse(BaseModel):
    pharmacy_name: str
    date: str
    execution_time_utc: str
    total_active_skus: int
    total_stock_value_fcfa: float
    critical_shortages_count: int
    expiring_soon_count: int
    capital_at_expiry_risk_fcfa: float
    critical_alerts: List[MorningAlertDetail]
    draft_purchase_orders_count: int
    recommendations: List[str]
    report_markdown: str


class MorningCycleTriggerResponse(BaseModel):
    status: str
    cycle_id: str
    pharmacy_id: str
    timestamp: datetime
    total_skus_evaluated: int
    high_shortage_risks: int
    critical_expiries: int
    draft_orders_created: int
    report: MorningIntelligenceReportResponse


# ----------------------
# Memory & Audit Schemas
# ----------------------
class AgentMemoryResponse(BaseModel):
    id: str
    pharmacy_id: str
    memory_type: str
    learned_context: Dict[str, Any]
    confidence_score: float
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class AgentActionLogResponse(BaseModel):
    id: Union[int, str]
    pharmacy_id: Optional[str] = None
    agent: str
    action: str
    reasoning: Optional[str] = None
    confidence_score: float
    approval_status: str
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# Forecasting Schemas (Phase 2)
# ----------------------
class DemandForecastDetail(BaseModel):
    medicine_id: str
    name: str
    generic_name: str
    category: Optional[str] = None
    pharmacy_location: str
    current_stock: int
    base_daily_sales: float
    trend_direction: str  # SURGING, STABLE, DECLINING
    trend_slope: float
    seasonal_multiplier: float
    seasonal_description: str
    projected_daily_demand: float
    forecast_7d_units: float
    forecast_14d_units: float
    forecast_30d_units: float
    days_until_stockout: float
    estimated_stockout_date: str
    supplier_lead_time_days: int
    supplier_name: str
    stockout_status: str  # IMMEDIATE_STOCKOUT, CRITICAL_BEFORE_DELIVERY, VULNERABLE_NEAR_TERM, SAFE_HORIZON
    stockout_before_replenishment: bool
    confidence_score: float
    reasoning: str
    model_config = ConfigDict(from_attributes=True)


class ForecastingSummaryResponse(BaseModel):
    status: str
    agent: str
    pharmacy_id: str
    pharmacy_name: str
    timestamp: datetime
    evaluated_skus_count: int
    imminent_stockouts_count: int
    seasonal_surges_count: int
    total_30d_projected_demand_units: float
    forecasts: List[DemandForecastDetail]
    imminent_stockout_risks: List[DemandForecastDetail]
    seasonal_surges: List[DemandForecastDetail]
    narrative_summary: str
    model_config = ConfigDict(from_attributes=True)


# ----------------------
# AI Action Center Schemas (Phase 3)
# ----------------------
class ActionDecisionRequest(BaseModel):
    action: str = "APPROVE"  # APPROVE, MODIFY, REJECT
    modified_items: Optional[List[OrderItem]] = None
    modified_supplier_id: Optional[str] = None
    notes: Optional[str] = None
    auto_dispatch: bool = True
    dispatch_channel: str = "EMAIL"  # EMAIL, WHATSAPP, EDI_API


class ActionExecutionResponse(BaseModel):
    id: str
    pharmacy_id: str
    supplier_id: str
    status: str
    total_amount_fcfa: float
    items: List[OrderItem]
    dispatch_channel: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    supplier_response_status: Optional[str] = None
    tracking_reference: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)



