"""Async worker for inventory service - processes stock.reserve events."""

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import async_session
from .models import Stock

import sys
sys.path.insert(0, "/app")

from shared.messaging import RabbitMQClient, Event

logger = logging.getLogger(__name__)

SERVICE_NAME = "inventory-service"


class InventoryWorker:
    """Worker that processes stock reservation events."""

    def __init__(self):
        self.rabbitmq = RabbitMQClient(SERVICE_NAME)

    async def start(self):
        """Start the worker."""
        await self.rabbitmq.connect()

        # Subscribe to stock.reserve queue
        await self.rabbitmq.subscribe(
            queue_name="stock.reserve",
            routing_keys=["stock.reserve"],
            handler=self.handle_stock_reserve
        )

        logger.info("Inventory worker started, listening for stock.reserve events")

    async def stop(self):
        """Stop the worker."""
        await self.rabbitmq.disconnect()
        logger.info("Inventory worker stopped")

    async def handle_stock_reserve(self, event: Event):
        """Handle stock.reserve event."""
        logger.info(f"Processing stock.reserve event: {event.event_id}")

        order_id = event.payload.get("order_id")
        items = event.payload.get("items", [])
        correlation_id = event.correlation_id or order_id

        async with async_session() as db:
            try:
                reserved_items = []

                for item in items:
                    product_id = UUID(item["product_id"])
                    quantity = item["quantity"]

                    result = await db.execute(
                        select(Stock).where(Stock.product_id == product_id)
                    )
                    stock = result.scalar_one_or_none()

                    if not stock:
                        raise ValueError(f"Stock not found for product {product_id}")

                    if stock.available < quantity:
                        raise ValueError(
                            f"Insufficient stock for product {product_id}: "
                            f"available={stock.available}, requested={quantity}"
                        )

                    stock.reserved += quantity
                    reserved_items.append(str(product_id))

                await db.commit()

                # Publish success event
                await self.rabbitmq.publish_stock_result(
                    order_id=order_id,
                    success=True,
                    correlation_id=correlation_id
                )

                logger.info(f"Stock reserved for order {order_id}")

            except ValueError as e:
                await db.rollback()
                logger.error(f"Failed to reserve stock: {e}")

                # Publish failure event
                await self.rabbitmq.publish_stock_result(
                    order_id=order_id,
                    success=False,
                    error=str(e),
                    correlation_id=correlation_id
                )

            except Exception as e:
                await db.rollback()
                logger.error(f"Error processing stock.reserve: {e}")
                raise


async def run_worker():
    """Run the inventory worker."""
    worker = InventoryWorker()

    try:
        await worker.start()

        # Keep running
        while True:
            await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Worker cancelled")
    finally:
        await worker.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
