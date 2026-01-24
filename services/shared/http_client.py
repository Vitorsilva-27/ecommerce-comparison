"""HTTP client with retry logic and circuit breaker pattern."""

import os
import time
import asyncio
import logging
from typing import Any, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx
from opentelemetry import trace

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker implementation for HTTP calls."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0  # seconds before trying again

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: Optional[datetime] = field(default=None, init=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                if datetime.now() - self._last_failure_time > timedelta(seconds=self.timeout):
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker opened due to failures")

    def can_execute(self) -> bool:
        """Check if the circuit allows execution."""
        return self.state != CircuitState.OPEN


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class HttpClient:
    """Async HTTP client with retry logic and circuit breaker."""

    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5

    def __init__(
        self,
        service_name: str,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        self.service_name = service_name
        self.base_url = base_url or ""
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _ensure_client(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Make an HTTP request with retry logic and circuit breaker."""
        await self._ensure_client()
        tracer = trace.get_tracer(__name__)

        if not self.circuit_breaker.can_execute():
            raise CircuitOpenError(f"Circuit breaker is open for {self.service_name}")

        url = f"{self.base_url}{path}" if self.base_url else path

        for attempt in range(self.MAX_RETRIES):
            with tracer.start_as_current_span(f"http.{method.lower()}") as span:
                span.set_attribute("http.method", method)
                span.set_attribute("http.url", url)
                span.set_attribute("http.retry_attempt", attempt)

                try:
                    response = await self._client.request(method, path, **kwargs)

                    span.set_attribute("http.status_code", response.status_code)

                    if response.is_success:
                        self.circuit_breaker.record_success()
                        return response

                    if response.status_code >= 500:
                        self.circuit_breaker.record_failure()
                        if attempt < self.MAX_RETRIES - 1:
                            await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                            continue

                    return response

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    span.record_exception(e)
                    self.circuit_breaker.record_failure()

                    if attempt < self.MAX_RETRIES - 1:
                        logger.warning(
                            f"Request to {url} failed (attempt {attempt + 1}): {e}"
                        )
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    else:
                        raise

        raise httpx.HTTPError(f"Max retries exceeded for {url}")

    async def get(self, path: str, **kwargs) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs) -> httpx.Response:
        """Make a PUT request."""
        return await self.request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs) -> httpx.Response:
        """Make a DELETE request."""
        return await self.request("DELETE", path, **kwargs)

    async def get_json(self, path: str, **kwargs) -> Dict[str, Any]:
        """Make a GET request and return JSON."""
        response = await self.get(path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post_json(
        self,
        path: str,
        data: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Make a POST request with JSON body and return JSON."""
        response = await self.post(path, json=data, **kwargs)
        response.raise_for_status()
        return response.json()


class ServiceClient:
    """Pre-configured HTTP client for internal service communication."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._clients: Dict[str, HttpClient] = {}

    def _get_service_url(self, service: str) -> str:
        """Get the URL for a service from environment."""
        env_var = f"{service.upper().replace('-', '_')}_URL"
        return os.getenv(env_var, f"http://{service}:8181")

    async def _get_client(self, service: str) -> HttpClient:
        """Get or create a client for a service."""
        if service not in self._clients:
            url = self._get_service_url(service)
            self._clients[service] = HttpClient(
                service_name=self.service_name,
                base_url=url
            )
            await self._clients[service]._ensure_client()
        return self._clients[service]

    async def close_all(self) -> None:
        """Close all clients."""
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    async def call_catalog(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Call catalog service."""
        client = await self._get_client("catalog-service")
        return await client.request(method, path, **kwargs)

    async def call_cart(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Call cart service."""
        client = await self._get_client("cart-service")
        return await client.request(method, path, **kwargs)

    async def call_order(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Call order service."""
        client = await self._get_client("order-service")
        return await client.request(method, path, **kwargs)

    async def call_payment(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Call payment service."""
        client = await self._get_client("payment-service")
        return await client.request(method, path, **kwargs)

    async def call_inventory(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Call inventory service."""
        client = await self._get_client("inventory-service")
        return await client.request(method, path, **kwargs)
