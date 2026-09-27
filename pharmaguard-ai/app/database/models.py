from datetime import datetime
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
from sqlalchemy.orm import relationship
from .database import Base


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    city = Column(String(100), default="Douala")
    country = Column(String(100), default="Cameroon")
    address = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    is_connected_to_network = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    medicines = relationship("Medicine", back_populates="pharmacy", cascade="all, delete-orphan")
    sales = relationship("SaleRecord", back_populates="pharmacy", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="pharmacy", cascade="all, delete-orphan")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    city = Column(String(100), default="Douala")
    address = Column(String(255), nullable=True)
    lead_time_days = Column(Integer, default=2)
    minimum_order_value_fcfa = Column(Float, default=50000.0)
    reliability_score = Column(Float, default=0.90)
    payment_terms = Column(String(100), default="30 Days Net")
    created_at = Column(DateTime, default=datetime.utcnow)

    medicines = relationship("Medicine", back_populates="supplier")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    generic_name = Column(String(150), nullable=False, index=True)
    category = Column(String(100), index=True)
    dosage_form = Column(String(50))
    strength = Column(String(50))
    batch_number = Column(String(50))
    quantity_in_stock = Column(Integer, default=0)
    unit_cost_fcfa = Column(Float, default=0.0)
    selling_price_fcfa = Column(Float, default=0.0)
    reorder_point = Column(Integer, default=15)
    expiry_date = Column(Date, nullable=False, index=True)
    supplier_id = Column(String(50), ForeignKey("suppliers.id"), nullable=True)
    location_shelf = Column(String(50), default="General Shelf")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pharmacy = relationship("Pharmacy", back_populates="medicines")
    supplier = relationship("Supplier", back_populates="medicines")
    sales = relationship("SaleRecord", back_populates="medicine")
    alerts = relationship("Alert", back_populates="medicine")


class SaleRecord(Base):
    __tablename__ = "sales_records"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    quantity_sold = Column(Integer, default=1)
    unit_price_fcfa = Column(Float, nullable=False)
    total_amount_fcfa = Column(Float, nullable=False)
    customer_type = Column(String(50), default="Walk-in Patient")
    created_at = Column(DateTime, default=datetime.utcnow)

    pharmacy = relationship("Pharmacy", back_populates="sales")
    medicine = relationship("Medicine", back_populates="sales")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False)
    supplier_id = Column(String(50), ForeignKey("suppliers.id"), nullable=False)
    status = Column(String(30), default="DRAFT")  # DRAFT, APPROVED, ORDERED, RECEIVED, CANCELLED
    total_amount_fcfa = Column(Float, default=0.0)
    items_json = Column(Text, nullable=False)  # JSON array of ordered items, qty, unit price
    reasoning = Column(Text, nullable=True)     # Agent reasoning for order
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)

    supplier = relationship("Supplier", back_populates="purchase_orders")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(50), primary_key=True, index=True)
    pharmacy_id = Column(String(50), ForeignKey("pharmacies.id"), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)  # STOCKOUT_RISK, EXPIRY_WARNING, DEMAND_SURGE, PROCUREMENT_SUGGESTION
    severity = Column(String(20), default="MEDIUM")  # CRITICAL, HIGH, MEDIUM, LOW
    medicine_id = Column(String(50), ForeignKey("medicines.id"), nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=True)
    status = Column(String(30), default="ACTIVE")  # ACTIVE, RESOLVED, DISMISSED
    created_at = Column(DateTime, default=datetime.utcnow)

    pharmacy = relationship("Pharmacy", back_populates="alerts")
    medicine = relationship("Medicine", back_populates="alerts")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pharmacy_id = Column(String(50), nullable=False, index=True)
    cycle_id = Column(String(50), index=True)
    phase = Column(String(50), nullable=False)  # OBSERVE, ANALYZE, PLAN, ACT, LEARN
    agent_name = Column(String(100), nullable=False)
    summary = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
