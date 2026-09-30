from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as px_go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Streamlit Page Config
st.set_page_config(
    page_title="LLMOps Monitoring Dashboard",
    page_icon="📊",
    layout="wide",
)

# Auto-refresh every 30 seconds
st_autorefresh(interval=30000, limit=100, key="dashboard_autorefresh")

st.title("📊 K4-L3B Day 13 LLMOps & Monitoring Dashboard")
st.caption("Real-time telemetry and metrics from data/logs.jsonl (Last 60 Minutes)")

LOG_PATH = Path("data/logs.jsonl")


def load_logs() -> pd.DataFrame:
    if not LOG_PATH.exists():
        return pd.DataFrame()

    records = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    if "ts" in df.columns:
        df["ts_dt"] = pd.to_datetime(df["ts"], utc=True)
        # Filter last 60 minutes
        cutoff = datetime.now(timezone.utc) - pd.Timedelta(minutes=60)
        df = df[df["ts_dt"] >= cutoff].copy()
    return df


df = load_logs()

if df.empty:
    st.warning("Chưa có dữ liệu log trong data/logs.jsonl hoặc trong 60 phút qua. Hãy chạy `python scripts/load_test.py` để phát sinh dữ liệu.")
    st.stop()

# Prepare grid layout (2 rows x 3 columns)
col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

# ---------------------------------------------------------
# Panel 1: Latency Percentiles & TTFT
# ---------------------------------------------------------
with col1:
    st.subheader("1. Latency & TTFT (ms)")
    sent_df = df[df["event"] == "response_sent"].copy()
    if not sent_df.empty and "latency_ms" in sent_df.columns:
        p50 = sent_df["latency_ms"].quantile(0.50)
        p95 = sent_df["latency_ms"].quantile(0.95)
        p99 = sent_df["latency_ms"].quantile(0.99)
        ttft_p95 = sent_df["ttft_ms"].quantile(0.95) if "ttft_ms" in sent_df.columns else 0

        fig = px.bar(
            x=["P50 Latency", "P95 Latency", "P99 Latency", "TTFT P95"],
            y=[p50, p95, p99, ttft_p95],
            labels={"x": "Percentile / Metric", "y": "ms"},
            color_discrete_sequence=["#636EFA"],
            title=f"P95 Latency: {p95:.1f}ms (Threshold: 3000ms)"
        )
        fig.add_hline(y=3000, line_dash="dash", line_color="red", annotation_text="Threshold (3000ms)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có event response_sent")

# ---------------------------------------------------------
# Panel 2: Request Traffic
# ---------------------------------------------------------
with col2:
    st.subheader("2. Traffic (Requests / Min)")
    rec_df = df[df["event"] == "request_received"].copy()
    if not rec_df.empty:
        rec_df["minute"] = rec_df["ts_dt"].dt.floor("1min")
        traffic = rec_df.groupby("minute").size().reset_index(name="requests")

        fig = px.line(
            traffic,
            x="minute",
            y="requests",
            markers=True,
            title=f"Total Traffic: {len(rec_df)} requests",
            labels={"minute": "Time", "requests": "req/min"}
        )
        fig.add_hline(y=1, line_dash="dash", line_color="green", annotation_text="Min Threshold (1 req/min)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có event request_received")

# ---------------------------------------------------------
# Panel 3: Errors & Retrieval Success
# ---------------------------------------------------------
with col3:
    st.subheader("3. Error Rate & Tool Success (%)")
    total_req = len(df[df["event"] == "request_received"])
    failed_req = len(df[df["event"] == "request_failed"])
    error_rate = (failed_req / total_req * 100) if total_req > 0 else 0

    tool_df = df[df["tool_success"].notna()]
    tool_success = (len(tool_df[tool_df["tool_success"] == True]) / len(tool_df) * 100) if len(tool_df) > 0 else 100

    fig = px.bar(
        x=["Error Rate %", "Tool Success %"],
        y=[error_rate, tool_success],
        labels={"x": "Metric", "y": "%"},
        color_discrete_sequence=["#EF553B"],
        title=f"Error Rate: {error_rate:.1f}% (Threshold: <= 2%)"
    )
    fig.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="Error Max (2%)")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------
# Panel 4: Cost Over Time (USD)
# ---------------------------------------------------------
with col4:
    st.subheader("4. Cost (USD)")
    sent_df = df[df["event"] == "response_sent"].copy()
    if not sent_df.empty and "cost_usd" in sent_df.columns:
        total_cost = sent_df["cost_usd"].sum()
        sent_df["minute"] = sent_df["ts_dt"].dt.floor("1min")
        cost_time = sent_df.groupby("minute")["cost_usd"].sum().reset_index()

        fig = px.line(
            cost_time,
            x="minute",
            y="cost_usd",
            markers=True,
            title=f"Total Cost: ${total_cost:.4f} (Threshold: <= $2.5)"
        )
        fig.add_hline(y=2.5, line_dash="dash", line_color="red", annotation_text="Cost Max ($2.5)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu chi phí")

# ---------------------------------------------------------
# Panel 5: Input & Output Tokens
# ---------------------------------------------------------
with col5:
    st.subheader("5. Token Usage")
    sent_df = df[df["event"] == "response_sent"].copy()
    if not sent_df.empty and "tokens_in" in sent_df.columns:
        total_in = sent_df["tokens_in"].sum()
        total_out = sent_df["tokens_out"].sum()

        fig = px.bar(
            x=["Tokens In", "Tokens Out"],
            y=[total_in, total_out],
            labels={"x": "Type", "y": "Count"},
            color_discrete_sequence=["#00CC96"],
            title=f"Total Tokens: {total_in + total_out:,} (Threshold: <= 50,000)"
        )
        fig.add_hline(y=50000, line_dash="dash", line_color="red", annotation_text="Token Max (50,000)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu Token")

# ---------------------------------------------------------
# Panel 6: Quality Proxy
# ---------------------------------------------------------
with col6:
    st.subheader("6. Quality Score (0 - 1)")
    sent_df = df[df["event"] == "response_sent"].copy()
    if not sent_df.empty and "quality_score" in sent_df.columns:
        avg_quality = sent_df["quality_score"].mean()

        fig = px.bar(
            x=["Avg Quality Score"],
            y=[avg_quality],
            labels={"x": "Metric", "y": "Score"},
            color_discrete_sequence=["#AB63FA"],
            title=f"Avg Score: {avg_quality:.2f} (Threshold: >= 0.75)"
        )
        fig.add_hline(y=0.75, line_dash="dash", line_color="green", annotation_text="Quality Min (0.75)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu Quality")
