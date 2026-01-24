"""Shop page - Browse products and checkout."""

import streamlit as st
from uuid import uuid4
import time

st.set_page_config(page_title="Shop", page_icon="🛍️", layout="wide")

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = f"user-{uuid4().hex[:8]}"
if "cart_id" not in st.session_state:
    st.session_state.cart_id = None
if "cart" not in st.session_state:
    st.session_state.cart = None
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None

st.title("🛍️ Shop")

try:
    from utils import (
        list_products, get_cart_by_user, create_cart, get_cart,
        add_to_cart, remove_cart_item, update_cart_item, create_order,
        list_orders, get_order_saga
    )

    # Callback functions for cart actions
    def delete_item(cart_id: str, item_id: str):
        """Delete item from cart."""
        try:
            updated_cart = remove_cart_item(cart_id, item_id)
            st.session_state.cart = updated_cart
            st.session_state.confirm_delete = None
        except Exception as e:
            st.error(f"Failed to remove item: {e}")

    def ask_delete(item_id: str, item_name: str):
        """Set item to confirm deletion."""
        st.session_state.confirm_delete = {"id": item_id, "name": item_name}

    def cancel_delete():
        """Cancel deletion."""
        st.session_state.confirm_delete = None

    def update_quantity(cart_id: str, item_id: str, new_quantity: int):
        """Update item quantity in cart."""
        try:
            if new_quantity <= 0:
                updated_cart = remove_cart_item(cart_id, item_id)
            else:
                updated_cart = update_cart_item(cart_id, item_id, new_quantity)
            st.session_state.cart = updated_cart
        except Exception as e:
            st.error(f"Failed to update quantity: {e}")

    # Ensure user has a cart
    def ensure_cart():
        if st.session_state.cart_id is None:
            cart = get_cart_by_user(st.session_state.user_id)
            if cart:
                st.session_state.cart_id = cart["id"]
                st.session_state.cart = cart
            else:
                cart = create_cart(st.session_state.user_id)
                st.session_state.cart_id = cart["id"]
                st.session_state.cart = cart

    ensure_cart()

    # Layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("Products")

        # Load products
        try:
            products_data = list_products(page_size=50)
            products = products_data.get("items", [])
        except Exception as e:
            st.error(f"Failed to load products: {e}")
            products = []

        if products:
            # Display products in a grid
            cols = st.columns(3)
            for i, product in enumerate(products):
                with cols[i % 3]:
                    # Product image
                    image_url = product.get('image_url')
                    if image_url:
                        st.image(image_url, use_column_width=True)

                    st.markdown(f"### {product['name']}")
                    st.markdown(f"**${float(product['price']):.2f}**")
                    st.caption(product.get('description', '')[:100])
                    st.caption(f"Category: {product.get('category', 'N/A')}")

                    if st.button(f"🛒 Add to Cart", key=f"add_{product['id']}"):
                        try:
                            cart = add_to_cart(
                                st.session_state.cart_id,
                                product['id']
                            )
                            st.session_state.cart = cart
                            st.success(f"Added {product['name']}!")
                            time.sleep(0.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to add to cart: {e}")

                    st.markdown("---")
        else:
            st.info("No products available. Please check if the catalog service is running.")

    with col2:
        st.header("🛒 Cart")

        # Confirmation modal for delete
        if st.session_state.confirm_delete:
            item_to_delete = st.session_state.confirm_delete
            st.warning(f"🗑️ Remove **{item_to_delete['name']}**?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Yes", key="confirm_yes", type="primary",
                             on_click=delete_item,
                             args=(st.session_state.cart_id, item_to_delete['id'])):
                    pass
            with col_no:
                if st.button("❌ No", key="confirm_no",
                             on_click=cancel_delete):
                    pass
            st.markdown("---")

        # Refresh cart button
        if st.button("🔄 Refresh Cart"):
            try:
                cart = get_cart(st.session_state.cart_id)
                if cart:
                    st.session_state.cart = cart
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to refresh cart: {e}")

        cart = st.session_state.cart
        if cart and cart.get("items"):
            for item in cart["items"]:
                item_name = item.get('product_name', item['product_id'][:8] + "...")
                st.markdown(f"**{item_name}**")
                st.markdown(f"${float(item['price']):.2f} each")

                # Quantity controls
                col_minus, col_qty, col_plus, col_del = st.columns([1, 1, 1, 1])

                with col_minus:
                    if st.button("➖", key=f"minus_{item['id']}",
                                 on_click=update_quantity,
                                 args=(st.session_state.cart_id, item['id'], item['quantity'] - 1)):
                        pass

                with col_qty:
                    st.markdown(f"<h3 style='text-align: center;'>{item['quantity']}</h3>", unsafe_allow_html=True)

                with col_plus:
                    if st.button("➕", key=f"plus_{item['id']}",
                                 on_click=update_quantity,
                                 args=(st.session_state.cart_id, item['id'], item['quantity'] + 1)):
                        pass

                with col_del:
                    if st.button("🗑️", key=f"remove_{item['id']}",
                                 on_click=ask_delete,
                                 args=(item['id'], item_name)):
                        pass

                subtotal = float(item['price']) * item['quantity']
                st.markdown(f"Subtotal: **${subtotal:.2f}**")
                st.markdown("---")

            st.markdown(f"## Total: ${float(cart.get('total', 0)):.2f}")

            # Checkout options
            st.markdown("### Checkout")

            mode = st.radio(
                "Communication Mode:",
                ["sync", "async"],
                horizontal=True,
                help="Sync: Direct HTTP calls. Async: Event-driven with message queue."
            )

            if st.button("🛒 Place Order", type="primary"):
                with st.spinner(f"Processing order ({mode} mode)..."):
                    start_time = time.time()
                    try:
                        order = create_order(
                            st.session_state.user_id,
                            st.session_state.cart_id,
                            mode
                        )
                        duration = time.time() - start_time

                        st.success(f"Order created! ID: {order['id'][:8]}...")
                        st.info(f"Status: {order['status']}")
                        st.metric("Processing Time", f"{duration:.2f}s")

                        # Clear cart from session
                        st.session_state.cart = None
                        st.session_state.cart_id = None

                        # Show saga status for async
                        if mode == "async" and order['status'] not in ['completed', 'failed']:
                            st.info("Order is being processed asynchronously. Check 'My Orders' for status.")

                    except Exception as e:
                        st.error(f"Order failed: {e}")

        else:
            st.info("Your cart is empty. Add some products!")

    # Orders section
    st.markdown("---")
    st.header("📦 My Orders")

    if st.button("🔄 Refresh Orders"):
        st.rerun()

    try:
        orders = list_orders(st.session_state.user_id)
        if orders:
            for order in orders[:10]:  # Show last 10 orders
                status_color = {
                    'completed': '🟢',
                    'failed': '🔴',
                    'pending': '🟡',
                    'payment_pending': '🟡',
                    'payment_failed': '🔴',
                    'stock_pending': '🟡',
                    'stock_failed': '🔴'
                }.get(order['status'], '⚪')

                with st.expander(f"{status_color} Order {order['id'][:8]}... - {order['status'].upper()}"):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.metric("Total", f"${float(order['total_amount']):.2f}")
                    with col_b:
                        st.metric("Mode", order['communication_mode'].upper())
                    with col_c:
                        st.metric("Items", len(order.get('items', [])))

                    st.markdown(f"**Created:** {order['created_at']}")

                    # Show saga state for async orders
                    if order['communication_mode'] == 'async':
                        saga = get_order_saga(order['id'])
                        if saga:
                            st.markdown("**Saga State:**")
                            st.json({
                                "step": saga.get('current_step'),
                                "status": saga.get('status'),
                                "payment": saga.get('payment_status'),
                                "inventory": saga.get('inventory_status'),
                                "error": saga.get('error_message')
                            })
        else:
            st.info("No orders yet")
    except Exception as e:
        st.error(f"Failed to load orders: {e}")

except ImportError as e:
    st.error(f"Failed to import utils: {e}")
except Exception as e:
    st.error(f"An error occurred: {e}")
    st.exception(e)
