"""Performance page - Compare sync vs async metrics."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import httpx
import time
from datetime import datetime
import sys
sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 2)[0])
from theme import apply_theme_css, render_theme_toggle, init_theme, get_plotly_theme, get_plotly_layout_updates

st.set_page_config(page_title="Performance", page_icon="bar_chart", layout="wide")

# Initialize theme and apply CSS
init_theme()
apply_theme_css()

st.title("Performance Comparison")

st.markdown("""
Compare the performance characteristics of **synchronous** vs **asynchronous**
communication patterns.
""")

# Configuration
PROMETHEUS_URL = "http://prometheus:9090"
GRAFANA_URL = "http://localhost:3000"
JAEGER_URL = "http://localhost:16686"


def query_prometheus(query: str) -> dict:
    """Query Prometheus for metrics."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": query}
            )
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


def query_prometheus_range(query: str, start: str, end: str, step: str = "15s") -> dict:
    """Query Prometheus for range metrics."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{PROMETHEUS_URL}/api/v1/query_range",
                params={
                    "query": query,
                    "start": start,
                    "end": end,
                    "step": step
                }
            )
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# Tabs for different views
tab1, tab2, tab3 = st.tabs(["Overview", "Detailed Metrics", "External Dashboards"])

with tab1:
    st.header("Quick Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sync Mode")

        # Query sync metrics
        sync_throughput = query_prometheus(
            'sum(rate(http_requests_total{communication_mode="sync"}[5m]))'
        )
        sync_latency = query_prometheus(
            'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{communication_mode="sync"}[5m])) by (le)) * 1000'
        )
        sync_errors = query_prometheus(
            'sum(rate(http_requests_total{communication_mode="sync", status=~"5.."}[5m])) / sum(rate(http_requests_total{communication_mode="sync"}[5m])) * 100'
        )

        if sync_throughput.get("status") == "success" and sync_throughput.get("data", {}).get("result"):
            value = float(sync_throughput["data"]["result"][0]["value"][1])
            st.metric("Throughput", f"{value:.2f} req/s")
        else:
            st.metric("Throughput", "N/A")

        if sync_latency.get("status") == "success" and sync_latency.get("data", {}).get("result"):
            value = float(sync_latency["data"]["result"][0]["value"][1])
            st.metric("P95 Latency", f"{value:.2f} ms")
        else:
            st.metric("P95 Latency", "N/A")

        if sync_errors.get("status") == "success" and sync_errors.get("data", {}).get("result"):
            value = float(sync_errors["data"]["result"][0]["value"][1])
            st.metric("Error Rate", f"{value:.2f}%")
        else:
            st.metric("Error Rate", "N/A")

    with col2:
        st.subheader("Async Mode")

        # Query async metrics
        async_throughput = query_prometheus(
            'sum(rate(http_requests_total{communication_mode="async"}[5m]))'
        )
        async_latency = query_prometheus(
            'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{communication_mode="async"}[5m])) by (le)) * 1000'
        )
        async_errors = query_prometheus(
            'sum(rate(http_requests_total{communication_mode="async", status=~"5.."}[5m])) / sum(rate(http_requests_total{communication_mode="async"}[5m])) * 100'
        )

        if async_throughput.get("status") == "success" and async_throughput.get("data", {}).get("result"):
            value = float(async_throughput["data"]["result"][0]["value"][1])
            st.metric("Throughput", f"{value:.2f} req/s")
        else:
            st.metric("Throughput", "N/A")

        if async_latency.get("status") == "success" and async_latency.get("data", {}).get("result"):
            value = float(async_latency["data"]["result"][0]["value"][1])
            st.metric("P95 Latency", f"{value:.2f} ms")
        else:
            st.metric("P95 Latency", "N/A")

        if async_errors.get("status") == "success" and async_errors.get("data", {}).get("result"):
            value = float(async_errors["data"]["result"][0]["value"][1])
            st.metric("Error Rate", f"{value:.2f}%")
        else:
            st.metric("Error Rate", "N/A")

    # Message Queue Metrics
    st.markdown("---")
    st.header("Message Queue (RabbitMQ)")

    col1, col2, col3 = st.columns(3)

    with col1:
        published = query_prometheus('sum(rate(rabbitmq_messages_published_total[5m]))')
        if published.get("status") == "success" and published.get("data", {}).get("result"):
            value = float(published["data"]["result"][0]["value"][1])
            st.metric("Messages Published", f"{value:.2f}/s")
        else:
            st.metric("Messages Published", "N/A")

    with col2:
        consumed = query_prometheus('sum(rate(rabbitmq_messages_consumed_total[5m]))')
        if consumed.get("status") == "success" and consumed.get("data", {}).get("result"):
            value = float(consumed["data"]["result"][0]["value"][1])
            st.metric("Messages Consumed", f"{value:.2f}/s")
        else:
            st.metric("Messages Consumed", "N/A")

    with col3:
        dlq = query_prometheus('sum(rate(rabbitmq_messages_dlq_total[5m]))')
        if dlq.get("status") == "success" and dlq.get("data", {}).get("result"):
            value = float(dlq["data"]["result"][0]["value"][1])
            st.metric("DLQ Messages", f"{value:.2f}/s")
        else:
            st.metric("DLQ Messages", "N/A")

with tab2:
    st.header("Detailed Metrics")

    # Per-service metrics
    st.subheader("Service Metrics")

    services = [
        "api-gateway",
        "catalog-service",
        "cart-service",
        "order-service",
        "payment-service",
        "inventory-service"
    ]

    data = []
    for service in services:
        throughput = query_prometheus(f'sum(rate(http_requests_total{{service="{service}"}}[5m]))')
        latency = query_prometheus(
            f'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m])) by (le)) * 1000'
        )

        throughput_val = "N/A"
        latency_val = "N/A"

        if throughput.get("status") == "success" and throughput.get("data", {}).get("result"):
            throughput_val = f"{float(throughput['data']['result'][0]['value'][1]):.2f}"

        if latency.get("status") == "success" and latency.get("data", {}).get("result"):
            latency_val = f"{float(latency['data']['result'][0]['value'][1]):.2f}"

        data.append({
            "Service": service,
            "Throughput (req/s)": throughput_val,
            "P95 Latency (ms)": latency_val
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)

    # Latency percentiles
    st.subheader("Latency Percentiles")

    percentiles = ["0.50", "0.90", "0.95", "0.99"]
    latency_data = {"Percentile": [], "Sync (ms)": [], "Async (ms)": []}

    for p in percentiles:
        sync_p = query_prometheus(
            f'histogram_quantile({p}, sum(rate(http_request_duration_seconds_bucket{{communication_mode="sync"}}[5m])) by (le)) * 1000'
        )
        async_p = query_prometheus(
            f'histogram_quantile({p}, sum(rate(http_request_duration_seconds_bucket{{communication_mode="async"}}[5m])) by (le)) * 1000'
        )

        latency_data["Percentile"].append(f"P{int(float(p)*100)}")

        if sync_p.get("status") == "success" and sync_p.get("data", {}).get("result"):
            latency_data["Sync (ms)"].append(float(sync_p["data"]["result"][0]["value"][1]))
        else:
            latency_data["Sync (ms)"].append(None)

        if async_p.get("status") == "success" and async_p.get("data", {}).get("result"):
            latency_data["Async (ms)"].append(float(async_p["data"]["result"][0]["value"][1]))
        else:
            latency_data["Async (ms)"].append(None)

    latency_df = pd.DataFrame(latency_data)
    st.dataframe(latency_df, use_container_width=True)

    # Bar chart comparison
    if latency_df["Sync (ms)"].notna().any() or latency_df["Async (ms)"].notna().any():
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Sync',
            x=latency_df['Percentile'],
            y=latency_df['Sync (ms)']
        ))
        fig.add_trace(go.Bar(
            name='Async',
            x=latency_df['Percentile'],
            y=latency_df['Async (ms)']
        ))

        # Apply theme to chart
        layout_updates = get_plotly_layout_updates()
        fig.update_layout(
            title="Latency Comparison by Percentile",
            barmode='group',
            yaxis_title="Latency (ms)",
            xaxis_title="Percentile",
            **layout_updates
        )
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("External Dashboards")

    st.markdown("""
    Access the full monitoring dashboards for detailed analysis:
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"""
        ### Grafana
        Comprehensive metrics visualization with pre-configured dashboards.

        [Open Grafana]({GRAFANA_URL})

        **Credentials:** admin / admin
        """)

    with col2:
        st.markdown(f"""
        ### Prometheus
        Direct access to metrics queries and exploration.

        [Open Prometheus]({PROMETHEUS_URL})
        """)

    with col3:
        st.markdown(f"""
        ### Jaeger
        Distributed tracing for request flow analysis.

        [Open Jaeger]({JAEGER_URL})
        """)

    st.markdown("---")
    st.markdown("""
    ### Useful Grafana Dashboard Queries

    **Sync vs Async Throughput:**
    ```promql
    sum(rate(http_requests_total{communication_mode="sync"}[1m]))
    sum(rate(http_requests_total{communication_mode="async"}[1m]))
    ```

    **Latency Comparison:**
    ```promql
    histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{communication_mode="sync"}[5m])) by (le))
    histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{communication_mode="async"}[5m])) by (le))
    ```

    **Error Rates:**
    ```promql
    sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
    ```
    """)

# Auto-refresh
st.sidebar.markdown("---")
if st.sidebar.checkbox("Auto-refresh (10s)"):
    time.sleep(10)
    st.rerun()

# Theme toggle at the bottom of sidebar
render_theme_toggle()
