"""Utility functions for the UI."""

import os
import httpx
from typing import Any, Dict, List, Optional

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8181")
TIMEOUT = 30.0


class APIClient:
    """Client for interacting with the API Gateway."""

    def __init__(self, base_url: str = API_GATEWAY_URL):
        self.base_url = base_url

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            url = f"{self.base_url}{path}"
            response = await client.request(
                method=method,
                url=url,
                json=json,
                params=params
            )
            response.raise_for_status()
            return response.json() if response.text else {}

    # Products
    async def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        params = {"page": page, "page_size": page_size}
        if category:
            params["category"] = category
        return await self._request("GET", "/api/products", params=params)

    async def get_product(self, product_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/products/{product_id}")

    async def list_categories(self) -> List[str]:
        return await self._request("GET", "/api/products/categories/list")

    # Cart
    async def create_cart(self, user_id: str) -> Dict[str, Any]:
        return await self._request("POST", "/api/carts", json={"user_id": user_id})

    async def get_cart(self, cart_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/carts/{cart_id}")

    async def get_cart_by_user(self, user_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/carts/user/{user_id}")

    async def add_to_cart(
        self,
        cart_id: str,
        product_id: str,
        quantity: int = 1
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/carts/{cart_id}/items",
            json={"product_id": product_id, "quantity": quantity}
        )

    async def update_cart_item(
        self,
        cart_id: str,
        item_id: str,
        quantity: int
    ) -> Dict[str, Any]:
        return await self._request(
            "PUT",
            f"/api/carts/{cart_id}/items/{item_id}",
            json={"quantity": quantity}
        )

    async def remove_cart_item(self, cart_id: str, item_id: str) -> Dict[str, Any]:
        return await self._request("DELETE", f"/api/carts/{cart_id}/items/{item_id}")

    async def clear_cart(self, cart_id: str) -> None:
        await self._request("DELETE", f"/api/carts/{cart_id}")

    # Orders
    async def create_order(
        self,
        user_id: str,
        cart_id: str,
        communication_mode: str = "sync"
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            "/api/orders",
            json={
                "user_id": user_id,
                "cart_id": cart_id,
                "communication_mode": communication_mode
            }
        )

    async def list_orders(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params = {}
        if user_id:
            params["user_id"] = user_id
        if status:
            params["status"] = status
        return await self._request("GET", "/api/orders", params=params)

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/orders/{order_id}")

    async def get_order_saga(self, order_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/orders/{order_id}/saga")

    # Inventory
    async def list_inventory(self) -> List[Dict[str, Any]]:
        return await self._request("GET", "/api/inventory")

    async def get_inventory(self, product_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/api/inventory/{product_id}")

    # Health
    async def health_check(self) -> Dict[str, Any]:
        return await self._request("GET", "/health")


def sync_request(
    method: str,
    path: str,
    json: Optional[Dict] = None,
    params: Optional[Dict] = None,
    base_url: str = API_GATEWAY_URL
) -> Dict[str, Any]:
    """Make a synchronous HTTP request."""
    with httpx.Client(timeout=TIMEOUT) as client:
        url = f"{base_url}{path}"
        response = client.request(
            method=method,
            url=url,
            json=json,
            params=params
        )
        response.raise_for_status()
        return response.json() if response.text else {}


# Convenience functions for synchronous calls
def list_products(page: int = 1, page_size: int = 20, category: Optional[str] = None):
    params = {"page": page, "page_size": page_size}
    if category:
        params["category"] = category
    return sync_request("GET", "/api/products", params=params)


def get_product(product_id: str):
    return sync_request("GET", f"/api/products/{product_id}")


def list_categories():
    try:
        return sync_request("GET", "/api/products/categories/list")
    except Exception:
        return []


def create_cart(user_id: str):
    return sync_request("POST", "/api/carts", json={"user_id": user_id})


def get_cart(cart_id: str):
    return sync_request("GET", f"/api/carts/{cart_id}")


def get_cart_by_user(user_id: str):
    try:
        return sync_request("GET", f"/api/carts/user/{user_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise


def add_to_cart(cart_id: str, product_id: str, quantity: int = 1):
    return sync_request(
        "POST",
        f"/api/carts/{cart_id}/items",
        json={"product_id": product_id, "quantity": quantity}
    )


def update_cart_item(cart_id: str, item_id: str, quantity: int):
    return sync_request(
        "PUT",
        f"/api/carts/{cart_id}/items/{item_id}",
        json={"quantity": quantity}
    )


def remove_cart_item(cart_id: str, item_id: str):
    try:
        return sync_request("DELETE", f"/api/carts/{cart_id}/items/{item_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Item already deleted, just return the current cart
            return get_cart(cart_id)
        raise


def create_order(user_id: str, cart_id: str, communication_mode: str = "sync"):
    return sync_request(
        "POST",
        "/api/orders",
        json={
            "user_id": user_id,
            "cart_id": cart_id,
            "communication_mode": communication_mode
        }
    )


def list_orders(user_id: Optional[str] = None):
    params = {}
    if user_id:
        params["user_id"] = user_id
    return sync_request("GET", "/api/orders", params=params)


def get_order(order_id: str):
    return sync_request("GET", f"/api/orders/{order_id}")


def get_order_saga(order_id: str):
    try:
        return sync_request("GET", f"/api/orders/{order_id}/saga")
    except httpx.HTTPStatusError:
        return None


def health_check():
    try:
        return sync_request("GET", "/health")
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
