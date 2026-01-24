"""API routes for catalog service."""

import json
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from .database import get_db
from .models import Product
from .schemas import ProductCreate, ProductUpdate, ProductResponse, ProductList

router = APIRouter(prefix="/products", tags=["products"])

# Redis client for caching
redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get Redis client."""
    global redis_client
    if redis_client is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.from_url(redis_url, decode_responses=True)
    return redis_client


CACHE_TTL = 300  # 5 minutes


@router.get("", response_model=ProductList)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all products with pagination and filtering."""
    query = select(Product)

    if category:
        query = query.where(Product.category == category)

    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    products = result.scalars().all()

    return ProductList(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total or 0,
        page=page,
        page_size=page_size
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis)
):
    """Get a product by ID."""
    cache_key = f"product:{product_id}"

    # Try cache first
    try:
        cached = await cache.get(cache_key)
        if cached:
            return ProductResponse.model_validate(json.loads(cached))
    except Exception:
        pass  # Cache miss or error

    # Query database
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    response = ProductResponse.model_validate(product)

    # Cache the result
    try:
        await cache.setex(
            cache_key,
            CACHE_TTL,
            response.model_dump_json()
        )
    except Exception:
        pass  # Cache write error

    return response


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new product."""
    db_product = Product(**product.model_dump())
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return ProductResponse.model_validate(db_product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis)
):
    """Update a product."""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    db_product = result.scalar_one_or_none()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)

    await db.commit()
    await db.refresh(db_product)

    # Invalidate cache
    try:
        await cache.delete(f"product:{product_id}")
    except Exception:
        pass

    return ProductResponse.model_validate(db_product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis)
):
    """Delete a product."""
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    db_product = result.scalar_one_or_none()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(db_product)
    await db.commit()

    # Invalidate cache
    try:
        await cache.delete(f"product:{product_id}")
    except Exception:
        pass


@router.get("/categories/list", response_model=List[str])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """List all product categories."""
    result = await db.execute(
        select(Product.category)
        .where(Product.category.isnot(None))
        .distinct()
    )
    categories = result.scalars().all()
    return list(categories)
