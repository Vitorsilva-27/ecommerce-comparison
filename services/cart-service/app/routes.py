"""API routes for cart service."""

import os
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import httpx

from .database import get_db
from .models import Cart, CartItem
from .schemas import (
    CartCreate, CartResponse, CartItemResponse,
    AddToCartRequest, CartItemUpdate
)

router = APIRouter(prefix="/carts", tags=["carts"])

CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://catalog-service:8001")


async def get_product_price(product_id: UUID) -> Decimal:
    """Get product price from catalog service."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CATALOG_SERVICE_URL}/products/{product_id}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Product not found")
        response.raise_for_status()
        product = response.json()
        return Decimal(str(product["price"]))


def calculate_cart_total(items: list) -> Decimal:
    """Calculate cart total."""
    return sum(Decimal(str(item.price)) * item.quantity for item in items)


@router.post("", response_model=CartResponse, status_code=201)
async def create_cart(
    cart: CartCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new cart for a user."""
    # Check if user already has a cart
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.user_id == cart.user_id)
    )
    existing_cart = result.scalar_one_or_none()

    if existing_cart:
        return CartResponse(
            id=existing_cart.id,
            user_id=existing_cart.user_id,
            items=[CartItemResponse.model_validate(i) for i in existing_cart.items],
            total=calculate_cart_total(existing_cart.items),
            created_at=existing_cart.created_at,
            updated_at=existing_cart.updated_at
        )

    db_cart = Cart(user_id=cart.user_id)
    db.add(db_cart)
    await db.commit()
    await db.refresh(db_cart)

    return CartResponse(
        id=db_cart.id,
        user_id=db_cart.user_id,
        items=[],
        total=Decimal("0"),
        created_at=db_cart.created_at,
        updated_at=db_cart.updated_at
    )


@router.get("/{cart_id}", response_model=CartResponse)
async def get_cart(
    cart_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a cart by ID."""
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id)
    )
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[CartItemResponse.model_validate(i) for i in cart.items],
        total=calculate_cart_total(cart.items),
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )


@router.get("/user/{user_id}", response_model=CartResponse)
async def get_cart_by_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a cart by user ID."""
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.user_id == user_id)
    )
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[CartItemResponse.model_validate(i) for i in cart.items],
        total=calculate_cart_total(cart.items),
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )


@router.post("/{cart_id}/items", response_model=CartResponse)
async def add_item_to_cart(
    cart_id: UUID,
    request: AddToCartRequest,
    db: AsyncSession = Depends(get_db)
):
    """Add an item to the cart."""
    # Get cart
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id)
    )
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    # Get product price
    price = await get_product_price(request.product_id)

    # Check if item already exists
    existing_item = next(
        (i for i in cart.items if i.product_id == request.product_id),
        None
    )

    if existing_item:
        existing_item.quantity += request.quantity
        existing_item.price = price
    else:
        new_item = CartItem(
            cart_id=cart_id,
            product_id=request.product_id,
            quantity=request.quantity,
            price=price
        )
        db.add(new_item)
        cart.items.append(new_item)

    await db.commit()
    await db.refresh(cart)

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[CartItemResponse.model_validate(i) for i in cart.items],
        total=calculate_cart_total(cart.items),
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )


@router.put("/{cart_id}/items/{item_id}", response_model=CartResponse)
async def update_cart_item(
    cart_id: UUID,
    item_id: UUID,
    update: CartItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a cart item quantity."""
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id)
    )
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.quantity = update.quantity
    await db.commit()
    await db.refresh(cart)

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[CartItemResponse.model_validate(i) for i in cart.items],
        total=calculate_cart_total(cart.items),
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )


@router.delete("/{cart_id}/items/{item_id}", response_model=CartResponse)
async def remove_cart_item(
    cart_id: UUID,
    item_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Remove an item from the cart."""
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id)
    )
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()

    # Refresh cart
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id)
    )
    cart = result.scalar_one()

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=[CartItemResponse.model_validate(i) for i in cart.items],
        total=calculate_cart_total(cart.items),
        created_at=cart.created_at,
        updated_at=cart.updated_at
    )


@router.delete("/{cart_id}", status_code=204)
async def clear_cart(
    cart_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Clear all items from a cart."""
    result = await db.execute(
        select(Cart)
        .options(selectinload(Cart.items))
        .where(Cart.id == cart_id)
    )
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    for item in cart.items:
        await db.delete(item)

    await db.commit()
