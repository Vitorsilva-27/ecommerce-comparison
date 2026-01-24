"""Async worker for payment service - processes payment.requested events."""

import os
import asyncio
import logging
import random
from uuid import uuid4, UUID
from decimal import Decimal

from sqlalchemy import select

from .database import async_session
from .models import Payment

import sys
sys.path.insert(0, "/app")

from shared.messaging import RabbitMQClient, Event

logger = logging.getLogger(__name__)

SERVICE_NAME = "payment-service"

# Payment simulation config
PAYMENT_FAILURE_RATE = float(os.getenv("PAYMENT_FAILURE_RATE", "0.1"))
PAYMENT_DELAY_MS = int(os.getenv("PAYMENT_DELAY_MS", "100"))


async def simulate_payment_processing(amount: float) -> tuple[bool, str | None, str | None]:
    """Simulate payment gateway call."""
    # Simulate processing delay
    await asyncio.sleep(PAYMENT_DELAY_MS / 1000)

    # Simulate random failures
    if random.random() < PAYMENT_FAILURE_RATE:
        return False, None, "Payment declined by gateway"

    # Generate transaction ID
    transaction_id = f"TXN-{uuid4().hex[:12].upper()}"
    return True, transaction_id, None


class PaymentWorker:
    """Worker that processes payment events."""

    def __init__(self):
        self.rabbitmq = RabbitMQClient(SERVICE_NAME)

    async def start(self):
        """Start the worker."""
        await self.rabbitmq.connect()

        # Subscribe to payment.requested queue
        await self.rabbitmq.subscribe(
            queue_name="payment.requested",
            routing_keys=["payment.requested"],
            handler=self.handle_payment_requested
        )

        logger.info("Payment worker started, listening for payment.requested events")

    async def stop(self):
        """Stop the worker."""
        await self.rabbitmq.disconnect()
        logger.info("Payment worker stopped")

    async def handle_payment_requested(self, event: Event):
        """Handle payment.requested event."""
        logger.info(f"Processing payment.requested event: {event.event_id}")

        order_id = event.payload.get("order_id")
        amount = Decimal(str(event.payload.get("amount", 0)))
        correlation_id = event.correlation_id or order_id

        async with async_session() as db:
            try:
                # Create payment record
                payment = Payment(
                    order_id=UUID(order_id),
                    amount=amount,
                    status="processing"
                )
                db.add(payment)
                await db.commit()

                # Simulate payment processing
                success, transaction_id, error = await simulate_payment_processing(float(amount))

                # Update payment status
                if success:
                    payment.status = "succeeded"
                    payment.transaction_id = transaction_id
                else:
                    payment.status = "failed"
                    payment.error_message = error

                await db.commit()

                # Publish result event
                await self.rabbitmq.publish_payment_result(
                    order_id=order_id,
                    success=success,
                    transaction_id=transaction_id,
                    error=error,
                    correlation_id=correlation_id
                )

                logger.info(
                    f"Payment for order {order_id}: "
                    f"{'success' if success else 'failed'}"
                )

            except Exception as e:
                await db.rollback()
                logger.error(f"Error processing payment: {e}")

                # Publish failure event
                await self.rabbitmq.publish_payment_result(
                    order_id=order_id,
                    success=False,
                    error=str(e),
                    correlation_id=correlation_id
                )
                raise


async def run_worker():
    """Run the payment worker."""
    worker = PaymentWorker()

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
