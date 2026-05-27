
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px

REAL_LOG = Path("logs/tank_log_norm.jsonl")
SYNTH_LOG = Path("logs/telemetry_10s.jsonl")

st.set_page_config(
    page_title="ESP32 SCADA Dashboard",
    layout="wide",
)

st.title("ESP32 SCADA Telemetry Dashboard")
st.caption("Real ESP32 telemetry vs synthetic AI training dataset")


def load_jsonl(path: Path):
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_json(path, lines=True)

    if "event_type" in df.columns:
        df = df[df["event_type"] == "telemetry"].copy()

    if "ts" in df.columns:
        df["time"] = pd.to_datetime(df["ts"], errors="coerce")
    elif "timestamp" in df.columns:
        df["time"] = pd.to_datetime(df["timestamp"], errors="coerce")
    else:
        df["time"] = range(len(df))

    return df


real = load_jsonl(REAL_LOG)
synthetic = load_jsonl(SYNTH_LOG)

col1, col2, col3 = st.columns(3)

if not real.empty:
    latest = real.iloc[-1]
    col1.metric("Latest real level", f"{latest.get('level_pct', 0):.1f}%")
    col2.metric("Latest real temp", f"{latest.get('temp_c', 0):.1f} °C")
    col3.metric("AI status", latest.get("ai_status", "N/A"))
else:
    col1.metric("Latest real level", "N/A")
    col2.metric("Latest real temp", "N/A")
    col3.metric("AI status", "N/A")

st.divider()

tab1, tab2, tab3 = st.tabs(["Real telemetry", "Synthetic dataset", "Comparison"])

with tab1:
    st.subheader("Real ESP32 telemetry")

    if real.empty:
        st.warning("No real telemetry log found.")
    else:
        fig_level = px.line(
            real.tail(500),
            x="time",
            y="level_pct",
            title="Real Tank Level Over Time",
        )
        st.plotly_chart(fig_level, use_container_width=True)

        fig_temp = px.line(
            real.tail(500),
            x="time",
            y="temp_c",
            title="Real Temperature Over Time",
        )
        st.plotly_chart(fig_temp, use_container_width=True)

        st.dataframe(real.tail(20), use_container_width=True)

with tab2:
    st.subheader("Synthetic training dataset")

    if synthetic.empty:
        st.warning("No synthetic dataset found.")
    else:
        fig_level_s = px.line(
            synthetic.tail(1000),
            x="time",
            y="level_pct",
            title="Synthetic Tank Level Over Time",
        )
        st.plotly_chart(fig_level_s, use_container_width=True)

        fig_temp_s = px.line(
            synthetic.tail(1000),
            x="time",
            y="temp_c",
            title="Synthetic Temperature Over Time",
        )
        st.plotly_chart(fig_temp_s, use_container_width=True)

        if "is_anomaly" in synthetic.columns:
            anomaly_count = int(synthetic["is_anomaly"].sum())
            st.info(f"Synthetic anomalies included: {anomaly_count}")

        st.dataframe(synthetic.tail(20), use_container_width=True)

with tab3:
    st.subheader("Real vs synthetic comparison")

    if real.empty or synthetic.empty:
        st.warning("Both real and synthetic logs are required.")
    else:
        real_cmp = real.tail(300).copy()
        real_cmp["source"] = "Real ESP32"

        synth_cmp = synthetic.tail(300).copy()
        synth_cmp["source"] = "Synthetic"

        compare = pd.concat([real_cmp, synth_cmp], ignore_index=True)

        fig_cmp_level = px.line(
            compare,
            x="time",
            y="level_pct",
            color="source",
            title="Tank Level: Real vs Synthetic",
        )
        st.plotly_chart(fig_cmp_level, use_container_width=True)

        fig_cmp_temp = px.line(
            compare,
            x="time",
            y="temp_c",
            color="source",
            title="Temperature: Real vs Synthetic",
        )
        st.plotly_chart(fig_cmp_temp, use_container_width=True)