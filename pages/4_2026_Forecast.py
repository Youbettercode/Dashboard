import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(layout="wide", page_title="2026 Forecast")

st.title("2026 Revenue & Profit Forecast")

st.write(
    "This page provides a **simple, explainable forecast** for 2026 "
    "based on historical performance."
)

file = st.file_uploader(
    "Upload Sales Summary (with Month, Grand Total, Gross Profit)",
    type=["xlsx", "xls"]
)

if not file:
    st.info("Upload sales data to generate forecast.")
    st.stop()

df = pd.read_excel(file)
df = df[df["Month"].notna()].copy()

df["Month"] = pd.to_datetime(df["Month"], errors="coerce")
df["Revenue"] = pd.to_numeric(df["Grand Total"], errors="coerce")
df["Profit"] = pd.to_numeric(df["Gross Profit(w/o Tax)"], errors="coerce")

monthly = (
    df.groupby(df["Month"].dt.to_period("M"))
    .agg(
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum")
    )
    .reset_index()
)
monthly["Month"] = monthly["Month"].dt.to_timestamp()

# -------- Assumptions --------
avg_margin = (monthly["Profit"] / monthly["Revenue"]).mean()
avg_monthly_revenue = monthly["Revenue"].mean()

growth = st.slider(
    "Expected Monthly Revenue Growth (%)",
    min_value=-10.0,
    max_value=20.0,
    value=3.0
) / 100

# -------- Forecast --------
future_months = pd.date_range("2026-01-01", "2026-12-01", freq="MS")
forecast = []

rev = avg_monthly_revenue
for m in future_months:
    rev *= (1 + growth)
    profit = rev * avg_margin
    forecast.append([m, rev, profit])

fc = pd.DataFrame(
    forecast, columns=["Month", "Forecast Revenue", "Forecast Profit"]
)

# -------- Charts --------
fig = px.line(
    fc,
    x="Month",
    y=["Forecast Revenue", "Forecast Profit"],
    markers=True,
    labels={"value": "USD"}
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Forecast Table")
st.dataframe(fc)
