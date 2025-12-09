# streamlit_app.py
# Streamlit interactive dashboard for Appliances4Less (Richmond)
# Features:
# - Load 2024 & 2025 sales Excel files (or let user upload their own)
# - Clean / infer key columns (date, revenue, cost, tax, profit)
# - Compute: monthly revenue, MoM growth, monthly profit (w/o tax), YoY revenue
# - Charts: KPI row, line charts, bar charts, heatmap, table, export
# - Deployable to Streamlit Cloud or any server

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime

st.set_page_config(layout="wide", page_title="Appliances4Less — Sales Dashboard")

@st.cache_data
def load_excel(path):
    try:
        return pd.read_excel(path)
    except Exception as e:
        st.error(f"Could not read {path}: {e}")
        return pd.DataFrame()

@st.cache_data
def infer_and_prepare(df):
    # make a copy
    df = df.copy()
    # normalize columns
    df.columns = [str(c).strip() for c in df.columns]
    cols_lower = [c.lower() for c in df.columns]

    # Find date column
    date_col = None
    for candidate in ['date','sale date','sold date','transaction date','transaction_date','datetime']:
        if candidate in cols_lower:
            date_col = df.columns[cols_lower.index(candidate)]
            break
    if date_col is None:
        # fallback: first datetime-like column
        for c in df.columns:
            try:
                pd.to_datetime(df[c])
                date_col = c
                break
            except:
                continue
    if date_col is None:
        st.warning('No date column detected. Please ensure a date column exists or upload a file with a date column.')
    else:
        df['__date'] = pd.to_datetime(df[date_col], errors='coerce')

    # Revenue column detection
    revenue_col = None
    for candidate in ['total','amount','sale amount','revenue','sale','total sale','total_amount','grand total','grand_total']:
        if candidate in cols_lower:
            revenue_col = df.columns[cols_lower.index(candidate)]
            break
    if revenue_col is None:
        # try columns containing 'total' or 'amount'
        for i,c in enumerate(cols_lower):
            if 'total' in c or 'amount' in c or 'sale' in c:
                revenue_col = df.columns[i]
                break
    if revenue_col is None:
        st.warning('No revenue column detected automatically. You can select manually in the sidebar.')
    else:
        df['__revenue'] = pd.to_numeric(df[revenue_col], errors='coerce')

    # Try to get tax/cost/profit
    cost_col = None
    for candidate in ['cost','unit cost','cogs','cost_of_goods','cost_of_goods_sold']:
        if candidate in cols_lower:
            cost_col = df.columns[cols_lower.index(candidate)]
            break
    if cost_col is not None:
        df['__cost'] = pd.to_numeric(df[cost_col], errors='coerce')

    tax_col = None
    for candidate in ['tax','sales tax','tax_amount']:
        if candidate in cols_lower:
            tax_col = df.columns[cols_lower.index(candidate)]
            break
    if tax_col is not None:
        df['__tax'] = pd.to_numeric(df[tax_col], errors='coerce')

    profit_col = None
    for candidate in ['profit','net','gross profit','profit_without_tax']:
        if candidate in cols_lower:
            profit_col = df.columns[cols_lower.index(candidate)]
            break
    if profit_col is not None:
        df['__profit'] = pd.to_numeric(df[profit_col], errors='coerce')

    # If profit not present but revenue and cost present, compute profit_without_tax
    if '__profit' not in df.columns or df.get('__profit').isna().all():
        if '__revenue' in df.columns and '__cost' in df.columns:
            if '__tax' in df.columns:
                df['__profit'] = df['__revenue'] - df['__cost'] - df['__tax']
            else:
                df['__profit'] = df['__revenue'] - df['__cost']
        else:
            # leave as NaN
            df['__profit'] = pd.to_numeric(df.get('__profit'))

    # helpful columns
    if '__date' in df.columns:
        df['year'] = df['__date'].dt.year
        df['month'] = df['__date'].dt.to_period('M').astype(str)
        df['month_start'] = df['__date'].dt.to_period('M').dt.to_timestamp()

    return df

# --- UI: sidebar ---
st.sidebar.title('Data inputs & options')
st.sidebar.write('By default the app looks for the two uploaded files:')
st.sidebar.write('- /mnt/data/A4L 2024 Sales data.xlsx\n- /mnt/data/A4L 2025 Sales data.xlsx')

use_defaults = st.sidebar.checkbox('Load default 2024 & 2025 files from /mnt/data (if present)', value=True)

uploaded_files = st.sidebar.file_uploader('Or upload one or more Excel/CSV files', type=['xlsx','xls','csv'], accept_multiple_files=True)

if use_defaults and not uploaded_files:
    paths = ['/mnt/data/A4L 2024 Sales data.xlsx','/mnt/data/A4L 2025 Sales data.xlsx']
    dfs = []
    for p in paths:
        df = load_excel(p)
        if not df.empty:
            df['__source_file'] = p
            dfs.append(df)
else:
    dfs = []
    for uf in uploaded_files:
        try:
            if uf.name.lower().endswith('.csv'):
                df = pd.read_csv(uf)
            else:
                df = pd.read_excel(uf)
            df['__source_file'] = uf.name
            dfs.append(df)
        except Exception as e:
            st.sidebar.error(f'Error reading {uf.name}: {e}')

if not dfs:
    st.warning('No data loaded yet. Upload files or enable default file loading in the sidebar.')
    st.stop()

# combine
raw = pd.concat(dfs, ignore_index=True)

# preprocess
# === Custom cleanup for fixed-format file ===
cols_to_drop = [
    'Data','Invoice#','Warranty(2-5Yrs)','Warranty 2-5Yrs(%)','Total Warranty','Delivery?',
    'Delivery Fee','Delivery Fee/Item','Delivery Date','Accessory?','Accessory Fee',
    'Accessory Fee/Item','Customer','Cashier','Source','Store','PO3A-ID'
]
raw = raw.drop(columns=[c for c in cols_to_drop if c in raw.columns], errors='ignore')

# Add Year column based on Month column
if 'Month' in raw.columns:
    mdt = pd.to_datetime(raw['Month'], errors='coerce')
    raw['Year'] = mdt.dt.year

# Use Grand Total as revenue if available
# Also force profit column to use 'Gross Profit(w/o Tax)' if present
if 'Gross Profit(w/o Tax)' in raw.columns:
    raw['__profit'] = pd.to_numeric(raw['Gross Profit(w/o Tax)'], errors='coerce')

if 'Grand Total' in raw.columns:
    raw['__revenue'] = pd.to_numeric(raw['Grand Total'], errors='coerce')
# === End custom cleanup ===

# Add data preview table
data_preview = st.sidebar.checkbox('Show raw data preview', value=False)
if data_preview:
    st.subheader('Raw Data Preview')
    st.dataframe(raw.head(200))

df = infer_and_prepare(raw)

# Let user override detected columns if needed
st.sidebar.markdown('---')
st.sidebar.subheader('Column overrides')
col_options = list(raw.columns)
selected_date = st.sidebar.selectbox('Date column (detected)', options=['__date'] + col_options, index=0)
selected_revenue = st.sidebar.selectbox('Revenue column (detected)', options=['__revenue'] + col_options, index=0)
selected_profit = st.sidebar.selectbox('Profit column (detected or computed)', options=['__profit'] + col_options, index=0)

if selected_date != '__date':
    df['__date'] = pd.to_datetime(raw[selected_date], errors='coerce')
    df['year'] = df['__date'].dt.year
    df['month'] = df['__date'].dt.to_period('M').astype(str)
    df['month_start'] = df['__date'].dt.to_period('M').dt.to_timestamp()

if selected_revenue != '__revenue':
    df['__revenue'] = pd.to_numeric(raw[selected_revenue], errors='coerce')
if selected_profit != '__profit' and selected_profit in raw.columns:
    df['__profit'] = pd.to_numeric(raw[selected_profit], errors='coerce')

# Filters
st.sidebar.markdown('---')
st.sidebar.subheader('Filters')
min_date = df['__date'].min()
max_date = df['__date'].max()
start_dt, end_dt = st.sidebar.date_input('Date range', value=[min_date.date() if pd.notna(min_date) else datetime.today().date(), max_date.date() if pd.notna(max_date) else datetime.today().date()])

mask = (df['__date'] >= pd.to_datetime(start_dt)) & (df['__date'] <= pd.to_datetime(end_dt))
filtered = df.loc[mask].copy()

# Optional grouping columns for business: store, cashier, payment method
group_cols = []
for key in ['store','location','cashier','payment method','payment','payment_method','method']:
    if key in [c.lower() for c in filtered.columns]:
        orig = filtered.columns[[c.lower() for c in filtered.columns].index(key)]
        group_cols.append(orig)

# allow user to pick a grouping column
group_by = None
if group_cols:
    group_by = st.sidebar.selectbox('Group data by (optional)', options=['(none)'] + group_cols, index=0)
    if group_by == '(none)':
        group_by = None

# compute KPIs
agg = filtered.groupby('month_start').agg(revenue=('__revenue','sum'), profit=('__profit','sum')).reset_index().sort_values('month_start')
agg['month'] = agg['month_start'].dt.to_period('M').astype(str)

# MoM growth
agg['revenue_prev'] = agg['revenue'].shift(1)
agg['revenue_mom_pct'] = (agg['revenue'] - agg['revenue_prev']) / agg['revenue_prev'] * 100
agg['profit_prev'] = agg['profit'].shift(1)
agg['profit_mom_pct'] = (agg['profit'] - agg['profit_prev']) / agg['profit_prev'] * 100

# YoY revenue: compare each month to same month last year
agg['month_number'] = agg['month_start'].dt.month
agg['year'] = agg['month_start'].dt.year
agg['revenue_lag_12'] = agg.groupby('month_number')['revenue'].shift(12)
agg['revenue_yoy_pct'] = (agg['revenue'] - agg['revenue_lag_12']) / agg['revenue_lag_12'] * 100

# Layout
st.title('Appliances4Less — Sales & Profit Dashboard (Richmond)')
st.markdown('Use the sidebar to change data inputs, date range, and grouping')

# KPI row
latest = agg.iloc[-1] if not agg.empty else None
col1, col2, col3, col4 = st.columns(4)
if latest is not None:
    col1.metric('Revenue (latest month)', f"${latest['revenue']:,.0f}", delta=f"{latest['revenue_mom_pct']:.2f}% MoM" if pd.notna(latest['revenue_mom_pct']) else "—")
    col2.metric('Profit w/o tax (latest month)', f"${latest['profit']:,.0f}", delta=f"{latest['profit_mom_pct']:.2f}% MoM" if pd.notna(latest['profit_mom_pct']) else "—")
    # Year to date revenue
    ytd = agg[agg['month_start'].dt.year == latest['year']]['revenue'].sum()
    col3.metric(f"YTD Revenue ({latest['year']})", f"${ytd:,.0f}")
    # YoY for the same month last year
    yoy_txt = f"{latest['revenue_yoy_pct']:.2f}% YoY" if pd.notna(latest['revenue_yoy_pct']) else '—'
    col4.metric('YoY (same month)', yoy_txt)
else:
    st.info('Not enough data to compute KPIs. Please adjust your date range or upload data.')

st.markdown('---')

# Charts area
left, right = st.columns((2,1))
with left:
    st.subheader('Revenue & Profit — monthly')
    fig = px.line(agg, x='month_start', y=['revenue','profit'], labels={'value':'USD','month_start':'Month'}, markers=True)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader('Month-over-month revenue % change')
    fig2 = px.bar(agg, x='month_start', y='revenue_mom_pct', labels={'revenue_mom_pct':'MoM %'})
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader('Revenue: monthly breakdown by group (if grouping selected)')
    if group_by:
        grouped = filtered.groupby([pd.Grouper(key='__date', freq='M'), group_by]).agg(revenue=('__revenue','sum')).reset_index()
        grouped['month_start'] = grouped['__date'].dt.to_period('M').dt.to_timestamp()
        fig3 = px.bar(grouped, x='month_start', y='revenue', color=group_by, barmode='stack')
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info('Select a grouping column in the sidebar to see breakdowns by that dimension.')

with right:
    st.subheader('Recent months table')
    st.dataframe(agg[['month','revenue','revenue_mom_pct','profit','profit_mom_pct','revenue_yoy_pct']].sort_values('month', ascending=False).head(12))

    st.subheader('Monthly revenue heatmap (month vs year)')
    # prepare heatmap
    rev_pivot = agg.pivot_table(index='year', columns='month_number', values='revenue', aggfunc='sum')
    if not rev_pivot.empty:
        rev_pivot = rev_pivot.reindex(sorted(rev_pivot.index), axis=0)
        rev_pivot = rev_pivot[[i for i in range(1,13)]]
        # Replace numeric heatmap with color-coded heatmap
# Heatmap removed per user request. Display numeric pivot table instead.
# Heatmap fully removed to eliminate syntax errors
# Simple revenue pivot table display
st.subheader('Monthly Revenue (pivot table)')
if not rev_pivot.empty:
    st.dataframe(rev_pivot)
else:
    st.info('Not enough data for monthly pivot.').astype(float))
    else:
        st.info('Not enough data for heatmap.')

st.markdown('---')

# Additional analysis
st.subheader('Deeper analysis')
with st.expander('Top SKUs / Products (if available)'):
    sku_cols = [c for c in filtered.columns if 'sku' in c.lower() or 'product' in c.lower() or 'item' in c.lower()]
    if sku_cols:
        sku = sku_cols[0]
        top = filtered.groupby(sku).agg(revenue=('__revenue','sum'), profit=('__profit','sum'), count=(sku,'count')).reset_index().sort_values('revenue', ascending=False)
        st.dataframe(top.head(25))
    else:
        st.info('No SKU or Product column detected.')

with st.expander('Payment method breakdown (if available)'):
    pay_cols = [c for c in filtered.columns if 'pay' in c.lower() or 'method' in c.lower()]
    if pay_cols:
        pay = pay_cols[0]
        pay_summary = filtered.groupby(pay).agg(revenue=('__revenue','sum'), count=(pay,'count')).reset_index().sort_values('revenue', ascending=False)
        st.dataframe(pay_summary)
        figpay = px.pie(pay_summary, names=pay, values='revenue')
        st.plotly_chart(figpay, use_container_width=True)
    else:
        st.info('No payment method column detected.')

st.markdown('---')

# Export filtered data / aggregated data
st.subheader('Export')
st.write('Download the filtered raw data or the monthly aggregated CSV for reporting')

@st.cache_data
def to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

if st.button('Download filtered raw (CSV)'):
    csv = to_csv(filtered)
    st.download_button('Click to download filtered CSV', data=csv, file_name='filtered_sales.csv', mime='text/csv')

csv_agg = to_csv(agg)
st.download_button('Download monthly aggregates (CSV)', data=csv_agg, file_name='monthly_aggregates.csv', mime='text/csv')

st.markdown('---')

st.info('This dashboard is a template. If column names in your files differ from the common names, use the Column overrides in the sidebar to point to the correct columns (date, revenue, profit).')

st.markdown('### Next steps / customization ideas')
st.markdown('- Add margins by product category, more precise "profit without tax" if taxes are stored separately.\n- Add rolling 3/6/12-month averages.\n- Add forecasting (e.g., Prophet or ARIMA) for 2026 planning.\n- Add user login or environment variables for multi-store deployments.\n- Add automated report email (PDF) monthly using a scheduler.')

# End of app
