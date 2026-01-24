"""Order Service - Main application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import sync_engine
from .routes import router, set_rabbitmq_client
from .async_handler import OrderSaga

import sys
sys.path.insert(0, "/app")

from shared.observability import (
    setup_observability,
    metrics_middleware,
    metrics_endpoint,
    instrument_fastapi
)
from shared.messaging import RabbitMQClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = "order-service"

# RabbitMQ client
rabbitmq: RabbitMQClient = None
saga: OrderSaga = None
consumer_task: asyncio.Task = None


async def start_consumers():
    """Start event consumers for saga."""
    global rabbitmq, saga

    rabbitmq = RabbitMQClient(SERVICE_NAME)
    await rabbitmq.connect()

    saga = OrderSaga(rabbitmq)

    # Subscribe to payment result events
    await rabbitmq.subscribe(
        queue_name="payment.completed",
        routing_keys=["payment.succeeded", "payment.failed"],
        handler=saga.handle_payment_result
    )

    # Subscribe to stock result events
    await rabbitmq.subscribe(
        queue_name="stock.reserved",
        routing_keys=["stock.reserved", "stock.failed"],
        handler=saga.handle_stock_result
    )

    # Make RabbitMQ client available to routes
    set_rabbitmq_client(rabbitmq)

    logger.info("Order saga consumers started")

    # Keep running
    while True:
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global consumer_task

    logger.info(f"Starting {SERVICE_NAME}")
    setup_observability(SERVICE_NAME, engine=sync_engine)

    # Start saga consumers in background
    consumer_task = asyncio.create_task(start_consumers())

    yield

    # Cleanup
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

    if rabbitmq:
        await rabbitmq.disconnect()

    logger.info(f"Shutting down {SERVICE_NAME}")


app = FastAPI(
    title="Order Service",
    description="Order management with sync/async support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics middleware
metrics_middleware(app, SERVICE_NAME)

# Instrument FastAPI
instrument_fastapi(app, SERVICE_NAME)

# Include routes
app.include_router(router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    import os
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "communication_mode": os.getenv("COMMUNICATION_MODE", "sync")
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return await metrics_endpoint()
