"""E-commerce Comparison UI - Main application."""

import streamlit as st
from uuid import uuid4
from theme import apply_theme_css, render_theme_toggle, init_theme

st.set_page_config(
    page_title="E-commerce Comparison",
    page_icon="cart",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize theme and apply CSS
init_theme()
apply_theme_css()

# Initialize session state
if "user_id" not in st.session_state:
    st.session_state.user_id = f"user-{uuid4().hex[:8]}"
if "cart_id" not in st.session_state:
    st.session_state.cart_id = None
if "cart" not in st.session_state:
    st.session_state.cart = None

st.title("E-commerce Sync vs Async Comparison")

st.markdown("""
Welcome to the E-commerce Comparison Demo!

This application demonstrates the differences between **synchronous** and **asynchronous**
communication patterns in a microservices architecture.

## Features

- **Shop**: Browse products, add to cart, and checkout
- **Performance**: Compare sync vs async performance metrics

## Navigation

Use the sidebar to navigate between pages:

1. **Shop** - Browse and purchase products
2. **Performance** - View performance metrics and comparison

## Architecture

This demo consists of the following services:

| Service | Description |
|---------|-------------|
| API Gateway | Entry point for all requests |
| Catalog Service | Product management |
| Cart Service | Shopping cart |
| Order Service | Order processing (sync/async) |
| Payment Service | Payment processing |
| Inventory Service | Stock management |

## Communication Modes

- **Sync Mode**: Direct HTTP calls between services
- **Async Mode**: Event-driven with RabbitMQ message queue

""")

# Show current user and cart status
st.sidebar.markdown("---")
st.sidebar.markdown(f"**User ID:** `{st.session_state.user_id}`")
if st.session_state.cart_id:
    st.sidebar.markdown(f"**Cart ID:** `{st.session_state.cart_id[:8]}...`")

# Health check
st.sidebar.markdown("---")
st.sidebar.markdown("### System Status")

try:
    from utils import health_check
    health = health_check()
    if health.get("status") == "healthy":
        st.sidebar.success(f"API Gateway: Healthy")
        mode = health.get("communication_mode", "unknown")
        st.sidebar.info(f"Mode: {mode.upper()}")
    else:
        st.sidebar.error("API Gateway: Unhealthy")
except Exception as e:
    st.sidebar.error(f"API Gateway: Offline")
    st.sidebar.caption(str(e))

# Theme toggle at the bottom of sidebar
render_theme_toggle()
