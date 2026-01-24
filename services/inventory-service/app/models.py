"""SQLAlchemy models for inventory service."""

import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID

from .database import Base


class Stock(Base):
    """Stock model."""

    __tablename__ = "stock"
    __table_args__ = {"schema": "inventory"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), nullable=False, index=True, unique=True)
    quantity = Column(Integer, nullable=False, default=0)
    reserved = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def available(self) -> int:
        """Calculate available stock."""
        return self.quantity - self.reserved

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "product_id": str(self.product_id),
            "quantity": self.quantity,
            "reserved": self.reserved,
            "available": self.available,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
