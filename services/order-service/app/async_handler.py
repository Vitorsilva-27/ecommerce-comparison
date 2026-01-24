"""Asynchronous order processing handler with Saga pattern."""

import logging
from uuid import UUID
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Order, OrderItem, SagaState
from .schemas import OrderStatus, SagaStep
from .database import async_session

import sys
sys.path.insert(0, "/app")

from shared.messaging import RabbitMQClient, Event

logger = logging.getLogger(__name__)

SERVICE_NAME = "order-service"


class OrderSaga:
    """Saga orchestrator for async order processing."""

    def __init__(self, rabbitmq: RabbitMQClient):
        self.rabbitmq = rabbitmq

    async def start_saga(
        self,
        order: Order,
        cart_data: Dict[str, Any],
        db: AsyncSession
    ) -> SagaState:
        """Start the order saga."""
        order_id = order.id
        user_id = order.user_id
        total_amount = float(order.total_amount)
        logger.info(f"Starting saga for order {order_id}")

        # Build items from cart_data to avoid lazy loading issues
        order_items = [
            {"product_id": item["product_id"], "quantity": item["quantity"]}
            for item in cart_data.get("items", [])
        ]

        # Create saga state and update order in a fresh session
        async with async_session() as session:
            saga = SagaState(
                order_id=order_id,
                current_step=SagaStep.CREATED.value,
                status="in_progress"
            )
            session.add(saga)
            await session.commit()

        # Publish order.created event
        await self.rabbitmq.publish_order_created(
            order_id=str(order_id),
            order_data={
                "user_id": user_id,
                "total_amount": total_amount,
                "items": order_items
            }
        )

        # Update saga and order status
        async with async_session() as session:
            from sqlalchemy import update
            await session.execute(
                update(SagaState).where(SagaState.order_id == order_id)
                .values(current_step=SagaStep.PAYMENT_REQUESTED.value)
            )
            await session.execute(
                update(Order).where(Order.id == order_id)
                .values(status=OrderStatus.PAYMENT_PENDING.value)
            )
            await session.commit()

        await self.rabbitmq.publish_payment_requested(
            order_id=str(order_id),
            amount=total_amount,
            correlation_id=str(order_id)
        )

        logger.info(f"Payment requested for order {order_id}")
        return saga

    async def handle_payment_result(self, event: Event):
        """Handle payment result event."""
        order_id = UUID(event.payload.get("order_id"))
        success = event.payload.get("success", False)
        transaction_id = event.payload.get("transaction_id")
        error = event.payload.get("error")

        logger.info(f"Payment result for order {order_id}: success={success}")

        async with async_session() as db:
            # Get order and saga state
            result = await db.execute(
                select(Order)
                .options(selectinload(Order.items), selectinload(Order.saga_state))
                .where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()

            if not order or not order.saga_state:
                logger.error(f"Order or saga not found: {order_id}")
                return

            saga = order.saga_state

            if success:
                saga.payment_status = "succeeded"
                saga.current_step = SagaStep.PAYMENT_COMPLETED.value

                # Request stock reservation
                saga.current_step = SagaStep.STOCK_REQUESTED.value
                order.status = OrderStatus.STOCK_PENDING.value
                await db.commit()

                await self.rabbitmq.publish_stock_reserve(
                    order_id=str(order_id),
                    items=[
                        {"product_id": str(item.product_id), "quantity": item.quantity}
                        for item in order.items
                    ],
                    correlation_id=str(order_id)
                )

                logger.info(f"Stock reservation requested for order {order_id}")

            else:
                saga.payment_status = "failed"
                saga.current_step = SagaStep.FAILED.value
                saga.status = "failed"
                saga.error_message = error
                order.status = OrderStatus.PAYMENT_FAILED.value
                await db.commit()

                # Publish order.failed event
                await self.rabbitmq.publish_order_failed(
                    order_id=str(order_id),
                    reason=error or "Payment failed",
                    correlation_id=str(order_id)
                )

                logger.info(f"Order {order_id} failed: payment failed")

    async def handle_stock_result(self, event: Event):
        """Handle stock reservation result event."""
        order_id = UUID(event.payload.get("order_id"))
        success = event.payload.get("success", False)
        error = event.payload.get("error")

        logger.info(f"Stock result for order {order_id}: success={success}")

        async with async_session() as db:
            # Get order and saga state
            result = await db.execute(
                select(Order)
                .options(selectinload(Order.saga_state))
                .where(Order.id == order_id)
            )
            order = result.scalar_one_or_none()

            if not order or not order.saga_state:
                logger.error(f"Order or saga not found: {order_id}")
                return

            saga = order.saga_state

            if success:
                saga.inventory_status = "reserved"
                saga.current_step = SagaStep.COMPLETED.value
                saga.status = "completed"
                order.status = OrderStatus.COMPLETED.value
                await db.commit()

                # Publish order.completed event
                await self.rabbitmq.publish_order_completed(
                    order_id=str(order_id),
                    correlation_id=str(order_id)
                )

                logger.info(f"Order {order_id} completed successfully")

            else:
                saga.inventory_status = "failed"
                saga.current_step = SagaStep.COMPENSATING.value
                saga.error_message = error
                order.status = OrderStatus.STOCK_FAILED.value
                await db.commit()

                # Compensate: Refund payment (would publish refund event)
                logger.info(f"Compensating: refunding payment for order {order_id}")

                saga.current_step = SagaStep.FAILED.value
                saga.status = "failed"
                order.status = OrderStatus.FAILED.value
                await db.commit()

                # Publish order.failed event
                await self.rabbitmq.publish_order_failed(
                    order_id=str(order_id),
                    reason=error or "Stock reservation failed",
                    correlation_id=str(order_id)
                )

                logger.info(f"Order {order_id} failed: stock reservation failed")


async def process_order_async(
    order: Order,
    cart_data: Dict[str, Any],
    db: AsyncSession,
    rabbitmq: RabbitMQClient
) -> Order:
    """Start async order processing with saga."""
    logger.info(f"Processing order {order.id} in ASYNC mode")

    saga = OrderSaga(rabbitmq)
    await saga.start_saga(order, cart_data, db)

    return order


async def process_order_async_simple(
    order_id: UUID,
    cart_data: Dict[str, Any],
    rabbitmq: RabbitMQClient
) -> None:
    """Start async order processing with saga (simplified version)."""
    logger.info(f"Processing order {order_id} in ASYNC mode")

    total_amount = float(cart_data.get("total", 0))
    user_id = cart_data.get("user_id", "unknown")

    # Build items from cart_data
    order_items = [
        {"product_id": item["product_id"], "quantity": item["quantity"]}
        for item in cart_data.get("items", [])
    ]

    # Create saga state
    async with async_session() as session:
        saga = SagaState(
            order_id=order_id,
            current_step=SagaStep.CREATED.value,
            status="in_progress"
        )
        session.add(saga)
        await session.commit()

    # Publish order.created event
    await rabbitmq.publish_order_created(
        order_id=str(order_id),
        order_data={
            "user_id": user_id,
            "total_amount": total_amount,
            "items": order_items
        }
    )

    # Update saga and order status
    async with async_session() as session:
        from sqlalchemy import update
        await session.execute(
            update(SagaState).where(SagaState.order_id == order_id)
            .values(current_step=SagaStep.PAYMENT_REQUESTED.value)
        )
        await session.execute(
            update(Order).where(Order.id == order_id)
            .values(status=OrderStatus.PAYMENT_PENDING.value)
        )
        await session.commit()

    await rabbitmq.publish_payment_requested(
        order_id=str(order_id),
        amount=total_amount,
        correlation_id=str(order_id)
    )

    logger.info(f"Payment requested for order {order_id}")
