import os
import json
import io
import pandas as pd
import requests
import streamlit as st
import plotly.express as px
# import pyperclip  # optional; if missing we fallback

API_URL = os.getenv("KPI_COPILOT_API", "http://127.0.0.1:8080")

st.set_page_config(page_title="KPI Copilot", layout="wide")
st.markdown(
    """
    <style>
      /* Subtle polish */
      .stMetric { background: #fff; border: 1px solid #e5e7eb; border-radius: 14px; padding: 12px; }
      .small-muted { color: #6b7280; font-size: 12px; }
      .pill { display:inline-block; padding:4px 8px; border:1px solid #e5e7eb; border-radius:999px; font-size:12px; color:#374151; background:#fff; }
      .card { background:#fff; border:1px solid #e5e7eb; border-radius:16px; padding:16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("KPI Copilot")
st.caption("Ask KPIs in plain English. Get charts, insights, and SQL.")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("Controls")
    q = st.text_input("Question", "Compare revenue by region in 2024")

    col_s, col_e = st.columns(2)
    with col_s:
        start = st.date_input("Start", value=pd.to_datetime("2024-01-01")).strftime("%Y-%m-%d")
    with col_e:
        end = st.date_input("End", value=pd.to_datetime("2024-12-31")).strftime("%Y-%m-%d")

    group_by = st.selectbox("Group by (optional)", ["(none)", "region", "plan_tier"], index=1)
    dims = [] if group_by == "(none)" else [group_by]

    st.divider()
    st.subheader("Diagnostics")
    if st.button("Check /health"):
        try:
            r = requests.get(f"{API_URL}/health/", timeout=5)
            st.write(r.status_code, r.text)
        except Exception as e:
            st.error(f"Health check failed: {e}")

# ---------------- Ask ----------------
c1, c2 = st.columns([1, 6])
with c1:
    ask_clicked = st.button("Ask", use_container_width=True)
with c2:
    st.markdown(f"<span class='pill'>API: {API_URL}</span>", unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def call_api(question: str, start: str, end: str, dims: list):
    resp = requests.post(
        f"{API_URL}/ask-llm/",
        headers={"Content-Type": "application/json"},
        json={"question": question, "start": start, "end": end, "dims": dims},
        timeout=25,
    )
    ct = resp.headers.get("content-type", "")
    if "application/json" not in ct:
        raise RuntimeError(f"Non-JSON response ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    if resp.status_code >= 400:
        raise RuntimeError(data.get("detail") or data)
    return data

if ask_clicked:
    with st.spinner("Thinking…"):
        try:
            data = call_api(q, start, end, dims)
        except Exception as e:
            st.error(str(e))
            st.stop()

        # ------------ Insights + KPIs ------------
        series_df = pd.DataFrame(data["chart"]["series"])
        meta = data["chart"].get("meta", {})
        unit = meta.get("unit")
        title = meta.get("kpi", "Chart")

        # quick stats for current selection
        def _last_and_mom(df: pd.DataFrame):
            if df.empty:
                return None, None
            # If dimension exists, aggregate by period
            if "dimension" in df.columns and df["dimension"].notna().any():
                agg = df.groupby("period")["value"].sum().sort_index()
            else:
                agg = df.set_index("period")["value"].sort_index()
            if len(agg) == 0:
                return None, None
            last = float(agg.iloc[-1])
            if len(agg) >= 2 and agg.iloc[-2] != 0:
                mom = (agg.iloc[-1] - agg.iloc[-2]) / agg.iloc[-2] * 100.0
            else:
                mom = None
            return last, mom

        last_val, mom_pct = _last_and_mom(series_df)

        def fmt_val(v):
            if v is None:
                return "—"
            if unit == "USD":
                return f"${v:,.0f}"
            if unit == "percent":
                # handle 0–1 or 0–100
                p = v if abs(v) > 1 else v * 100
                return f"{p:.1f}%"
            return f"{v:,.0f}"

        st.subheader(title)
        m1, m2, m3 = st.columns(3)
        m1.metric("Last value", fmt_val(last_val))
        m2.metric("Avg MoM change", fmt_val(mom_pct) if mom_pct is not None else "—")
        peak = next((b for b in data.get("insights", []) if "Peak" in b or "**Peak**" in b), None)
        m3.metric("Peak", peak.replace("**", "") if peak else "—")

        # ------------ Chart ------------
        st.markdown("### Chart")
        if series_df.empty:
            st.info("No data returned for this query/time range.")
        else:
            if "dimension" in series_df.columns and series_df["dimension"].notna().any():
                fig = px.line(series_df, x="period", y="value", color="dimension")
            else:
                fig = px.line(series_df, x="period", y="value")
            fig.update_layout(
                height=460,
                margin=dict(l=20, r=20, t=10, b=10),
                legend=dict(orientation="h", y=-0.2),
                xaxis_title=None, yaxis_title=unit or "value",
            )
            if unit == "USD":
                fig.update_yaxes(tickprefix="$", separatethousands=True)
            elif unit == "percent":
                fig.update_yaxes(ticksuffix="%", tickformat=".1f")
            st.plotly_chart(fig, use_container_width=True)

        # ------------ Insights ------------
        if data.get("insights"):
            st.markdown("### Insights")
            with st.container():
                for b in data["insights"]:
                    st.markdown(f"- {b}")

        # ------------ SQL + actions ------------
        st.markdown("### SQL")
        sql_text = "\n\n".join(data.get("sql", [])) or "-- no SQL returned --"
        st.code(sql_text, language="sql")

        csql, cdl, craw = st.columns([1, 1, 1])