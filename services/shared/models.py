"""Shared Pydantic models and enums."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

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


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class CommunicationMode(str, Enum):
    """Communication mode for orders."""
    SYNC = "sync"
    ASYNC = "async"


# ============== Product Models ==============

class ProductBase(BaseModel):
    """Base product schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    image_url: Optional[str] = None
    category: Optional[str] = None


class ProductCreate(ProductBase):
    """Product creation schema."""
    pass


class ProductUpdate(BaseModel):
    """Product update schema."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    image_url: Optional[str] = None
    category: Optional[str] = None


class Product(ProductBase):
    """Product response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductWithStock(Product):
    """Product with stock information."""
    available_quantity: int = 0


# ============== Cart Models ==============

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


class CartItem(CartItemBase):
    """Cart item response schema."""
    id: UUID
    cart_id: UUID
    price: Decimal
    product_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CartBase(BaseModel):
    """Base cart schema."""
    user_id: str


class Cart(CartBase):
    """Cart response schema."""
    id: UUID
    items: List[CartItem] = []
    total: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Order Models ==============

class OrderItemBase(BaseModel):
    """Base order item schema."""
    product_id: UUID
    quantity: int = Field(..., ge=1)
    price: Decimal


class OrderItemCreate(OrderItemBase):
    """Order item creation schema."""
    pass


class OrderItem(OrderItemBase):
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


class Order(BaseModel):
    """Order response schema."""
    id: UUID
    user_id: str
    status: OrderStatus
    total_amount: Decimal
    communication_mode: CommunicationMode
    items: List[OrderItem] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    """Order status update schema."""
    status: OrderStatus
    error_message: Optional[str] = None


# ============== Payment Models ==============

class PaymentCreate(BaseModel):
    """Payment creation schema."""
    order_id: UUID
    amount: Decimal = Field(..., gt=0)


class Payment(BaseModel):
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


class PaymentProcess(BaseModel):
    """Payment processing request."""
    order_id: UUID
    amount: Decimal


class PaymentResult(BaseModel):
    """Payment processing result."""
    success: bool
    transaction_id: Optional[str] = None
    error: Optional[str] = None


# ============== Inventory Models ==============

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


class Stock(StockBase):
    """Stock response schema."""
    id: UUID
    reserved: int = 0
    available: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StockReserveRequest(BaseModel):
    """Stock reservation request."""
    order_id: UUID
    items: List[CartItemBase]


class StockReserveResult(BaseModel):
    """Stock reservation result."""
    success: bool
    reserved_items: List[UUID] = []
    error: Optional[str] = None


# ============== Health Check ==============

class HealthCheck(BaseModel):
    """Health check response."""
    status: str = "healthy"
    service: str
    version: str = "1.0.0"
    communication_mode: Optional[str] = None


# ============== Saga State ==============

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


class SagaState(BaseModel):
    """Saga state for order processing."""
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
