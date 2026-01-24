"""Observability utilities: OpenTelemetry tracing + Prometheus metrics."""

import os
import time
import logging
from typing import Callable, Optional
from functools import wraps

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Prometheus Metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status", "communication_mode"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["service", "method", "endpoint", "communication_mode"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

RABBITMQ_MESSAGES_PUBLISHED = Counter(
    "rabbitmq_messages_published_total",
    "Total messages published to RabbitMQ",
    ["service", "routing_key"]
)

RABBITMQ_MESSAGES_CONSUMED = Counter(
    "rabbitmq_messages_consumed_total",
    "Total messages consumed from RabbitMQ",
    ["service", "queue"]
)

RABBITMQ_MESSAGES_DLQ = Counter(
    "rabbitmq_messages_dlq_total",
    "Total messages sent to DLQ",
    ["service", "queue"]
)

ACTIVE_ORDERS = Gauge(
    "active_orders",
    "Number of active orders",
    ["status", "communication_mode"]
)


def setup_observability(service_name: str, engine=None) -> None:
    """Initialize OpenTelemetry tracing with Jaeger exporter."""

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")

    resource = Resource.create({
        SERVICE_NAME: service_name
    })

    provider = TracerProvider(resource=resource)

    try:
        exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    except Exception as e:
        logger.warning(f"Failed to initialize OTLP exporter: {e}")

    trace.set_tracer_provider(provider)
    set_global_textmap(B3MultiFormat())

    # Instrument libraries
    HTTPXClientInstrumentor().instrument()

    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine)

    logger.info(f"Observability initialized for {service_name}")


def instrument_fastapi(app, service_name: str) -> None:
    """Instrument a FastAPI application."""
    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str = __name__):
    """Get a tracer instance."""
    return trace.get_tracer(name)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    def __init__(self, app, service_name: str):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint
        if request.url.path == "/metrics":
            return await call_next(request)

        # Get communication mode from header or default
        communication_mode = request.headers.get("X-Communication-Mode", "sync")
        method = request.method
        endpoint = self._get_endpoint_pattern(request.url.path)

        start_time = time.time()

        try:
            response = await call_next(request)
            status = str(response.status_code)
            # Check if response has communication mode header
            if "X-Communication-Mode" in response.headers:
                communication_mode = response.headers["X-Communication-Mode"]
        except Exception as e:
            status = "500"
            raise
        finally:
            duration = time.time() - start_time

            REQUEST_COUNT.labels(
                service=self.service_name,
                method=method,
                endpoint=endpoint,
                status=status,
                communication_mode=communication_mode
            ).inc()

            REQUEST_LATENCY.labels(
                service=self.service_name,
                method=method,
                endpoint=endpoint,
                communication_mode=communication_mode
            ).observe(duration)

        return response

    def _get_endpoint_pattern(self, path: str) -> str:
        """Normalize path to avoid high cardinality."""
        import re
        # Replace UUIDs with placeholder
        path = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '{id}',
            path,
            flags=re.IGNORECASE
        )
        # Replace numeric IDs with placeholder
        path = re.sub(r'/\d+', '/{id}', path)
        return path


def metrics_middleware(app, service_name: str):
    """Add metrics middleware to FastAPI app."""
    app.add_middleware(MetricsMiddleware, service_name=service_name)
    return app


async def metrics_endpoint():
    """Generate Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def trace_async(name: Optional[str] = None):
    """Decorator to trace async functions."""
    def decorator(func: Callable):
        tracer = get_tracer()
        span_name = name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name) as span:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        return wrapper
    return decorator


def trace_sync(name: Optional[str] = None):
    """Decorator to trace sync functions."""
    def decorator(func: Callable):
        tracer = get_tracer()
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name) as span:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        return wrapper
    return decorator
