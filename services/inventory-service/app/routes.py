"""API routes for inventory service."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import Stock
from .schemas import (
    StockCreate, StockUpdate, StockResponse,
    StockReserveRequest, StockReserveResponse,
    StockReleaseRequest
)

router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)


@router.get("", response_model=List[StockResponse])
async def list_stock(db: AsyncSession = Depends(get_db)):
    """List all stock items."""
    result = await db.execute(select(Stock))
    stocks = result.scalars().all()
    return [
        StockResponse(
            id=s.id,
            product_id=s.product_id,
            quantity=s.quantity,
            reserved=s.reserved,
            available=s.available,
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in stocks
    ]


@router.get("/{product_id}", response_model=StockResponse)
async def get_stock(
    product_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get stock for a product."""
    result = await db.execute(
        select(Stock).where(Stock.product_id == product_id)
    )
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    return StockResponse(
        id=stock.id,
        product_id=stock.product_id,
        quantity=stock.quantity,
        reserved=stock.reserved,
        available=stock.available,
        created_at=stock.created_at,
        updated_at=stock.updated_at
    )


@router.post("", response_model=StockResponse, status_code=201)
async def create_stock(
    stock: StockCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create stock for a product."""
    # Check if stock already exists
    result = await db.execute(
        select(Stock).where(Stock.product_id == stock.product_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="Stock already exists for product")

    db_stock = Stock(
        product_id=stock.product_id,
        quantity=stock.quantity,
        reserved=0
    )
    db.add(db_stock)
    await db.commit()
    await db.refresh(db_stock)

    return StockResponse(
        id=db_stock.id,
        product_id=db_stock.product_id,
        quantity=db_stock.quantity,
        reserved=db_stock.reserved,
        available=db_stock.available,
        created_at=db_stock.created_at,
        updated_at=db_stock.updated_at
    )


@router.put("/{product_id}", response_model=StockResponse)
async def update_stock(
    product_id: UUID,
    stock: StockUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update stock quantity for a product."""
    result = await db.execute(
        select(Stock).where(Stock.product_id == product_id)
    )
    db_stock = result.scalar_one_or_none()

    if not db_stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    db_stock.quantity = stock.quantity
    await db.commit()
    await db.refresh(db_stock)

    return StockResponse(
        id=db_stock.id,
        product_id=db_stock.product_id,
        quantity=db_stock.quantity,
        reserved=db_stock.reserved,
        available=db_stock.available,
        created_at=db_stock.created_at,
        updated_at=db_stock.updated_at
    )


@router.post("/reserve", response_model=StockReserveResponse)
async def reserve_stock(
    request: StockReserveRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reserve stock for an order (sync mode)."""
    reserved_items = []

    try:
        for item in request.items:
            result = await db.execute(
                select(Stock).where(Stock.product_id == item.product_id)
            )
            stock = result.scalar_one_or_none()

            if not stock:
                raise ValueError(f"Stock not found for product {item.product_id}")

            if stock.available < item.quantity:
                raise ValueError(
                    f"Insufficient stock for product {item.product_id}: "
                    f"available={stock.available}, requested={item.quantity}"
                )

            stock.reserved += item.quantity
            reserved_items.append(item.product_id)

        await db.commit()

        logger.info(f"Reserved stock for order {request.order_id}")
        return StockReserveResponse(
            success=True,
            reserved_items=reserved_items
        )

    except ValueError as e:
        # Rollback any reservations
        await db.rollback()
        logger.error(f"Failed to reserve stock: {e}")
        return StockReserveResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error reserving stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/release", response_model=StockReserveResponse)
async def release_stock(
    request: StockReleaseRequest,
    db: AsyncSession = Depends(get_db)
):
    """Release reserved stock (compensation)."""
    released_items = []

    try:
        for item in request.items:
            result = await db.execute(
                select(Stock).where(Stock.product_id == item.product_id)
            )
            stock = result.scalar_one_or_none()

            if stock:
                stock.reserved = max(0, stock.reserved - item.quantity)
                released_items.append(item.product_id)

        await db.commit()

        logger.info(f"Released stock for order {request.order_id}")
        return StockReserveResponse(
            success=True,
            reserved_items=released_items
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error releasing stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm", response_model=StockReserveResponse)
async def confirm_stock(
    request: StockReleaseRequest,
    db: AsyncSession = Depends(get_db)
):
    """Confirm stock reservation (deduct from quantity)."""
    confirmed_items = []

    try:
        for item in request.items:
            result = await db.execute(
                select(Stock).where(Stock.product_id == item.product_id)
            )
            stock = result.scalar_one_or_none()

            if stock:
                stock.quantity -= item.quantity
                stock.reserved = max(0, stock.reserved - item.quantity)
                confirmed_items.append(item.product_id)

        await db.commit()

        logger.info(f"Confirmed stock for order {request.order_id}")
        return StockReserveResponse(
            success=True,
            reserved_items=confirmed_items
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error confirming stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))
