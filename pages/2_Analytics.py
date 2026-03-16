import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. CONNECTION ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_data():
    res = supabase.table("billing_history").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
        df['balance'] = df['amount'] - df['received_amount']
        df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce').dt.date
        df['due_date_dt'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
    return df

# --- 2. CONFIG & STYLE ---
st.set_page_config(page_title="Tuesday | Analytics", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-title { font-size: 34px; font-weight: 700; color: #0F172A; margin-bottom: 20px; }
    .stMetric { background-color: #FFFFFF; border: 1px solid #E2E8F0; padding: 15px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">Financial Insights Dashboard 📊</p>', unsafe_allow_html=True)

# --- 3. DATA & SIDEBAR FILTERS ---
df_raw = get_data()

if df_raw.empty:
    st.warning("No data found. Please send invoices first.")
    st.stop()

st.sidebar.header("🔍 Global Filters")

# Date Filter
min_date = df_raw['date_dt'].min()
max_date = df_raw['date_dt'].max()
date_range = st.sidebar.date_input("Date Range", [min_date, max_date])

# Company Filter
companies = sorted(df_raw['company'].unique())
selected_companies = st.sidebar.multiselect("Companies", companies, default=companies)

# Status Filter
statuses = sorted(df_raw['status'].unique())
selected_statuses = st.sidebar.multiselect("Statuses", statuses, default=statuses)

# Apply Filters
mask = (
    (df_raw['date_dt'] >= date_range[0]) & 
    (df_raw['date_dt'] <= (date_range[1] if len(date_range) > 1 else date_range[0])) &
    (df_raw['company'].isin(selected_companies)) &
    (df_raw['status'].isin(selected_statuses))
)
df = df_raw.loc[mask]

if st.sidebar.button("🔄 Clear Cache & Refresh"):
    st.cache_resource.clear()
    st.rerun()

# --- 4. CALCULATIONS ---
today = datetime.now().date()
next_week = today + timedelta(days=7)

total_billed = df['amount'].sum()
total_received = df['received_amount'].sum()
total_pending = df['balance'].sum()

# Accurate Overdue: Only where status is 'Overdue' OR (due_date passed AND status not Paid)
overdue_amount = df[
    (df['status'] == 'Overdue') | 
    ((df['due_date_dt'] < today) & (df['status'] != 'Paid'))
]['balance'].sum()

# Expected this week: Due dates within the next 7 days
expected_this_week = df[
    (df['due_date_dt'] >= today) & 
    (df['due_date_dt'] <= next_week) & 
    (df['status'] != 'Paid')
]['balance'].sum()

collection_rate = (total_received / total_billed * 100) if total_billed > 0 else 0

# --- 5. TOP KPI ROW ---
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Billed", f"₪{total_billed:,.0f}")
k2.metric("Collected", f"₪{total_received:,.0f}", f"{collection_rate:.1f}% Rate")
k3.metric("Outstanding", f"₪{total_pending:,.0f}")
k4.metric("Overdue 🚨", f"₪{overdue_amount:,.0f}", delta_color="inverse")
k5.metric("Due This Week 📅", f"₪{expected_this_week:,.0f}")

st.markdown("---")

# --- 6. VISUALS ---
c1, c2 = st.columns([1, 1])

with c1:
    st.subheader("Billing by Status")
    status_summary = df.groupby('status')['amount'].sum().reset_index()
    fig_pie = px.pie(status_summary, values='amount', names='status', 
                     hole=0.5, template="plotly_white",
                     color='status',
                     color_discrete_map={'Paid':'#10B981', 'Sent':'#6366F1', 'Overdue':'#EF4444', 'Partial':'#F59E0B'})
    fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0))
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("Monthly Performance")
    df['month_year'] = pd.to_datetime(df['date_dt']).dt.strftime('%b %Y')
    trend_df = df.sort_values('date_dt').groupby('month_year', sort=False).agg({'amount':'sum', 'received_amount':'sum'}).reset_index()
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(x=trend_df['month_year'], y=trend_df['amount'], name='Billed', marker_color='#6366F1'))
    fig_trend.add_trace(go.Bar(x=trend_df['month_year'], y=trend_df['received_amount'], name='Collected', marker_color='#10B981'))
    fig_trend.update_layout(barmode='group', template="plotly_white", margin=dict(t=30, b=0, l=0, r=0))
    st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# --- 7. PIVOT TABLE ---
st.subheader("Company Performance Table")

pivot_table = df.groupby('company').agg({
    'amount': 'sum',
    'received_amount': 'sum',
    'balance': 'sum',
    'id': 'count'
}).rename(columns={'id': 'Invoices'}).reset_index()

pivot_table['Collection %'] = (pivot_table['received_amount'] / pivot_table['amount'] * 100).fillna(0)
pivot_table = pivot_table.sort_values(by='balance', ascending=False)

st.dataframe(
    pivot_table,
    column_config={
        "company": "Company",
        "amount": st.column_config.NumberColumn("Billed", format="₪%.0f"),
        "received_amount": st.column_config.NumberColumn("Collected", format="₪%.0f"),
        "balance": st.column_config.NumberColumn("Debt", format="₪%.0f"),
        "Collection %": st.column_config.ProgressColumn("Rate", format="%.0f%%", min_value=0, max_value=100),
    },
    use_container_width=True, 
    hide_index=True
)

# --- 8. TOP DEBTORS ---
st.subheader("Top 5 Debtors")
top_5 = pivot_table[pivot_table['balance'] > 0].head(5)
if not top_5.empty:
    fig_debt = px.bar(top_5, x='company', y='balance', 
                      text_auto='.2s', color='balance', color_continuous_scale='Reds',
                      labels={'balance': 'Unpaid', 'company': 'Client'}, template="plotly_white")
    st.plotly_chart(fig_debt, use_container_width=True)
else:
    st.success("No outstanding debts for current selection!")
