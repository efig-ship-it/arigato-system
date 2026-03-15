import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from app import get_cloud_history, supabase

# --- PAGE CONFIG ---
st.set_page_config(page_title="Tuesday | BI & Analytics", page_icon="📈", layout="wide")

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.title("Business Intelligence & Analytics 📊")

# --- CSS ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# 1. LOAD DATA
df_raw = get_cloud_history()

if not df_raw.empty:
    df = df_raw.copy()
    
    # --- תיקון השגיאה: המרת תאריכים בטוחה ---
    # ה-errors='coerce' הופך תאריכים לא חוקיים ל-NaT במקום להפיל את האפליקציה
    df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce').dt.date
    # הסרת שורות שבהן התאריך לא חוקי כדי שהגרפים לא יקרסו
    df = df.dropna(subset=['date_dt'])
    
    # יצירת עמודת חודש-שנה לתצוגה בגרפים
    df['month_year'] = pd.to_datetime(df['date_dt']).dt.strftime('%b %Y')
    
    # --- FILTERS SECTION ---
    with st.expander("🔍 Advanced Reporting Filters", expanded=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            all_comps = sorted(df['company'].unique())
            sel_comps = st.multiselect("Filter Companies", all_comps)
        with f2:
            all_status = df['status'].unique()
            sel_status = st.multiselect("Filter Status", all_status)
        with f3:
            min_d, max_d = df['date_dt'].min(), df['date_dt'].max()
            date_rng = st.date_input("Time Period", value=(min_d, max_d))

    # Apply Filters
    if sel_comps:
        df = df[df['company'].isin(sel_comps)]
    if sel_status:
        df = df[df['status'].isin(sel_status)]
    if isinstance(date_rng, tuple) and len(date_rng) == 2:
        df = df[(df['date_dt'] >= date_rng[0]) & (df['date_dt'] <= date_rng[1])]

    st.divider()

    # --- TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    total_inv = df['amount'].sum()
    total_rec = df['received_amount'].sum()
    total_pen = total_inv - total_rec
    rate = (total_rec / total_inv * 100) if total_inv > 0 else 0

    m1.metric("Gross Invoiced", f"${total_inv:,.0f}")
    m2.metric("Total Collected", f"${total_rec:,.0f}")
    m3.metric("Pending Balance", f"${total_pen:,.0f}", delta=f"{100-rate:.1f}% Unpaid", delta_color="inverse")
    m4.metric("Collection Efficiency", f"{rate:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- CHARTS ROW 1 ---
    g1, g2 = st.columns(2)

    with g1:
        st.subheader("Revenue vs Collection (Monthly)")
        # מיון לפי תאריך כדי שהגרף יזרום כרונולוגית
        monthly = df.groupby(['month_year', pd.to_datetime(df['date_dt']).dt.to_period('M')]).agg({'amount':'sum', 'received_amount':'sum'}).reset_index()
        monthly = monthly.sort_values('date_dt')
        
        fig_rev = px.bar(monthly, x='month_year', y=['amount', 'received_amount'],
                         barmode='group', color_discrete_map={'amount': '#3b82f6', 'received_amount': '#10b981'})
        st.plotly_chart(fig_rev, use_container_width=True)

    with g2:
        st.subheader("Debt Distribution")
        status_sum = df.groupby('status')['amount'].sum().reset_index()
        fig_pie = px.pie(status_sum, names='status', values='amount', hole=0.5,
                         color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # --- ROW 2: AGING & GAUGE ---
    g3, g4 = st.columns(2)

    with g3:
        st.subheader("Top 10 Open Debts by Client")
        debts = df[df['balance'] > 0].groupby('company')['balance'].sum().nlargest(10).reset_index()
        fig_debts = px.bar(debts, x='balance', y='company', orientation='h', color='balance', color_continuous_scale='Reds')
        st.plotly_chart(fig_debts, use_container_width=True)

    with g4:
        st.subheader("Collection Goal Status")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", value = rate,
            gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#1E3A8A"},
                     'steps': [{'range': [0, 70], 'color': "#fee2e2"}, {'range': [70, 90], 'color': "#fef3c7"}, {'range': [90, 100], 'color': "#d1fae5"}]}))
        st.plotly_chart(fig_gauge, use_container_width=True)

else:
    st.info("No data available to generate charts.")

st.divider()
st.caption("Tuesday Analytics Engine | Version 2.1 (Safe Date Parsing)")
