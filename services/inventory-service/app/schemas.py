"""Pydantic schemas for inventory service."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class StockBase(BaseModel):
    """Base stock schema."""
    product_id: UUID
    quantity: int = Field(..., ge=0)


class StockCreate(StockBase):
    """Stock creation schema."""
    pass


class StockUpdate(BaseModel):
    """Stock update schema."""
    quantity: int = Field(..., ge=0)


class StockResponse(StockBase):
    """Stock response schema."""
    id: UUID
    reserved: int
    available: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReserveItem(BaseModel):
    """Item to reserve."""
    product_id: UUID
    quantity: int = Field(..., ge=1)


class StockReserveRequest(BaseModel):
    """Stock reservation request."""
    order_id: UUID
    items: List[ReserveItem]


class StockReserveResponse(BaseModel):
    """Stock reservation response."""
    success: bool
    reserved_items: List[UUID] = []
    error: Optional[str] = None


class StockReleaseRequest(BaseModel):
    """Stock release request."""
    order_id: UUID
    items: List[ReserveItem]
