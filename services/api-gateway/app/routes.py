"""API Gateway routes - proxies requests to backend services."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
import httpx

from .config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

HTTP_TIMEOUT = settings.request_timeout


async def proxy_request(
    method: str,
    url: str,
    request: Request,
    json_body: Optional[Dict[str, Any]] = None,
    communication_mode: str = "sync"
) -> JSONResponse:
    """Proxy a request to a backend service."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        try:
            # Build headers
            headers = {
                "Content-Type": "application/json",
                "X-Communication-Mode": communication_mode
            }

            # Make request
            if method == "GET":
                response = await client.get(url, headers=headers, params=request.query_params)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json_body)
            elif method == "PUT":
                response = await client.put(url, headers=headers, json=json_body)
            elif method == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

            return JSONResponse(
                content=response.json() if response.text else None,
                status_code=response.status_code
            )

        except httpx.TimeoutException:
            logger.error(f"Timeout proxying to {url}")
            raise HTTPException(status_code=504, detail="Gateway timeout")
        except httpx.ConnectError:
            logger.error(f"Connection error proxying to {url}")
            raise HTTPException(status_code=503, detail="Service unavailable")
        except Exception as e:
            logger.error(f"Error proxying to {url}: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# ============== Products ==============

@router.get("/api/products")
async def list_products(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None
):
    """List all products."""
    url = f"{settings.catalog_service_url}/products"
    return await proxy_request("GET", url, request)


@router.get("/api/products/{product_id}")
async def get_product(product_id: str, request: Request):
    """Get a product by ID."""
    url = f"{settings.catalog_service_url}/products/{product_id}"
    return await proxy_request("GET", url, request)


@router.get("/api/products/categories/list")
async def list_categories(request: Request):
    """List all categories."""
    url = f"{settings.catalog_service_url}/products/categories/list"
    return await proxy_request("GET", url, request)


# ============== Cart ==============

@router.post("/api/carts")
async def create_cart(request: Request):
    """Create a new cart."""
    body = await request.json()
    url = f"{settings.cart_service_url}/carts"
    return await proxy_request("POST", url, request, body)


@router.get("/api/carts/{cart_id}")
async def get_cart(cart_id: str, request: Request):
    """Get a cart by ID."""
    url = f"{settings.cart_service_url}/carts/{cart_id}"
    return await proxy_request("GET", url, request)


@router.get("/api/carts/user/{user_id}")
async def get_cart_by_user(user_id: str, request: Request):
    """Get a cart by user ID."""
    url = f"{settings.cart_service_url}/carts/user/{user_id}"
    return await proxy_request("GET", url, request)


@router.post("/api/carts/{cart_id}/items")
async def add_to_cart(cart_id: str, request: Request):
    """Add item to cart."""
    body = await request.json()
    url = f"{settings.cart_service_url}/carts/{cart_id}/items"
    return await proxy_request("POST", url, request, body)


@router.put("/api/carts/{cart_id}/items/{item_id}")
async def update_cart_item(cart_id: str, item_id: str, request: Request):
    """Update cart item."""
    body = await request.json()
    url = f"{settings.cart_service_url}/carts/{cart_id}/items/{item_id}"
    return await proxy_request("PUT", url, request, body)


@router.delete("/api/carts/{cart_id}/items/{item_id}")
async def remove_cart_item(cart_id: str, item_id: str, request: Request):
    """Remove item from cart."""
    url = f"{settings.cart_service_url}/carts/{cart_id}/items/{item_id}"
    return await proxy_request("DELETE", url, request)


@router.delete("/api/carts/{cart_id}")
async def clear_cart(cart_id: str, request: Request):
    """Clear cart."""
    url = f"{settings.cart_service_url}/carts/{cart_id}"
    return await proxy_request("DELETE", url, request)


# ============== Orders ==============

@router.post("/api/orders")
async def create_order(request: Request):
    """Create a new order."""
    body = await request.json()

    # Get communication mode from body
    comm_mode = body.get("communication_mode", "sync")

    url = f"{settings.order_service_url}/orders"
    return await proxy_request("POST", url, request, body, communication_mode=comm_mode)


@router.get("/api/orders")
async def list_orders(
    request: Request,
    user_id: Optional[str] = None,
    status: Optional[str] = None
):
    """List orders."""
    url = f"{settings.order_service_url}/orders"
    return await proxy_request("GET", url, request)


@router.get("/api/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    """Get an order by ID."""
    url = f"{settings.order_service_url}/orders/{order_id}"
    return await proxy_request("GET", url, request)


@router.get("/api/orders/{order_id}/saga")
async def get_order_saga(order_id: str, request: Request):
    """Get order saga state."""
    url = f"{settings.order_service_url}/orders/{order_id}/saga"
    return await proxy_request("GET", url, request)


@router.post("/api/orders/{order_id}/cancel")
async def cancel_order(order_id: str, request: Request):
    """Cancel an order."""
    url = f"{settings.order_service_url}/orders/{order_id}/cancel"
    return await proxy_request("POST", url, request, {})


# ============== Inventory ==============

@router.get("/api/inventory")
async def list_inventory(request: Request):
    """List all inventory."""
    url = f"{settings.inventory_service_url}/inventory"
    return await proxy_request("GET", url, request)


@router.get("/api/inventory/{product_id}")
async def get_inventory(product_id: str, request: Request):
    """Get inventory for a product."""
    url = f"{settings.inventory_service_url}/inventory/{product_id}"
    return await proxy_request("GET", url, request)


# ============== Payments ==============

@router.get("/api/payments/{payment_id}")
async def get_payment(payment_id: str, request: Request):
    """Get a payment by ID."""
    url = f"{settings.payment_service_url}/payments/{payment_id}"
    return await proxy_request("GET", url, request)


@router.get("/api/payments/order/{order_id}")
async def get_payment_by_order(order_id: str, request: Request):
    """Get payment for an order."""
    url = f"{settings.payment_service_url}/payments/order/{order_id}"
    return await proxy_request("GET", url, request)
