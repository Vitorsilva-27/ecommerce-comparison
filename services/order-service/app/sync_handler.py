"""Synchronous order processing handler."""

import os
import logging
from uuid import UUID
from decimal import Decimal
from typing import List, Dict, Any

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Order, OrderItem
from .schemas import OrderStatus
from .database import async_session

logger = logging.getLogger(__name__)

CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://cart-service:8002")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8005")

HTTP_TIMEOUT = 30.0


async def update_order_status(order_id: UUID, status: str):
    """Update order status using a fresh session."""
    async with async_session() as db:
        await db.execute(
            update(Order).where(Order.id == order_id).values(status=status)
        )
        await db.commit()


async def process_order_sync_simple(
    order_id: UUID,
    cart_data: Dict[str, Any]
) -> None:
    """Process order synchronously with direct HTTP calls."""
    # Get total amount from cart
    total_amount = float(cart_data.get("total", 0))
    logger.info(f"Processing order {order_id} in SYNC mode")

    # Build stock request from cart_data to avoid lazy loading issues
    stock_items = [
        {"product_id": item["product_id"], "quantity": item["quantity"]}
        for item in cart_data.get("items", [])
    ]

    stock_request = {
        "order_id": str(order_id),
        "items": stock_items
    }

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            # Step 1: Reserve stock
            logger.info(f"Reserving stock for order {order_id}")
            await update_order_status(order_id, OrderStatus.STOCK_PENDING.value)

            stock_response = await client.post(
                f"{INVENTORY_SERVICE_URL}/inventory/reserve",
                json=stock_request
            )
            stock_result = stock_response.json()

            if not stock_result.get("success"):
                logger.error(f"Stock reservation failed: {stock_result.get('error')}")
                await update_order_status(order_id, OrderStatus.STOCK_FAILED.value)
                return

            # Step 2: Process payment
            logger.info(f"Processing payment for order {order_id}")
            await update_order_status(order_id, OrderStatus.PAYMENT_PENDING.value)

            payment_request = {
                "order_id": str(order_id),
                "amount": total_amount
            }

            payment_response = await client.post(
                f"{PAYMENT_SERVICE_URL}/payments/process",
                json=payment_request
            )
            payment_result = payment_response.json()

            if not payment_result.get("success"):
                logger.error(f"Payment failed: {payment_result.get('error')}")

                # Compensate: Release stock
                await client.post(
                    f"{INVENTORY_SERVICE_URL}/inventory/release",
                    json=stock_request
                )

                await update_order_status(order_id, OrderStatus.PAYMENT_FAILED.value)
                return

            # Step 3: Confirm stock (deduct from quantity)
            logger.info(f"Confirming stock for order {order_id}")
            await client.post(
                f"{INVENTORY_SERVICE_URL}/inventory/confirm",
                json=stock_request
            )

            # Step 4: Clear cart
            try:
                await client.delete(f"{CART_SERVICE_URL}/carts/{cart_data['id']}")
            except Exception as e:
                logger.warning(f"Failed to clear cart: {e}")

            # Order completed
            await update_order_status(order_id, OrderStatus.COMPLETED.value)
            logger.info(f"Order {order_id} completed successfully")

        except httpx.TimeoutException as e:
            logger.error(f"Timeout processing order {order_id}: {e}")
            await update_order_status(order_id, OrderStatus.FAILED.value)
            raise

        except Exception as e:
            logger.error(f"Error processing order {order_id}: {e}")
            await update_order_status(order_id, OrderStatus.FAILED.value)
            raise
