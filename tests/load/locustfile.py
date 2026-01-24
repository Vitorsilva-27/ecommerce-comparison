"""Load tests for E-commerce Comparison."""

import os
import random
from uuid import uuid4

from locust import HttpUser, task, between, events


# Sample product IDs from seed data
PRODUCT_IDS = [
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a12",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a13",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a14",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a15",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a16",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a17",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a18",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a19",
    "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a20",
]


class EcommerceUser(HttpUser):
    """Simulates a typical e-commerce user."""

    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user session."""
        self.user_id = f"loadtest-{uuid4().hex[:8]}"
        self.cart_id = None
        self.communication_mode = os.getenv("COMMUNICATION_MODE", "sync")

        # Create a cart for this user
        self._create_cart()

    def _create_cart(self):
        """Create a cart for the user."""
        response = self.client.post(
            "/api/carts",
            json={"user_id": self.user_id},
            name="/api/carts [create]"
        )
        if response.status_code == 201:
            data = response.json()
            self.cart_id = data.get("id")
        elif response.status_code == 200:
            # Cart already exists
            data = response.json()
            self.cart_id = data.get("id")

    @task(5)
    def browse_products(self):
        """Browse product listing."""
        self.client.get(
            "/api/products",
            params={"page": 1, "page_size": 20},
            name="/api/products [list]"
        )

    @task(3)
    def view_product(self):
        """View a specific product."""
        product_id = random.choice(PRODUCT_IDS)
        self.client.get(
            f"/api/products/{product_id}",
            name="/api/products/{id} [get]"
        )

    @task(2)
    def add_to_cart(self):
        """Add a product to cart."""
        if not self.cart_id:
            self._create_cart()
            if not self.cart_id:
                return

        product_id = random.choice(PRODUCT_IDS)
        self.client.post(
            f"/api/carts/{self.cart_id}/items",
            json={
                "product_id": product_id,
                "quantity": random.randint(1, 3)
            },
            name="/api/carts/{id}/items [add]"
        )

    @task(2)
    def view_cart(self):
        """View cart contents."""
        if not self.cart_id:
            self._create_cart()
            return

        self.client.get(
            f"/api/carts/{self.cart_id}",
            name="/api/carts/{id} [get]"
        )

    @task(1)
    def checkout(self):
        """Create an order from cart."""
        if not self.cart_id:
            self._create_cart()
            return

        # First add some items if cart might be empty
        for _ in range(random.randint(1, 3)):
            product_id = random.choice(PRODUCT_IDS)
            self.client.post(
                f"/api/carts/{self.cart_id}/items",
                json={
                    "product_id": product_id,
                    "quantity": random.randint(1, 2)
                },
                name="/api/carts/{id}/items [add]"
            )

        # Create order
        response = self.client.post(
            "/api/orders",
            json={
                "user_id": self.user_id,
                "cart_id": self.cart_id,
                "communication_mode": self.communication_mode
            },
            name=f"/api/orders [create-{self.communication_mode}]"
        )

        if response.status_code in [200, 201]:
            order = response.json()
            # Create new cart after checkout
            self.cart_id = None
            self._create_cart()

    @task(1)
    def view_orders(self):
        """View order history."""
        self.client.get(
            "/api/orders",
            params={"user_id": self.user_id},
            name="/api/orders [list]"
        )


class SyncUser(EcommerceUser):
    """User that only uses sync mode."""

    def on_start(self):
        super().on_start()
        self.communication_mode = "sync"


class AsyncUser(EcommerceUser):
    """User that only uses async mode."""

    def on_start(self):
        super().on_start()
        self.communication_mode = "async"


class MixedUser(EcommerceUser):
    """User that randomly uses sync or async mode."""

    def on_start(self):
        super().on_start()

    @task(1)
    def checkout(self):
        """Create an order with random mode."""
        self.communication_mode = random.choice(["sync", "async"])
        super().checkout()


class BrowseOnlyUser(HttpUser):
    """User that only browses (read-heavy load)."""

    wait_time = between(0.5, 2)

    @task(10)
    def browse_products(self):
        """Browse product listing."""
        self.client.get(
            "/api/products",
            params={"page": random.randint(1, 3), "page_size": 20},
            name="/api/products [list]"
        )

    @task(5)
    def view_product(self):
        """View a specific product."""
        product_id = random.choice(PRODUCT_IDS)
        self.client.get(
            f"/api/products/{product_id}",
            name="/api/products/{id} [get]"
        )

    @task(1)
    def view_inventory(self):
        """Check inventory."""
        product_id = random.choice(PRODUCT_IDS)
        self.client.get(
            f"/api/inventory/{product_id}",
            name="/api/inventory/{id} [get]"
        )


class CheckoutHeavyUser(HttpUser):
    """User that focuses on checkout (write-heavy load)."""

    wait_time = between(0.5, 1)

    def on_start(self):
        """Initialize user session."""
        self.user_id = f"checkout-{uuid4().hex[:8]}"
        self.cart_id = None
        self.communication_mode = os.getenv("COMMUNICATION_MODE", "sync")

    def _ensure_cart(self):
        """Ensure user has a cart."""
        if not self.cart_id:
            response = self.client.post(
                "/api/carts",
                json={"user_id": self.user_id},
                name="/api/carts [create]"
            )
            if response.status_code in [200, 201]:
                self.cart_id = response.json().get("id")

    @task
    def rapid_checkout(self):
        """Quickly add items and checkout."""
        self._ensure_cart()
        if not self.cart_id:
            return

        # Add items
        for _ in range(random.randint(1, 5)):
            product_id = random.choice(PRODUCT_IDS)
            self.client.post(
                f"/api/carts/{self.cart_id}/items",
                json={
                    "product_id": product_id,
                    "quantity": 1
                },
                name="/api/carts/{id}/items [add]"
            )

        # Checkout
        self.client.post(
            "/api/orders",
            json={
                "user_id": self.user_id,
                "cart_id": self.cart_id,
                "communication_mode": self.communication_mode
            },
            name=f"/api/orders [create-{self.communication_mode}]"
        )

        # Reset cart
        self.cart_id = None


# Event hooks for custom reporting
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Log request details for debugging."""
    if exception:
        print(f"Request failed: {name} - {exception}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print(f"Load test starting...")
    print(f"Target host: {environment.host}")
    print(f"Communication mode: {os.getenv('COMMUNICATION_MODE', 'sync')}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("Load test completed.")
