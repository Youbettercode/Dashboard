import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.express as px

st.set_page_config(
    page_title="Appliances4Less Richmond - Sales Dashboard",
    layout="wide"
)

# ---------- Data Loading ----------

@st.cache_data
def load_data(file_path: str = "24 & 25 Sales Summary.xlsx") -> pd.DataFrame:
    """Load the fixed-format sales summary file."""
    try:
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        st.error(f"Error loading '{file_path}': {e}")
        return pd.DataFrame()

# For Streamlit Cloud, you can either:
# 1) keep the Excel file in the repo root with this exact name, or
# 2) use file_uploader below to override.

st.sidebar.header("Data Source")

use_default = st.sidebar.checkbox(
    "Use bundled file: '24 & 25 Sales Summary.xlsx'",
    value=True
)

uploaded_file = st.sidebar.file_uploader(
    "Or upload a Sales Summary file",
    type=["xlsx", "xls"],
    accept_multiple_files=False
)

if use_default:
    df_raw = load_data()
else:
    if uploaded_file is not None:
        df_raw = pd.read_excel(uploaded_file)
    else:
        st.warning("No file loaded yet. Please upload a file or enable default file.")
        st.stop()

if df_raw.empty:
    st.warning("Loaded data is empty. Please check the file.")
    st.stop()

# ---------- Schema Cleanup & Business Rules ----------

# 1) Only keep rows where Month has values
if "Month" not in df_raw.columns:
    st.error("Column 'Month' not found in the data. Please check your Excel format.")
    st.dataframe(df_raw.head())
    st.stop()

df = df_raw[df_raw["Month"].notna()].copy()

# 2) Drop columns you don't care about
cols_to_drop = [
    "Data", "Invoice#", "Warranty(2-5Yrs)", "Warranty 2-5Yrs(%)",
    "Total Warranty", "Delivery?", "Delivery Fee", "Delivery Fee/Item",
    "Delivery Date", "Accessory?", "Accessory Fee", "Accessory Fee/Item",
    "Customer", "Cashier", "Source", "Store", "PO3A-ID"
]
df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors="ignore")

# 3) Create Year column based on Month
# Try to parse Month as a date (e.g. '2024-01', 'Jan-24', etc.)
month_parsed = pd.to_datetime(df["Month"], errors="coerce")

df["Year"] = month_parsed.dt.year
# We'll also create a normalized month_start date for grouping/plotting
df["MonthStart"] = month_parsed.dt.to_period("M").dt.to_timestamp()

# 4) Set Revenue and Profit
if "Grand Total" not in df.columns:
    st.error("Column 'Grand Total' (revenue) not found in the data.")
    st.dataframe(df.head())
    st.stop()

if "Gross Profit(w/o Tax)" not in df.columns:
    st.error("Column 'Gross Profit(w/o Tax)' not found in the data.")
    st.dataframe(df.head())
    st.stop()

df["Revenue"] = pd.to_numeric(df["Grand Total"], errors="coerce")
df["Profit"] = pd.to_numeric(df["Gross Profit(w/o Tax)"], errors="coerce")

# Safety: drop rows with no MonthStart or Revenue
df = df[df["MonthStart"].notna() & df["Revenue"].notna()].copy()

# ---------- Sidebar Filters ----------

st.sidebar.header("Filters")

min_month = df["MonthStart"].min()
max_month = df["MonthStart"].max()

if pd.isna(min_month) or pd.isna(max_month):
    st.error("Could not determine min/max Month from data.")
    st.dataframe(df.head())
    st.stop()

start_date, end_date = st.sidebar.date_input(
    "Month range",
    value=[min_month.date(), max_month.date()]
)

mask = (df["MonthStart"].dt.date >= start_date) & (df["MonthStart"].dt.date <= end_date)
df_filtered = df.loc[mask].copy()

if df_filtered.empty:
    st.warning("No data in the selected date range.")
    st.stop()

# ---------- Aggregations ----------

# Monthly aggregation (Revenue + Profit)
monthly = (
    df_filtered
    .groupby("MonthStart", as_index=False)
    .agg(
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum")
    )
    .sort_values("MonthStart")
)

# Month-over-month growth
monthly["Revenue_prev"] = monthly["Revenue"].shift(1)
monthly["Profit_prev"] = monthly["Profit"].shift(1)

monthly["Revenue_MoM_%"] = (monthly["Revenue"] - monthly["Revenue_prev"]) / monthly["Revenue_prev"] * 100
monthly["Profit_MoM_%"] = (monthly["Profit"] - monthly["Profit_prev"]) / monthly["Profit_prev"] * 100

# Year column for monthly
monthly["Year"] = monthly["MonthStart"].dt.year
monthly["MonthLabel"] = monthly["MonthStart"].dt.strftime("%Y-%m")

# Yearly aggregation for YoY
yearly = (
    df_filtered
    .groupby("Year", as_index=False)
    .agg(
        Revenue=("Revenue", "sum"),
        Profit=("Profit", "sum")
    )
    .sort_values("Year")
)

# ---------- Layout: Title & Raw Preview ----------

st.title("Appliances4Less Richmond — Sales Summary Dashboard")

with st.expander("🔍 Raw Data Preview (after cleaning)"):
    st.write("Showing only rows where `Month` has values and after dropping unused columns.")
    st.dataframe(df_filtered.head(500))

# ---------- KPI Row ----------

latest_row = monthly.iloc[-1]

col1, col2, col3 = st.columns(3)
col1.metric(
    "Latest Month Revenue",
    f"${latest_row['Revenue']:,.0f}",
    f"{latest_row['Revenue_MoM_%']:.1f}% MoM" if pd.notna(latest_row["Revenue_MoM_%"]) else "N/A"
)
col2.metric(
    "Latest Month Profit (w/o Tax)",
    f"${latest_row['Profit']:,.0f}",
    f"{latest_row['Profit_MoM_%']:.1f}% MoM" if pd.notna(latest_row["Profit_MoM_%"]) else "N/A"
)
col3.metric(
    "Selected Range Total Revenue",
    f"${df_filtered['Revenue'].sum():,.0f}"
)

st.markdown("---")

# ---------- Charts: Revenue & Profit Over Time ----------

left, right = st.columns(2)

with left:
    st.subheader("Revenue & Profit by Month")

    fig_line = px.line(
        monthly,
        x="MonthStart",
        y=["Revenue", "Profit"],
        labels={"value": "USD", "MonthStart": "Month"},
        markers=True
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.subheader("Month-over-Month Revenue % Change")
    fig_mom = px.bar(
        monthly,
        x="MonthStart",
        y="Revenue_MoM_%",
        labels={"Revenue_MoM_%": "Revenue MoM %", "MonthStart": "Month"}
    )
    st.plotly_chart(fig_mom, use_container_width=True)

with right:
    st.subheader("Yearly Revenue & Profit")

    fig_year = px.bar(
        yearly,
        x="Year",
        y=["Revenue", "Profit"],
        barmode="group",
        labels={"value": "USD"}
    )
    st.plotly_chart(fig_year, use_container_width=True)

    st.subheader("Monthly Aggregates Table")
    st.dataframe(
        monthly[["MonthLabel", "Revenue", "Revenue_MoM_%", "Profit", "Profit_MoM_%"]]
        .sort_values("MonthLabel", ascending=False)
    )

st.markdown("---")

# ---------- Extra: Cumulative Revenue ----------

st.subheader("Cumulative Revenue Over Time")

monthly["Cumulative_Revenue"] = monthly["Revenue"].cumsum()
fig_cum = px.line(
    monthly,
    x="MonthStart",
    y="Cumulative_Revenue",
    labels={"MonthStart": "Month", "Cumulative_Revenue": "Cumulative Revenue (USD)"},
    markers=True
)
st.plotly_chart(fig_cum, use_container_width=True)

# ---------- Export Options ----------

st.markdown("---")
st.subheader("Export Data")

@st.cache_data
def to_csv_bytes(_df: pd.DataFrame) -> bytes:
    return _df.to_csv(index=False).encode("utf-8")

col_exp1, col_exp2 = st.columns(2)

with col_exp1:
    st.download_button(
        "Download filtered raw data (CSV)",
        data=to
