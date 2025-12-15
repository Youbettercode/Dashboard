import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide", page_title="2025 P&L Analysis")

st.title("2025 P&L — Net Profit Analysis")

st.write(
    "This page analyzes the 2025 P&L file and focuses on **net profit trends, averages, "
    "and variability** to support planning and decision-making."
)

uploaded_file = st.file_uploader(
    "Upload 2025 P&L Excel file",
    type=["xlsx", "xls"]
)

if uploaded_file is None:
    st.info("Please upload the 2025 P&L Excel file to begin.")
    st.stop()

# ---------------- Load & Clean ----------------

df_raw = pd.read_excel(uploaded_file)
df = df_raw.copy()

df.columns = [str(c).strip() for c in df.columns]
cols_lower = [c.lower() for c in df.columns]

# Detect month/date column
date_col = None
for c in cols_lower:
    if "month" in c or "date" in c:
        date_col = df.columns[cols_lower.index(c)]
        break

if date_col is None:
    st.error("Could not find a Month or Date column.")
    st.dataframe(df.head())
    st.stop()

df["Month"] = pd.to_datetime(df[date_col], errors="coerce")

# Detect net profit column
profit_col = None
for c in cols_lower:
    if "net profit" in c or "net income" in c:
        profit_col = df.columns[cols_lower.index(c)]
        break

if profit_col is None:
    st.error("Could not find a Net Profit / Net Income column.")
    st.dataframe(df.head())
    st.stop()

df["Net Profit"] = pd.to_numeric(df[profit_col], errors="coerce")

# Keep valid rows only
df = df[df["Month"].notna() & df["Net Profit"].notna()].copy()
df = df.sort_values("Month")

if df.empty:
    st.error("No valid data found after cleaning.")
    st.stop()

# ---------------- KPIs ----------------

avg_profit = df["Net Profit"].mean()

k1, k2, k3 = st.columns(3)
k1.metric("Average Monthly Net Profit", f"${avg_profit:,.0f}")
k2.metric(
    "Best Month",
    df.loc[df["Net Profit"].idxmax(), "Month"].strftime("%Y-%m"),
    f"${df['Net Profit'].max():,.0f}",
)
k3.metric(
    "Worst Month",
    df.loc[df["Net Profit"].idxmin(), "Month"].strftime("%Y-%m"),
    f"${df['Net Profit'].min():,.0f}",
)

st.markdown("---")

# ---------------- Trend ----------------

st.subheader("Net Profit Trend (2025)")

fig_trend = px.line(
    df,
    x="Month",
    y="Net Profit",
    markers=True,
    labels={"Net Profit": "USD"},
)

fig_trend.add_hline(
    y=avg_profit,
    line_dash="dash",
    annotation_text="Average Net Profit",
)

st.plotly_chart(fig_trend, use_container_width=True)

# ---------------- Distribution ----------------

st.subheader("Net Profit Distribution")

fig_dist = px.histogram(
    df,
    x="Net Profit",
    nbins=10,
    marginal="box",
)

st.plotly_chart(fig_dist, use_container_width=True)

# ---------------- Table ----------------

st.subheader("P&L Detail Table")
st.dataframe(df)
