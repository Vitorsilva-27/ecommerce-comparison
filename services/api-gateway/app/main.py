"""API Gateway - Main application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import router
from .middleware import RequestLoggingMiddleware, CommunicationModeMiddleware

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

SERVICE_NAME = "api-gateway"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting {SERVICE_NAME}")
    logger.info(f"Communication mode: {settings.communication_mode}")
    setup_observability(SERVICE_NAME)
    yield
    logger.info(f"Shutting down {SERVICE_NAME}")


app = FastAPI(
    title="E-commerce API Gateway",
    description="API Gateway for e-commerce microservices",
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

# Add custom middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(CommunicationModeMiddleware, mode=settings.communication_mode)

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
        "version": "1.0.0",
        "communication_mode": settings.communication_mode
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return await metrics_endpoint()


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "service": "E-commerce API Gateway",
        "version": "1.0.0",
        "communication_mode": settings.communication_mode,
        "endpoints": {
            "products": "/api/products",
            "carts": "/api/carts",
            "orders": "/api/orders",
            "inventory": "/api/inventory",
            "payments": "/api/payments",
            "health": "/health",
            "metrics": "/metrics"
        }
    }
