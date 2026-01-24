"""RabbitMQ messaging client with retry and DLQ support."""

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field, asdict
from uuid import uuid4

import aio_pika
from aio_pika import Message, ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractExchange

from .observability import (
    RABBITMQ_MESSAGES_PUBLISHED,
    RABBITMQ_MESSAGES_CONSUMED,
    RABBITMQ_MESSAGES_DLQ,
    get_tracer
)

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event class for messaging."""
    event_type: str
    payload: Dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "Event":
        parsed = json.loads(data)
        return cls(**parsed)


class RabbitMQClient:
    """Async RabbitMQ client with retry logic and DLQ support."""

    EXCHANGE_NAME = "ecommerce.events"
    DLX_NAME = "ecommerce.dlx"
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.exchange: Optional[AbstractExchange] = None
        self._consumers: Dict[str, Callable] = {}
        self._url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

    async def connect(self) -> None:
        """Establish connection with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                self.connection = await aio_pika.connect_robust(self._url)
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=10)

                # Declare exchanges
                self.exchange = await self.channel.declare_exchange(
                    self.EXCHANGE_NAME,
                    ExchangeType.TOPIC,
                    durable=True
                )

                await self.channel.declare_exchange(
                    self.DLX_NAME,
                    ExchangeType.TOPIC,
                    durable=True
                )

                logger.info(f"Connected to RabbitMQ for service: {self.service_name}")
                return

            except Exception as e:
                logger.warning(f"RabbitMQ connection attempt {attempt + 1} failed: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise

    async def disconnect(self) -> None:
        """Close connection gracefully."""
        if self.connection:
            await self.connection.close()
            logger.info(f"Disconnected from RabbitMQ for service: {self.service_name}")

    async def publish(
        self,
        routing_key: str,
        event: Event,
        correlation_id: Optional[str] = None
    ) -> None:
        """Publish an event to the exchange."""
        tracer = get_tracer()

        with tracer.start_as_current_span(f"rabbitmq.publish.{routing_key}") as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination", routing_key)
            span.set_attribute("messaging.message_id", event.event_id)

            if correlation_id:
                event.correlation_id = correlation_id

            message = Message(
                body=event.to_json().encode(),
                content_type="application/json",
                message_id=event.event_id,
                correlation_id=event.correlation_id,
                headers={
                    "service": self.service_name,
                    "event_type": event.event_type,
                }
            )

            try:
                await self.exchange.publish(message, routing_key=routing_key)

                RABBITMQ_MESSAGES_PUBLISHED.labels(
                    service=self.service_name,
                    routing_key=routing_key
                ).inc()

                logger.debug(f"Published event {event.event_type} to {routing_key}")

            except Exception as e:
                span.record_exception(e)
                logger.error(f"Failed to publish event: {e}")
                raise

    async def subscribe(
        self,
        queue_name: str,
        routing_keys: list[str],
        handler: Callable[[Event], Any],
        auto_ack: bool = False
    ) -> None:
        """Subscribe to a queue with the given handler."""

        # Declare queue with DLQ
        queue = await self.channel.declare_queue(
            queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self.DLX_NAME,
                "x-dead-letter-routing-key": f"{queue_name}.dlq"
            }
        )

        # Bind routing keys
        for routing_key in routing_keys:
            await queue.bind(self.exchange, routing_key)

        # Declare and bind DLQ
        dlq = await self.channel.declare_queue(
            f"{queue_name}.dlq",
            durable=True
        )
        dlx = await self.channel.get_exchange(self.DLX_NAME)
        await dlq.bind(dlx, f"{queue_name}.dlq")

        async def process_message(message: aio_pika.IncomingMessage):
            tracer = get_tracer()

            async with message.process(requeue=False):
                with tracer.start_as_current_span(f"rabbitmq.consume.{queue_name}") as span:
                    span.set_attribute("messaging.system", "rabbitmq")
                    span.set_attribute("messaging.destination", queue_name)
                    span.set_attribute("messaging.message_id", message.message_id)

                    try:
                        event = Event.from_json(message.body.decode())

                        await handler(event)

                        RABBITMQ_MESSAGES_CONSUMED.labels(
                            service=self.service_name,
                            queue=queue_name
                        ).inc()

                        logger.debug(f"Processed event {event.event_type} from {queue_name}")

                    except Exception as e:
                        span.record_exception(e)
                        logger.error(f"Failed to process message: {e}")

                        # Track retry count
                        retry_count = (message.headers or {}).get("x-retry-count", 0)

                        if retry_count < self.MAX_RETRIES:
                            # Requeue with incremented retry count
                            headers = dict(message.headers or {})
                            headers["x-retry-count"] = retry_count + 1

                            retry_message = Message(
                                body=message.body,
                                content_type=message.content_type,
                                message_id=message.message_id,
                                correlation_id=message.correlation_id,
                                headers=headers
                            )

                            await asyncio.sleep(self.RETRY_DELAY * (retry_count + 1))
                            await self.exchange.publish(
                                retry_message,
                                routing_key=message.routing_key or queue_name
                            )
                        else:
                            # Send to DLQ
                            RABBITMQ_MESSAGES_DLQ.labels(
                                service=self.service_name,
                                queue=queue_name
                            ).inc()
                            logger.error(f"Message sent to DLQ after {self.MAX_RETRIES} retries")
                            raise

        await queue.consume(process_message)
        self._consumers[queue_name] = handler
        logger.info(f"Subscribed to queue {queue_name} with routing keys {routing_keys}")

    async def publish_order_created(self, order_id: str, order_data: dict) -> None:
        """Publish order.created event."""
        event = Event(
            event_type="order.created",
            payload={"order_id": order_id, **order_data}
        )
        await self.publish("order.created", event, correlation_id=order_id)

    async def publish_payment_requested(
        self,
        order_id: str,
        amount: float,
        correlation_id: str
    ) -> None:
        """Publish payment.requested event."""
        event = Event(
            event_type="payment.requested",
            payload={"order_id": order_id, "amount": amount},
            correlation_id=correlation_id
        )
        await self.publish("payment.requested", event)

    async def publish_payment_result(
        self,
        order_id: str,
        success: bool,
        transaction_id: Optional[str] = None,
        error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Publish payment result event."""
        event_type = "payment.succeeded" if success else "payment.failed"
        event = Event(
            event_type=event_type,
            payload={
                "order_id": order_id,
                "success": success,
                "transaction_id": transaction_id,
                "error": error
            },
            correlation_id=correlation_id
        )
        await self.publish(event_type, event)

    async def publish_stock_reserve(
        self,
        order_id: str,
        items: list[dict],
        correlation_id: str
    ) -> None:
        """Publish stock.reserve event."""
        event = Event(
            event_type="stock.reserve",
            payload={"order_id": order_id, "items": items},
            correlation_id=correlation_id
        )
        await self.publish("stock.reserve", event)

    async def publish_stock_result(
        self,
        order_id: str,
        success: bool,
        error: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> None:
        """Publish stock reservation result."""
        event_type = "stock.reserved" if success else "stock.failed"
        event = Event(
            event_type=event_type,
            payload={
                "order_id": order_id,
                "success": success,
                "error": error
            },
            correlation_id=correlation_id
        )
        await self.publish(event_type, event)

    async def publish_order_completed(
        self,
        order_id: str,
        correlation_id: str
    ) -> None:
        """Publish order.completed event."""
        event = Event(
            event_type="order.completed",
            payload={"order_id": order_id},
            correlation_id=correlation_id
        )
        await self.publish("order.completed", event)

    async def publish_order_failed(
        self,
        order_id: str,
        reason: str,
        correlation_id: str
    ) -> None:
        """Publish order.failed event."""
        event = Event(
            event_type="order.failed",
            payload={"order_id": order_id, "reason": reason},
            correlation_id=correlation_id
        )
        await self.publish("order.failed", event)
