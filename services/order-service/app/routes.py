"""API routes for order service."""

import os
import logging
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import httpx

from .database import get_db
from .models import Order, OrderItem, SagaState
from .schemas import (
    OrderCreate, OrderResponse, OrderItemResponse,
    OrderStatus, CommunicationMode, SagaStateResponse
)
from .sync_handler import process_order_sync_simple
from .async_handler import process_order_async_simple

import sys
sys.path.insert(0, "/app")

from shared.messaging import RabbitMQClient

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger(__name__)

CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://cart-service:8002")
COMMUNICATION_MODE = os.getenv("COMMUNICATION_MODE", "sync")

# RabbitMQ client (initialized in main.py)
rabbitmq_client: Optional[RabbitMQClient] = None


def set_rabbitmq_client(client: RabbitMQClient):
    """Set the RabbitMQ client."""
    global rabbitmq_client
    rabbitmq_client = client


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    order_request: OrderCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new order from cart."""
    from .database import async_session

    logger.info(f"Creating order for user {order_request.user_id}")

    # Get cart data
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{CART_SERVICE_URL}/carts/{order_request.cart_id}"
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Cart not found")
        response.raise_for_status()
        cart_data = response.json()

    if not cart_data.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Calculate total
    total_amount = Decimal(str(cart_data.get("total", 0)))

    # Determine communication mode
    mode = order_request.communication_mode
    if mode == CommunicationMode.SYNC:
        comm_mode = "sync"
    else:
        comm_mode = "async"

    # Create order and items in a fresh session
    async with async_session() as session:
        order = Order(
            user_id=order_request.user_id,
            status=OrderStatus.PENDING.value,
            total_amount=total_amount,
            communication_mode=comm_mode
        )
        session.add(order)
        await session.flush()
        order_id = order.id

        # Create order items
        for item in cart_data.get("items", []):
            order_item = OrderItem(
                order_id=order_id,
                product_id=UUID(item["product_id"]),
                quantity=item["quantity"],
                price=Decimal(str(item["price"]))
            )
            session.add(order_item)

        await session.commit()

    logger.info(f"Order {order_id} created, processing in {comm_mode} mode")

    # Process order based on mode (uses its own sessions)
    if comm_mode == "sync":
        await process_order_sync_simple(order_id, cart_data)
    else:
        if rabbitmq_client is None:
            raise HTTPException(
                status_code=503,
                detail="Async processing unavailable"
            )
        await process_order_async_simple(order_id, cart_data, rabbitmq_client)

    # Fetch final order state
    async with async_session() as session:
        result = await session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one()

        return OrderResponse(
            id=order.id,
            user_id=order.user_id,
            status=OrderStatus(order.status),
            total_amount=order.total_amount,
            communication_mode=CommunicationMode(order.communication_mode),
            items=[OrderItemResponse.model_validate(i) for i in order.items],
            created_at=order.created_at,
            updated_at=order.updated_at
        )


@router.get("", response_model=List[OrderResponse])
async def list_orders(
    user_id: Optional[str] = None,
    status: Optional[OrderStatus] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List orders with optional filtering."""
    query = select(Order).options(selectinload(Order.items))

    if user_id:
        query = query.where(Order.user_id == user_id)

    if status:
        query = query.where(Order.status == status.value)

    query = query.offset(offset).limit(limit).order_by(Order.created_at.desc())

    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        OrderResponse(
            id=o.id,
            user_id=o.user_id,
            status=OrderStatus(o.status),
            total_amount=o.total_amount,
            communication_mode=CommunicationMode(o.communication_mode),
            items=[OrderItemResponse.model_validate(i) for i in o.items],
            created_at=o.created_at,
            updated_at=o.updated_at
        )
        for o in orders
    ]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get an order by ID."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=OrderStatus(order.status),
        total_amount=order.total_amount,
        communication_mode=CommunicationMode(order.communication_mode),
        items=[OrderItemResponse.model_validate(i) for i in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at
    )


@router.get("/{order_id}/saga", response_model=SagaStateResponse)
async def get_order_saga(
    order_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get saga state for an order (async mode only)."""
    result = await db.execute(
        select(SagaState).where(SagaState.order_id == order_id)
    )
    saga = result.scalar_one_or_none()

    if not saga:
        raise HTTPException(status_code=404, detail="Saga state not found")

    return SagaStateResponse.model_validate(saga)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Cancel an order."""
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status in [OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order in {order.status} status"
        )

    order.status = OrderStatus.CANCELLED.value
    await db.commit()
    await db.refresh(order)

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=OrderStatus(order.status),
        total_amount=order.total_amount,
        communication_mode=CommunicationMode(order.communication_mode),
        items=[OrderItemResponse.model_validate(i) for i in order.items],
        created_at=order.created_at,
        updated_at=order.updated_at
    )
