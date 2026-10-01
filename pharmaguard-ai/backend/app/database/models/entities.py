import json
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Date,
    DateTime,
    Boolean,
    Text,
    ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now():
    return datetime.now(timezone.utc)


class Pharmacy(Base):
    """Pharmacy organization entity."""
    __tablename__ = "pharmacies"

    id = Column(String(50), primary_key=True, index=True)
    organization_name = Column(String(150), nullable=False)
    address = Column(String(255), nullable=True)
    location = Column(String(255), default="Douala, Cameroon")
    contact_information = Column(String(150), nullable=True)
    verification_status = Column(String(50), default="VERIFIED")
    
    # Pilot & Onboarding Tracking
    onboarding_status = Column(String(50), default="REGISTERED")  # REGISTERED, DATA_CONNECTED, AGENT_ACTIVATED, PILOT_ACTIVE
    pilot_tier = Column(String(50), default="STANDARD_PILOT")     # STANDARD_PILOT, ENTERPRISE_PILOT
    agent_active = Column(Boolean, default=True)
    preferred_morning_run_time = Column(String(10), default="07:30")
    created_at = Column(DateTime, default=utc_now)

    users = relationship("User", back_populates="pharmacy", cascade="all, delete-orphan")
    inventory_items = relationship("Inventory", back_populates="pharmacy", cascade="all, delete-orphan")
    sales_history = relationship("SalesHistory", back_populates="pharmacy", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="pharmacy", cascade="all, delete-orphan")
    memories = relationship("AgentMemory", back_populates="pharmacy", cascade="all, delete-orphan")
    action_logs = relationship("AgentActionLog", back_populates="pharmacy", cascade="all, delete-orphan")
    purchase_orders = relationship("PurchaseOrder", back_populates="pharmacy", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "city" in kwargs and "region" in kwargs:
            kwargs["location"] = f"{kwargs.pop('city')}, {kwargs.pop('region')}"
        if "contact_email" in kwargs:
            kwargs["contact_information"] = kwargs.pop("contact_email")
        if "license_number" in kwargs:
            kwargs.pop("license_number")
        super().__init__(**kwargs)


class User(Base):
    """User account entity with Role-Based Access Control."""
    __tablename__ = "users"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="PHARMACIST")  # OWNER, PHARMACIST, ASSISTANT, AUDITOR
    permissions = Column(Text, default='["READ", "WRITE", "APPROVE_ORDERS"]')
    created_at = Column(DateTime, default=utc_now)

    pharmacy = relationship("Pharmacy", back_populates="users")

    def __init__(self, **kwargs):
        if "full_name" in kwargs:
            kwargs["name"] = kwargs.pop("full_name")
        if "hashed_password" in kwargs:
            kwargs["password_hash"] = kwargs.pop("hashed_password")
        if "is_active" in kwargs:
            kwargs.pop("is_active")
        super().__init__(**kwargs)


class Medicine(Base):
    """Medicine master catalog entity."""
    __tablename__ = "medicines"

    id = Column(String(50), primary_key=True, index=True)
    generic_name = Column(String(150), nullable=False, index=True)
    brand_names = Column(String(255), nullable=False, index=True)  # Primary brand name or aliases
    category = Column(String(100), index=True)
    strength = Column(String(50), nullable=True)
    dosage_form = Column(String(50), nullable=True)  # Tablet, Capsule, Injectable, Syrup, Inhaler
    barcode = Column(String(100), unique=True, index=True, nullable=True)  # EAN-13, UPC, DataMatrix
    
    # Medicine Intelligence & Regulatory Metadata
    storage_temperature = Column(String(50), default="15-25°C")
    storage_conditions = Column(String(200), default="Store in cool, dry place away from direct light")
    regulatory_schedule = Column(String(50), default="Prescription Required (Rx)")  # Rx, OTC, Controlled, List I, List II
    atc_code = Column(String(20), nullable=True)
    is_essential = Column(Boolean, default=True)

    @property
    def name(self):
        return self.brand_names

    @property
    def form(self):
        return self.dosage_form

    inventory_items = relationship("Inventory", back_populates="medicine", cascade="all, delete-orphan")
    sales_history = relationship("SalesHistory", back_populates="medicine", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="medicine")

    def __init__(self, **kwargs):
        if "brand_name" in kwargs:
            kwargs["brand_names"] = kwargs.pop("brand_name")
        if "therapeutic_class" in kwargs:
            kwargs["category"] = kwargs.pop("therapeutic_class")
        kwargs.pop("unit_cost_fcfa", None)
        kwargs.pop("unit_sale_price_fcfa", None)
        super().__init__(**kwargs)


class AgentEvaluationMetric(Base):
    """Evaluation framework store for AI agent accuracy and reliability scoring."""
    __tablename__ = "agent_evaluation_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    metric_type = Column(String(80), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    target_benchmark = Column(Float, default=0.85)
    sample_size = Column(Integer, default=1)
    evaluation_details = Column(Text, nullable=True)  # JSON string
    timestamp = Column(DateTime, default=utc_now)

    pharmacy = relationship("Pharmacy")


class Supplier(Base):
    """Wholesale pharmaceutical supplier entity."""
    __tablename__ = "suppliers"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    contact = Column(String(150), nullable=True)
    delivery_time = Column(Integer, default=2)  # Lead time in days
    reliability_score = Column(Float, default=0.90)
    minimum_order_value_fcfa = Column(Float, default=50000.0)
    payment_terms = Column(String(100), default="30 Days Net")
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    location = Column(String(255), default="Douala, Cameroon")

    @property
    def lead_time_days(self):
        return self.delivery_time

    inventory_items = relationship("Inventory", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")

    def __init__(self, **kwargs):
        if "lead_time_days" in kwargs:
            kwargs["delivery_time"] = kwargs.pop("lead_time_days")
        if "contact_email" in kwargs:
            kwargs["email"] = kwargs.pop("contact_email")
        if "contact_person" in kwargs:
            kwargs["contact"] = kwargs.pop("contact_person")
        super().__init__(**kwargs)


def default_expiry():
    return date.today() + timedelta(days=365)


class Inventory(Base):
    """Pharmacy stock and batch inventory entity."""
    __tablename__ = "inventory"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=False, index=True)
    supplier_id = Column(String(50), ForeignKey("suppliers.id"), nullable=True)
    quantity = Column(Integer, default=0)
    reorder_threshold = Column(Integer, default=15)
    expiry_date = Column(Date, default=default_expiry, nullable=False, index=True)
    unit_cost_fcfa = Column(Float, default=0.0)
    selling_price_fcfa = Column(Float, default=0.0)
    batch_number = Column(String(50), default="BATCH-DEFAULT")
    location_shelf = Column(String(50), default="General Shelf")
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    @property
    def quantity_in_stock(self):
        return self.quantity

    @property
    def reorder_point(self):
        return self.reorder_threshold

    @property
    def reorder_level(self):
        return self.reorder_threshold

    pharmacy = relationship("Pharmacy", back_populates="inventory_items")
    medicine = relationship("Medicine", back_populates="inventory_items")
    supplier = relationship("Supplier", back_populates="inventory_items")

    def __init__(self, **kwargs):
        if "quantity_in_stock" in kwargs:
            kwargs["quantity"] = kwargs.pop("quantity_in_stock")
        if "reorder_point" in kwargs:
            kwargs["reorder_threshold"] = kwargs.pop("reorder_point")
        if "reorder_level" in kwargs:
            kwargs["reorder_threshold"] = kwargs.pop("reorder_level")
        if "unit_sale_price_fcfa" in kwargs:
            kwargs["selling_price_fcfa"] = kwargs.pop("unit_sale_price_fcfa")
        if "expiry_date" not in kwargs and "days_until_expiry" in kwargs:
            kwargs["expiry_date"] = date.today() + timedelta(days=kwargs.pop("days_until_expiry"))
        else:
            kwargs.pop("days_until_expiry", None)
        super().__init__(**kwargs)


class SalesHistory(Base):
    """Historical sales transactions entity."""
    __tablename__ = "sales_history"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=False, index=True)
    quantity = Column(Integer, default=1)
    unit_price_fcfa = Column(Float, default=0.0)
    total_amount_fcfa = Column(Float, default=0.0)
    customer_type = Column(String(50), default="Walk-in Patient")
    timestamp = Column(DateTime, default=utc_now, index=True)

    @property
    def quantity_sold(self):
        return self.quantity

    @property
    def date(self):
        return self.timestamp.date() if isinstance(self.timestamp, datetime) else self.timestamp

    pharmacy = relationship("Pharmacy", back_populates="sales_history")
    medicine = relationship("Medicine", back_populates="sales_history")

    def __init__(self, **kwargs):
        if "quantity_sold" in kwargs:
            kwargs["quantity"] = kwargs.pop("quantity_sold")
        if "unit_sale_price_fcfa" in kwargs:
            kwargs["unit_price_fcfa"] = kwargs.pop("unit_sale_price_fcfa")
        if "sale_date" in kwargs:
            s_date = kwargs.pop("sale_date")
            if isinstance(s_date, date) and not isinstance(s_date, datetime):
                kwargs["timestamp"] = datetime.combine(s_date, datetime.min.time(), tzinfo=timezone.utc)
            else:
                kwargs["timestamp"] = s_date
        super().__init__(**kwargs)


class AgentMemory(Base):
    """Episodic memory store for pharmacy-specific learned behaviors."""
    __tablename__ = "agent_memory"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    memory_type = Column(String(50), nullable=False)  # PREFERENCE, SUPPLIER_RELIABILITY, ORDER_RHYTHM, DEMAND_TREND
    information = Column(Text, nullable=False)        # JSON string of learned information
    confidence = Column(Float, default=0.90)
    timestamp = Column(DateTime, default=utc_now)

    @property
    def learned_context(self):
        try:
            return json.loads(self.information)
        except Exception:
            return {"raw": self.information}

    @property
    def confidence_score(self):
        return self.confidence

    pharmacy = relationship("Pharmacy", back_populates="memories")

    def __init__(self, **kwargs):
        if "learned_context" in kwargs:
            val = kwargs.pop("learned_context")
            kwargs["information"] = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
        if "confidence_score" in kwargs:
            kwargs["confidence"] = kwargs.pop("confidence_score")
        super().__init__(**kwargs)


class AgentActionLog(Base):
    """Immutable audit trail for all agent decisions and reasoning."""
    __tablename__ = "agent_action_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=True, index=True)
    agent = Column(String(100), nullable=False, default="PharmaGuardAutonomousAgent")
    action = Column(String(100), nullable=False)
    reasoning = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.90)
    approval_status = Column(String(50), default="AUTONOMOUS")  # AUTONOMOUS, PENDING_APPROVAL, APPROVED, REJECTED
    timestamp = Column(DateTime, default=utc_now)
    metadata_json = Column(Text, nullable=True)

    @property
    def action_type(self):
        return self.action

    @property
    def details(self):
        return self.reasoning

    pharmacy = relationship("Pharmacy", back_populates="action_logs")

    def __init__(self, **kwargs):
        if "action_type" in kwargs:
            kwargs["action"] = kwargs.pop("action_type")
        if "details" in kwargs:
            kwargs["reasoning"] = kwargs.pop("details")
        if "agent" not in kwargs:
            kwargs["agent"] = "PharmaGuardAutonomousAgent"
        if "reasoning" not in kwargs:
            kwargs["reasoning"] = "Autonomous operational log"
        if "id" in kwargs and isinstance(kwargs["id"], str):
            kwargs.pop("id")
        super().__init__(**kwargs)


class PurchaseOrder(Base):
    """Purchase Order entity requiring human pharmacist authorization and real-world execution."""
    __tablename__ = "purchase_orders"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    supplier_id = Column(String(50), ForeignKey("suppliers.id"), nullable=False)
    status = Column(String(30), default="DRAFT")  # DRAFT, APPROVED, REJECTED, DISPATCHED, CONFIRMED, DELIVERED
    total_amount_fcfa = Column(Float, default=0.0)
    items_json = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.90)
    approved_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    approved_at = Column(DateTime, nullable=True)
    
    # Action & Dispatch tracking
    dispatch_channel = Column(String(30), nullable=True)  # EMAIL, WHATSAPP, EDI_API
    dispatched_at = Column(DateTime, nullable=True)
    supplier_response_status = Column(String(50), default="PENDING")  # PENDING, CONFIRMED, OUT_OF_STOCK, PARTIAL_DELIVERY, DELIVERED
    tracking_reference = Column(String(100), nullable=True)
    actual_delivery_date = Column(Date, nullable=True)

    @property
    def items(self):
        try:
            return json.loads(self.items_json)
        except Exception:
            return []

    @property
    def notes(self):
        return self.reasoning

    pharmacy = relationship("Pharmacy", back_populates="purchase_orders")
    supplier = relationship("Supplier", back_populates="purchase_orders")

    def __init__(self, **kwargs):
        if "notes" in kwargs:
            kwargs["reasoning"] = kwargs.pop("notes")
        super().__init__(**kwargs)


class Alert(Base):
    """Operational risk alerts entity."""
    __tablename__ = "alerts"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=True)
    alert_type = Column(String(50), nullable=False)  # SHORTAGE_RISK, EXPIRY_WARNING, DEMAND_SURGE
    severity = Column(String(20), default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.90)
    status = Column(String(30), default="ACTIVE")  # ACTIVE, RESOLVED, DISMISSED
    created_at = Column(DateTime, default=utc_now)

    @property
    def recommended_action(self):
        return self.suggested_action

    pharmacy = relationship("Pharmacy", back_populates="alerts")
    medicine = relationship("Medicine", back_populates="alerts")

    def __init__(self, **kwargs):
        if "recommended_action" in kwargs:
            kwargs["suggested_action"] = kwargs.pop("recommended_action")
        if "title" not in kwargs:
            a_type = kwargs.get("alert_type", "OPERATIONAL_ALERT")
            kwargs["title"] = str(a_type).replace("_", " ").title()
        super().__init__(**kwargs)
