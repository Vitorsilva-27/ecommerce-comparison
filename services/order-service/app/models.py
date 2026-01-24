"""SQLAlchemy models for order service."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class Order(Base):
    """Order model."""

    __tablename__ = "orders"
    __table_args__ = {"schema": "orders"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="pending")
    total_amount = Column(Numeric(10, 2), nullable=False)
    communication_mode = Column(String(20), nullable=False, default="sync")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    saga_state = relationship("SagaState", back_populates="order", uselist=False)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "status": self.status,
            "total_amount": float(self.total_amount),
            "communication_mode": self.communication_mode,
            "items": [item.to_dict() for item in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OrderItem(Base):
    """Order item model."""

    __tablename__ = "order_items"
    __table_args__ = {"schema": "orders"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "order_id": str(self.order_id),
            "product_id": str(self.product_id),
            "quantity": self.quantity,
            "price": float(self.price),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SagaState(Base):
    """Saga state for async order processing."""

    __tablename__ = "saga_state"
    __table_args__ = {"schema": "orders"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.orders.id"), nullable=False)
    current_step = Column(String(50), nullable=False, default="created")
    status = Column(String(50), nullable=False, default="pending")
    payment_status = Column(String(50))
    inventory_status = Column(String(50))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("Order", back_populates="saga_state")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "order_id": str(self.order_id),
            "current_step": self.current_step,
            "status": self.status,
            "payment_status": self.payment_status,
            "inventory_status": self.inventory_status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
