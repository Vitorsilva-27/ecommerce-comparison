"""Middleware for API Gateway."""

import time
import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

        # Log response
        duration = time.time() - start_time
        logger.info(
            f"Response: {request.method} {request.url.path} "
            f"status={response.status_code} duration={duration:.3f}s"
        )

        return response


class CommunicationModeMiddleware(BaseHTTPMiddleware):
    """Middleware to inject communication mode header."""

    def __init__(self, app, mode: str):
        super().__init__(app)
        self.mode = mode

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Add communication mode to request state
        request.state.communication_mode = self.mode

        response = await call_next(request)

        # Add header to response
        response.headers["X-Communication-Mode"] = self.mode

        return response
