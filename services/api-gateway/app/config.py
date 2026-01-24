"""Configuration for API Gateway."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service URLs
    catalog_service_url: str = os.getenv(
        "CATALOG_SERVICE_URL", "http://catalog-service:8001"
    )
    cart_service_url: str = os.getenv(
        "CART_SERVICE_URL", "http://cart-service:8002"
    )
    order_service_url: str = os.getenv(
        "ORDER_SERVICE_URL", "http://order-service:8003"
    )
    payment_service_url: str = os.getenv(
        "PAYMENT_SERVICE_URL", "http://payment-service:8004"
    )
    inventory_service_url: str = os.getenv(
        "INVENTORY_SERVICE_URL", "http://inventory-service:8005"
    )

    # Communication mode
    communication_mode: str = os.getenv("COMMUNICATION_MODE", "sync")

    # Timeouts
    request_timeout: float = 30.0

    class Config:
        env_file = ".env"


settings = Settings()
