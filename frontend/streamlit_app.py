import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# ---- Config ----
API_URL = os.getenv("KPI_COPILOT_API", "http://127.0.0.1:8080")  # change if your API is on a different port

st.set_page_config(page_title="KPI Copilot", layout="wide")
st.title("KPI Copilot")

# ---- Inputs ----
col1, col2, col3 = st.columns([3, 2, 2])
with col1:
    q = st.text_input("Ask a question", "Compare revenue by region in 2024")
with col2:
    start = st.text_input("Start date (YYYY-MM-DD)", "2024-01-01")
with col3:
    end = st.text_input("End date (YYYY-MM-DD)", "2024-12-31")

# Optional dimension control
dim_options = ["(none)", "region"]  # extend later (e.g., plan_tier)
dim_choice = st.selectbox("Group by (optional)", dim_options, index=1)
dims = [] if dim_choice == "(none)" else [dim_choice]

# ---- Diagnostics ----
with st.expander("Diagnostics", expanded=False):
    if st.button("Check API /health"):
        try:
            r = requests.get(f"{API_URL}/health/", timeout=5)
            st.write("Health:", r.status_code, r.text)
        except Exception as e:
            st.error(f"Health check failed: {e}")

# ---- Ask ----
if st.button("Ask"):
    with st.spinner("Thinking..."):
        try:
            resp = requests.post(
                f"{API_URL}/ask",
                json={"question": q, "start": start, "end": end, "dims": dims},
                timeout=20,
            )
        except Exception as e:
            st.error(f"Request failed to reach API: {e}")
            st.stop()

        # Robust JSON handling
        if resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json()
            if resp.status_code >= 400:
                st.error(f"API error: {data.get('detail') or data}")
                st.stop()
        else:
            st.error(f"Non-JSON response from API (status {resp.status_code}): {resp.text[:300]}...")
            st.stop()

        st.subheader("Insights")
        for b in data.get("insights", []):
            st.markdown(f"- {b}")

        # Plot
        series = pd.DataFrame(data["chart"]["series"])
        if not series.empty:
            if "dimension" in series.columns and series["dimension"].notna().any():
                fig = px.line(series, x="period", y="value", color="dimension")
            else:
                fig = px.line(series, x="period", y="value")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data returned for this query/time range.")

        with st.expander("Show SQL"):
            for s in data.get("sql", []):
                st.code(s, language="sql")
