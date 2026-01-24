"""Pydantic schemas for cart service."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CartItemBase(BaseModel):
    """Base cart item schema."""
    product_id: UUID
    quantity: int = Field(..., ge=1)


class CartItemCreate(CartItemBase):
    """Cart item creation schema."""
    pass


class CartItemUpdate(BaseModel):
    """Cart item update schema."""
    quantity: int = Field(..., ge=1)


class CartItemResponse(CartItemBase):
    """Cart item response schema."""
    id: UUID
    cart_id: UUID
    price: Decimal
    product_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CartCreate(BaseModel):
    """Cart creation schema."""
    user_id: str


class CartResponse(BaseModel):
    """Cart response schema."""
    id: UUID
    user_id: str
    items: List[CartItemResponse] = []
    total: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AddToCartRequest(BaseModel):
    """Add to cart request."""
    product_id: UUID
    quantity: int = Field(1, ge=1)
