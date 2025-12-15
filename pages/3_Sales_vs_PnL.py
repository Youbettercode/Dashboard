import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="Sales vs P&L")

st.title("Sales vs P&L — Profit Bridge Analysis")

st.write(
    "This page compares **Gross Profit from Sales** with **Net Profit from P&L** "
    "to understand overhead, leakage, and operational efficiency."
)

# -------- Uploads --------
col1, col2 = st.columns(2)

with col1:
    sales_file = st.file_uploader(
        "Upload Sales Summary (Gross Profit)",
        type=["xlsx", "xls"],
        key="sales"
    )

with col2:
    pnl_file = st.file_uploader(
        "Upload 2025 P&L (Net Profit)",
        type=["xlsx", "xls"],
        key="pnl"
    )

if not sales_file or not pnl_file:
    st.info("Please upload both files to begin.")
    st.stop()

# -------- Load Sales --------
sales = pd.read_excel(sales_file)
sales = sales[sales["Month"].notna()].copy()
sales["Month"] = pd.to_datetime(sales["Month"], errors="coerce")
sales["Gross Profit"] = pd.to_numeric(
    sales["Gross Profit(w/o Tax)"], errors="coerce"
)

sales_gp = (
    sales.groupby(sales["Month"].dt.to_period("M"))
    .agg(Gross_Profit=("Gross Profit", "sum"))
    .reset_index()
)
sales_gp["Month"] = sales_gp["Month"].dt.to_timestamp()

# -------- Load P&L --------
pnl = pd.read_excel(pnl_file)
pnl.columns = [c.strip() for c in pnl.columns]

date_col = [c for c in pnl.columns if "month" in c.lower() or "date" in c.lower()][0]
profit_col = [c for c in pnl.columns if "net" in c.lower()][0]

pnl["Month"] = pd.to_datetime(pnl[date_col], errors="coerce")
pnl["Net Profit"] = pd.to_numeric(pnl[profit_col], errors="coerce")

pnl_np = pnl[pnl["Month"].notna()].copy()
pnl_np = pnl_np.sort_values("Month")

# -------- Merge --------
merged = pd.merge(
    sales_gp,
    pnl_np[["Month", "Net Profit"]],
    on="Month",
    how="inner"
)

merged["Overhead / Leakage"] = (
    merged["Gross_Profit"] - merged["Net Profit"]
)

# -------- KPIs --------
avg_overhead = merged["Overhead / Leakage"].mean()

k1, k2, k3 = st.columns(3)
k1.metric("Average Overhead", f"${avg_overhead:,.0f}")
k2.metric(
    "Best Month (Lowest Overhead)",
    merged.loc[merged["Overhead / Leakage"].idxmin(), "Month"].strftime("%Y-%m")
)
k3.metric(
    "Worst Month (Highest Overhead)",
    merged.loc[merged["Overhead / Leakage"].idxmax(), "Month"].strftime("%Y-%m")
)

st.markdown("---")

# -------- Chart --------
fig = px.line(
    merged,
    x="Month",
    y=["Gross_Profit", "Net Profit", "Overhead / Leakage"],
    markers=True,
    labels={"value": "USD"}
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Detail Table")
st.dataframe(merged)
