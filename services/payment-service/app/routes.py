"""API routes for payment service."""

import os
import logging
import random
import asyncio
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import Payment
from .schemas import (
    PaymentCreate, PaymentProcess, PaymentResponse, PaymentResult
)

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)

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


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a payment by ID."""
    result = await db.execute(
        select(Payment).where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return PaymentResponse.model_validate(payment)


@router.get("/order/{order_id}", response_model=PaymentResponse)
async def get_payment_by_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get payment for an order."""
    result = await db.execute(
        select(Payment).where(Payment.order_id == order_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return PaymentResponse.model_validate(payment)


@router.post("/process", response_model=PaymentResult)
async def process_payment(
    request: PaymentProcess,
    db: AsyncSession = Depends(get_db)
):
    """Process a payment (sync mode)."""
    logger.info(f"Processing payment for order {request.order_id}")

    # Create payment record
    payment = Payment(
        order_id=request.order_id,
        amount=request.amount,
        status="processing"
    )
    db.add(payment)
    await db.commit()

    # Simulate payment processing
    success, transaction_id, error = await simulate_payment_processing(float(request.amount))

    # Update payment status
    if success:
        payment.status = "succeeded"
        payment.transaction_id = transaction_id
    else:
        payment.status = "failed"
        payment.error_message = error

    await db.commit()

    logger.info(f"Payment for order {request.order_id}: {'success' if success else 'failed'}")

    return PaymentResult(
        success=success,
        transaction_id=transaction_id,
        error=error
    )


@router.post("/refund/{order_id}", response_model=PaymentResult)
async def refund_payment(
    order_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Refund a payment (compensation)."""
    logger.info(f"Refunding payment for order {order_id}")

    result = await db.execute(
        select(Payment).where(Payment.order_id == order_id)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != "succeeded":
        raise HTTPException(status_code=400, detail="Cannot refund non-successful payment")

    # Simulate refund processing
    await asyncio.sleep(PAYMENT_DELAY_MS / 1000)

    payment.status = "refunded"
    await db.commit()

    logger.info(f"Payment refunded for order {order_id}")

    return PaymentResult(
        success=True,
        transaction_id=f"REF-{payment.transaction_id}"
    )
