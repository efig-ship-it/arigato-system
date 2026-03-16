import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime, timedelta, date

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

# --- 2. LAYOUT & STYLE ---
st.set_page_config(page_title="Analytics Dashboard", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .kpi-box {
        background-color: #ffffff; padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;
        text-align: center;
    }
    .kpi-title { color: #64748b; font-size: 14px; font-weight: 600; text-transform: uppercase; }
    .kpi-value { font-size: 28px; font-weight: 700; color: #0f172a; margin: 10px 0; }
    .overdue { color: #ef4444 !important; }
    .expected { color: #10b981 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA & TOP SLICERS ---
df_raw = get_data()
if df_raw.empty:
    st.warning("No data found.")
    st.stop()

st.markdown('<p style="font-size:32px; font-weight:700;">Financial Operations Slicers 🎚️</p>', unsafe_allow_html=True)

# Slicers Row
s1, s2, s3 = st.columns(3)
with s1:
    companies = sorted(df_raw['company'].unique())
    selected_companies = st.multiselect("Filter Companies", companies, default=companies)
with s2:
    valid_dates = df_raw['date_dt'].dropna()
    default_min = valid_dates.min() if not valid_dates.empty else date.today()
    default_max = valid_dates.max() if not valid_dates.empty else date.today()
    date_range = st.date_input("Filter Date Range", [default_min, default_max])
with s3:
    statuses = sorted(df_raw['status'].unique())
    selected_statuses = st.multiselect("Filter Status", statuses, default=statuses)

# Filter Application
start_date = date_range[0]
end_date = date_range[1] if len(date_range) > 1 else date_range[0]

mask = (
    (df_raw['company'].isin(selected_companies)) &
    (df_raw['status'].isin(selected_statuses)) &
    (df_raw['date_dt'].fillna(date.min) >= start_date) &
    (df_raw['date_dt'].fillna(date.max) <= end_date)
)
df = df_raw.loc[mask]

# --- 4. CALCULATIONS ---
today = date.today()
next_week = today + timedelta(days=7)

total_billed = df['amount'].sum()
total_received = df['received_amount'].sum()
total_pending = df['balance'].sum()
overdue_amt = df[(df['due_date_dt'] < today) & (df['status'] != 'Paid')]['balance'].sum()
expected_amt = df[(df['due_date_dt'] >= today) & (df['due_date_dt'] <= next_week) & (df['status'] != 'Paid')]['balance'].sum()

# --- 5. KPI DASHBOARD ---
st.markdown("<br>", unsafe_allow_html=True)
k1, k2, k3, k4, k5 = st.columns(5)

with k1:
    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Total Billed</p><p class="kpi-value">₪{total_billed:,.0f}</p></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Collected</p><p class="kpi-value" style="color:#10b981;">₪{total_received:,.0f}</p></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Outstanding</p><p class="kpi-value" style="color:#3b82f6;">₪{total_pending:,.0f}</p></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Overdue 🚨</p><p class="kpi-value overdue">₪{overdue_amt:,.0f}</p></div>', unsafe_allow_html=True)
with k5:
    st.markdown(f'<div class="kpi-box"><p class="kpi-title">Next 7 Days 📅</p><p class="kpi-value expected">₪{expected_amt:,.0f}</p></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- 6. CHARTS ---
c1, c2 = st.columns(2)
with c1:
    st.subheader("Revenue by Status")
    fig_pie = px.pie(df, values='amount', names='status', hole=0.5,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("Monthly Collection Trend")
    df['month'] = pd.to_datetime(df['date_dt']).dt.strftime('%b %Y')
    trend = df.groupby('month').agg({'amount':'sum', 'received_amount':'sum'}).reset_index()
    fig_bar = go.Figure(data=[
        go.Bar(name='Billed', x=trend['month'], y=trend['amount'], marker_color='#cbd5e1'),
        go.Bar(name='Collected', x=trend['month'], y=trend['received_amount'], marker_color='#10b981')
    ])
    fig_bar.update_layout(barmode='group', template="simple_white")
    st.plotly_chart(fig_bar, use_container_width=True)

# --- 7. DETAILED TABLE ---
st.subheader("Collection Breakdown by Company")
pivot = df.groupby('company').agg({'amount':'sum', 'received_amount':'sum', 'balance':'sum'}).reset_index()
pivot['Rate'] = (pivot['received_amount'] / pivot['amount'] * 100).fillna(0)

st.dataframe(
    pivot.sort_values('balance', ascending=False),
    column_config={
        "amount": st.column_config.NumberColumn("Billed", format="₪%.0f"),
        "received_amount": st.column_config.NumberColumn("Collected", format="₪%.0f"),
        "balance": st.column_config.NumberColumn("Debt", format="₪%.0f"),
        "Rate": st.column_config.ProgressColumn("Collection %", format="%.0f%%", min_value=0, max_value=100)
    },
    use_container_width=True, hide_index=True
)
