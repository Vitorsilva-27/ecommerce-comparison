"""Pydantic schemas for order service."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_FAILED = "payment_failed"
    STOCK_PENDING = "stock_pending"
    STOCK_FAILED = "stock_failed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CommunicationMode(str, Enum):
    """Communication mode for orders."""
    SYNC = "sync"
    ASYNC = "async"


class OrderItemBase(BaseModel):
    """Base order item schema."""
    product_id: UUID
    quantity: int = Field(..., ge=1)
    price: Decimal


class OrderItemResponse(OrderItemBase):
    """Order item response schema."""
    id: UUID
    order_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    """Order creation schema."""
    user_id: str
    cart_id: UUID
    communication_mode: CommunicationMode = CommunicationMode.SYNC


class OrderResponse(BaseModel):
    """Order response schema."""
    id: UUID
    user_id: str
    status: OrderStatus
    total_amount: Decimal
    communication_mode: CommunicationMode
    items: List[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    """Order status update schema."""
    status: OrderStatus
    error_message: Optional[str] = None


class SagaStep(str, Enum):
    """Saga steps for async order processing."""
    CREATED = "created"
    PAYMENT_REQUESTED = "payment_requested"
    PAYMENT_COMPLETED = "payment_completed"
    STOCK_REQUESTED = "stock_requested"
    STOCK_COMPLETED = "stock_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"


class SagaStateResponse(BaseModel):
    """Saga state response schema."""
    id: UUID
    order_id: UUID
    current_step: SagaStep
    status: str
    payment_status: Optional[str] = None
    inventory_status: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
