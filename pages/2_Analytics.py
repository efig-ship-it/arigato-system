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

# --- 2. ADVANCED STYLE ---
st.set_page_config(page_title="Executive Dashboard", layout="wide")
st.markdown("""
    <style>
    .main-kpi {
        background-color: #ffffff; padding: 25px; border-radius: 20px;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-top: 5px solid;
        text-align: center; margin-bottom: 20px;
    }
    .kpi-label { color: #64748b; font-size: 16px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    .kpi-val { font-size: 42px; font-weight: 800; margin: 10px 0; }
    .secondary-kpi {
        background-color: #f8fafc; padding: 15px; border-radius: 12px;
        border: 1px solid #e2e8f0; text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA & SLICERS ---
df_raw = get_data()
if df_raw.empty:
    st.warning("No data found.")
    st.stop()

# --- TOP PRIORITY KPIs ---
today = date.today()
next_week = today + timedelta(days=7)

overdue_total = df_raw[(df_raw['due_date_dt'] < today) & (df_raw['status'] != 'Paid')]['balance'].sum()
expected_total = df_raw[(df_raw['due_date_dt'] >= today) & (df_raw['due_date_dt'] <= next_week) & (df_raw['status'] != 'Paid')]['balance'].sum()

st.markdown('<p style="font-size:28px; font-weight:700; color:#0f172a;">Executive Summary 👑</p>', unsafe_allow_html=True)

t1, t2 = st.columns(2)
with t1:
    st.markdown(f"""<div class="main-kpi" style="border-top-color: #ef4444;">
        <p class="kpi-label">🚨 Total Overdue</p>
        <p class="kpi-val" style="color: #ef4444;">₪{overdue_total:,.0f}</p>
    </div>""", unsafe_allow_html=True)
with t2:
    st.markdown(f"""<div class="main-kpi" style="border-top-color: #10b981;">
        <p class="kpi-label">📅 Expected This Week</p>
        <p class="kpi-val" style="color: #10b981;">₪{expected_total:,.0f}</p>
    </div>""", unsafe_allow_html=True)

st.divider()

# --- HORIZONTAL COMPACT SLICERS ---
st.markdown('**Filters:**')
f1, f2, f3 = st.columns([1, 1, 1])
with f1:
    companies = ["All Companies"] + sorted(df_raw['company'].unique().tolist())
    sel_comp = st.selectbox("Select Company", companies)
with f2:
    valid_dates = df_raw['date_dt'].dropna()
    dr = st.date_input("Date Range", [valid_dates.min(), valid_dates.max()] if not valid_dates.empty else [today, today])
with f3:
    status_list = ["All Statuses"] + sorted(df_raw['status'].unique().tolist())
    sel_stat = st.selectbox("Select Status", status_list)

# Data Filtering Logic
mask = (df_raw['date_dt'] >= dr[0]) & (df_raw['date_dt'] <= (dr[1] if len(dr) > 1 else dr[0]))
if sel_comp != "All Companies": mask &= (df_raw['company'] == sel_comp)
if sel_stat != "All Statuses": mask &= (df_raw['status'] == sel_stat)
df = df_raw.loc[mask]

# --- SECONDARY KPIs ---
st.markdown("<br>", unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)
total_billed = df['amount'].sum()
total_rec = df['received_amount'].sum()
coll_rate = (total_rec / total_billed * 100) if total_billed > 0 else 0

with k1:
    st.markdown(f'<div class="secondary-kpi"><p style="color:#64748b; font-size:12px;">BILLED</p><b>₪{total_billed:,.0f}</b></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="secondary-kpi"><p style="color:#64748b; font-size:12px;">COLLECTED</p><b>₪{total_rec:,.0f}</b></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="secondary-kpi"><p style="color:#64748b; font-size:12px;">COLLECTION RATE</p><b>{coll_rate:.1f}%</b></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="secondary-kpi"><p style="color:#64748b; font-size:12px;">ACTIVE CASES</p><b>{len(df)}</b></div>', unsafe_allow_html=True)

# --- CHARTS VARIETY ---
st.markdown("<br>", unsafe_allow_html=True)
c1, c2, c3 = st.columns([1.2, 1, 1.2])

with c1:
    # 1. Gauge Chart for Collection Rate
    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = coll_rate,
        title = {'text': "Collection Target %", 'font': {'size': 18}},
        gauge = {'axis': {'range': [None, 100]},
                 'bar': {'color': "#6366F1"},
                 'steps' : [
                     {'range': [0, 50], 'color': "#fee2e2"},
                     {'range': [50, 80], 'color': "#fef3c7"},
                     {'range': [80, 100], 'color': "#dcfce7"}]}))
    fig_gauge.update_layout(height=280, margin=dict(t=50, b=0, l=20, r=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

with c2:
    # 2. Treemap for Debt Distribution
    if not df[df['balance'] > 0].empty:
        fig_tree = px.treemap(df[df['balance'] > 0], path=['company'], values='balance',
                              title="Debt Distribution", color='balance', color_continuous_scale='Reds')
        fig_tree.update_layout(height=280, margin=dict(t=30, b=0, l=0, r=0))
        st.plotly_chart(fig_tree, use_container_width=True)
    else: 
        st.info("No Debt to show for current selection")

with c3:
    # 3. Monthly Trend Line
    if not df.empty:
        df_sorted = df.sort_values('date_dt')
        df_sorted['m'] = pd.to_datetime(df_sorted['date_dt']).dt.strftime('%b')
        trend = df_sorted.groupby('m', sort=False).agg({'amount':'sum', 'received_amount':'sum'}).reset_index()
        fig_line = go.Figure()
        fig_line.add_trace(go.Scatter(x=trend['m'], y=trend['amount'], name="Billed", line=dict(color='#cbd5e1', width=3)))
        fig_line.add_trace(go.Scatter(x=trend['m'], y=trend['received_amount'], name="Collected", line=dict(color='#6366F1', width=4)))
        fig_line.update_layout(height=280, title="Collection Over Time", margin=dict(t=30, b=0, l=20, r=20), template="simple_white")
        st.plotly_chart(fig_line, use_container_width=True)

# --- FINAL TABLE ---
st.subheader("Account Receivable Ledger")
ledger = df.groupby('company').agg({'amount':'sum', 'received_amount':'sum', 'balance':'sum'}).reset_index()
st.dataframe(
    ledger.sort_values('balance', ascending=False),
    column_config={
        "company": "Company Name",
        "amount": st.column_config.NumberColumn("Total Billed", format="₪%.0f"),
        "received_amount": st.column_config.NumberColumn("Collected", format="₪%.0f"),
        "balance": st.column_config.NumberColumn("Outstanding", format="₪%.0f")
    }, use_container_width=True, hide_index=True
)
