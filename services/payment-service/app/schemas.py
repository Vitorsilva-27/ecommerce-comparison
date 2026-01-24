"""Pydantic schemas for payment service."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentCreate(BaseModel):
    """Payment creation schema."""
    order_id: UUID
    amount: Decimal = Field(..., gt=0)


class PaymentProcess(BaseModel):
    """Payment processing request."""
    order_id: UUID
    amount: Decimal = Field(..., gt=0)


class PaymentResponse(BaseModel):
    """Payment response schema."""
    id: UUID
    order_id: UUID
    amount: Decimal
    status: PaymentStatus
    transaction_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaymentResult(BaseModel):
    """Payment processing result."""
    success: bool
    transaction_id: Optional[str] = None
    error: Optional[str] = None
