from datetime import datetime, timezone
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
from sqlalchemy.orm import relationship, synonym
from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Pharmacy(Base):
    """Pharmacy entity model."""
    __tablename__ = "pharmacies"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    location = Column(String(255), default="Douala, Cameroon")
    contact = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    inventory_items = relationship("Inventory", back_populates="pharmacy", cascade="all, delete-orphan")
    sales_history = relationship("SalesHistory", back_populates="pharmacy", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="pharmacy", cascade="all, delete-orphan")


class Medicine(Base):
    """Medicine catalog entity model."""
    __tablename__ = "medicines"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    generic_name = Column(String(150), nullable=False, index=True)
    category = Column(String(100), index=True)
    strength = Column(String(50), nullable=True)
    form = Column(String(50), nullable=True)

    inventory_items = relationship("Inventory", back_populates="medicine", cascade="all, delete-orphan")
    sales_history = relationship("SalesHistory", back_populates="medicine", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="medicine")


class Supplier(Base):
    """Wholesale pharmaceutical supplier entity model."""
    __tablename__ = "suppliers"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    delivery_time = Column(Integer, default=2)
    reliability_score = Column(Float, default=0.90)
    contact = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    location = Column(String(255), default="Douala, Cameroon")
    minimum_order_value_fcfa = Column(Float, default=50000.0)
    payment_terms = Column(String(100), default="30 Days Net")

    # Alias lead_time_days to delivery_time for compatibility
    @property
    def lead_time_days(self):
        return self.delivery_time

    @lead_time_days.setter
    def lead_time_days(self, value):
        self.delivery_time = value

    inventory_items = relationship("Inventory", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class Inventory(Base):
    """Pharmacy stock & batch inventory entity model."""
    __tablename__ = "inventory"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=False, index=True)
    quantity = Column(Integer, default=0)
    expiry_date = Column(Date, nullable=False, index=True)
    last_updated = Column(DateTime, default=utc_now, onupdate=utc_now)
    
    unit_cost_fcfa = Column(Float, default=0.0)
    selling_price_fcfa = Column(Float, default=0.0)
    reorder_point = Column(Integer, default=15)
    batch_number = Column(String(50), default="BATCH-DEFAULT")
    supplier_id = Column(String(50), ForeignKey("suppliers.id"), nullable=True)
    location_shelf = Column(String(50), default="General Shelf")

    @property
    def quantity_in_stock(self):
        return self.quantity

    pharmacy = relationship("Pharmacy", back_populates="inventory_items")
    medicine = relationship("Medicine", back_populates="inventory_items")
    supplier = relationship("Supplier", back_populates="inventory_items")


class SalesHistory(Base):
    """Historical sales transactions model."""
    __tablename__ = "sales_history"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=False, index=True)
    quantity_sold = Column(Integer, default=1)
    date = Column(Date, nullable=False, index=True)
    unit_price_fcfa = Column(Float, default=0.0)
    total_amount_fcfa = Column(Float, default=0.0)
    customer_type = Column(String(50), default="Walk-in Patient")

    pharmacy = relationship("Pharmacy", back_populates="sales_history")
    medicine = relationship("Medicine", back_populates="sales_history")


class AgentAction(Base):
    """Auditable agent actions and reasoning logs."""
    __tablename__ = "agent_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False)
    action_type = Column(String(100), nullable=False)
    reasoning = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.90)
    timestamp = Column(DateTime, default=utc_now)
    pharmacy_id = Column(String(50), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)


class PurchaseOrder(Base):
    """Purchase Order model requiring pharmacist authorization."""
    __tablename__ = "purchase_orders"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False)
    supplier_id = Column(String(50), ForeignKey("suppliers.id"), nullable=False)
    status = Column(String(30), default="DRAFT")
    total_amount_fcfa = Column(Float, default=0.0)
    items_json = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.90)
    created_at = Column(DateTime, default=utc_now)
    approved_at = Column(DateTime, nullable=True)

    supplier = relationship("Supplier", back_populates="purchase_orders")


class Alert(Base):
    """Operational risk alerts model."""
    __tablename__ = "alerts"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="MEDIUM")
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.90)
    status = Column(String(30), default="ACTIVE")
    created_at = Column(DateTime, default=utc_now)

    pharmacy = relationship("Pharmacy", back_populates="alerts")
    medicine = relationship("Medicine", back_populates="alerts")
