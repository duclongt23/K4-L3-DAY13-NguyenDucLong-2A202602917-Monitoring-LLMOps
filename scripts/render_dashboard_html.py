from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

LOG_PATH = Path("data/logs.jsonl")
OUTPUT_HTML = Path("data/dashboard.html")
OUTPUT_PNG = Path("submission/evidence/05-dashboard-incident.png")

def main():
    if not LOG_PATH.exists():
        print("data/logs.jsonl not found")
        return

    records = []
    with LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    df = pd.DataFrame(records)
    if "ts" in df.columns:
        df["ts_dt"] = pd.to_datetime(df["ts"], utc=True)

    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            "1. Latency Percentiles & TTFT (ms)",
            "2. Traffic (req/min)",
            "3. Error Rate & Tool Success (%)",
            "4. Cost (USD)",
            "5. Input & Output Tokens",
            "6. Quality Score (0-1)"
        )
    )

    # Panel 1: Latency
    sent_df = df[df["event"] == "response_sent"].copy() if not df.empty and "event" in df.columns else pd.DataFrame()
    if not sent_df.empty and "latency_ms" in sent_df.columns:
        p50 = sent_df["latency_ms"].quantile(0.50)
        p95 = sent_df["latency_ms"].quantile(0.95)
        p99 = sent_df["latency_ms"].quantile(0.99)
        ttft_p95 = sent_df["ttft_ms"].quantile(0.95) if "ttft_ms" in sent_df.columns else 0
        fig.add_trace(go.Bar(x=["P50", "P95", "P99", "TTFT_P95"], y=[p50, p95, p99, ttft_p95], name="Latency ms"), row=1, col=1)
        fig.add_hline(y=3000, line_dash="dash", line_color="red", row=1, col=1)

    # Panel 2: Traffic
    rec_df = df[df["event"] == "request_received"].copy() if not df.empty and "event" in df.columns else pd.DataFrame()
    if not rec_df.empty:
        rec_df["minute"] = rec_df["ts_dt"].dt.floor("1min")
        traffic = rec_df.groupby("minute").size().reset_index(name="requests")
        fig.add_trace(go.Scatter(x=traffic["minute"], y=traffic["requests"], mode="lines+markers", name="Traffic"), row=1, col=2)
        fig.add_hline(y=1, line_dash="dash", line_color="green", row=1, col=2)

    # Panel 3: Errors
    total_req = len(rec_df)
    failed_req = len(df[df["event"] == "request_failed"]) if not df.empty and "event" in df.columns else 0
    err_rate = (failed_req / total_req * 100) if total_req > 0 else 0
    tool_df = df[df["tool_success"].notna()] if not df.empty and "tool_success" in df.columns else pd.DataFrame()
    tool_succ = (len(tool_df[tool_df["tool_success"] == True]) / len(tool_df) * 100) if len(tool_df) > 0 else 100
    fig.add_trace(go.Bar(x=["Error Rate %", "Tool Success %"], y=[err_rate, tool_succ], name="Errors/Success %"), row=1, col=3)
    fig.add_hline(y=2, line_dash="dash", line_color="red", row=1, col=3)

    # Panel 4: Cost
    if not sent_df.empty and "cost_usd" in sent_df.columns:
        sent_df["minute"] = sent_df["ts_dt"].dt.floor("1min")
        cost_time = sent_df.groupby("minute")["cost_usd"].sum().reset_index()
        fig.add_trace(go.Scatter(x=cost_time["minute"], y=cost_time["cost_usd"], mode="lines+markers", name="Cost USD"), row=2, col=1)
        fig.add_hline(y=2.5, line_dash="dash", line_color="red", row=2, col=1)

    # Panel 5: Tokens
    if not sent_df.empty and "tokens_in" in sent_df.columns:
        total_in = sent_df["tokens_in"].sum()
        total_out = sent_df["tokens_out"].sum()
        fig.add_trace(go.Bar(x=["Tokens In", "Tokens Out"], y=[total_in, total_out], name="Tokens"), row=2, col=2)
        fig.add_hline(y=50000, line_dash="dash", line_color="red", row=2, col=2)

    # Panel 6: Quality
    if not sent_df.empty and "quality_score" in sent_df.columns:
        avg_q = sent_df["quality_score"].mean()
        fig.add_trace(go.Bar(x=["Avg Quality Score"], y=[avg_q], name="Quality"), row=2, col=3)
        fig.add_hline(y=0.75, line_dash="dash", line_color="green", row=2, col=3)

    fig.update_layout(height=800, width=1400, title_text="K4-L3B Day 13 Monitoring Dashboard", showlegend=False)
    fig.write_html(str(OUTPUT_HTML))
    print(f"Dashboard saved to {OUTPUT_HTML}")

if __name__ == "__main__":
    main()
