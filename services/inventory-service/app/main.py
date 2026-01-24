"""Inventory Service - Main application."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import sync_engine
from .routes import router
from .worker import InventoryWorker

import sys
sys.path.insert(0, "/app")

from shared.observability import (
    setup_observability,
    metrics_middleware,
    metrics_endpoint,
    instrument_fastapi
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_NAME = "inventory-service"

# Worker instance
worker: InventoryWorker = None
worker_task: asyncio.Task = None


async def start_worker():
    """Start the async worker."""
    global worker
    worker = InventoryWorker()
    await worker.start()

    # Keep worker running
    while True:
        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global worker_task

    logger.info(f"Starting {SERVICE_NAME}")
    setup_observability(SERVICE_NAME, engine=sync_engine)

    # Start worker in background
    worker_task = asyncio.create_task(start_worker())

    yield

    # Cleanup
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    if worker:
        await worker.stop()

    logger.info(f"Shutting down {SERVICE_NAME}")


app = FastAPI(
    title="Inventory Service",
    description="Stock management service",
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
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "1.0.0"
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return await metrics_endpoint()
