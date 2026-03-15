import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from app import get_cloud_history, supabase

# --- PAGE CONFIG ---
st.set_page_config(page_title="Tuesday | Business Intelligence", page_icon="📈", layout="wide")

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.title("Business Intelligence & Analytics 📊")

# --- CSS FOR PREMIUM LOOK ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .metric-container {
        background-color: #ffffff; padding: 20px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

# 1. LOAD DATA
df = get_cloud_history()

if not df.empty:
    # --- DATA PREP ---
    df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True).dt.date
    df['month_year'] = pd.to_datetime(df['date'], dayfirst=True).dt.strftime('%b %Y')
    
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
            min_date = df['date_dt'].min()
            max_date = df['date_dt'].max()
            date_rng = st.date_input("Time Period", value=(min_date, max_date))

    # Apply Filters
    filtered_df = df.copy()
    if sel_comps:
        filtered_df = filtered_df[filtered_df['company'].isin(sel_comps)]
    if sel_status:
        filtered_df = filtered_df[filtered_df['status'].isin(sel_status)]
    if isinstance(date_rng, tuple) and len(date_rng) == 2:
        filtered_df = filtered_df[(filtered_df['date_dt'] >= date_rng[0]) & (filtered_df['date_dt'] <= date_rng[1])]

    st.divider()

    # --- TOP METRICS ---
    m1, m2, m3, m4 = st.columns(4)
    total_inv = filtered_df['amount'].sum()
    total_rec = filtered_df['received_amount'].sum()
    total_pen = total_inv - total_rec
    rate = (total_rec / total_inv * 100) if total_inv > 0 else 0

    m1.metric("Gross Invoiced", f"${total_inv:,.0f}")
    m2.metric("Total Collected", f"${total_rec:,.0f}")
    m3.metric("Pending (Debt)", f"${total_pen:,.0f}", delta=f"{100-rate:.1f}% Unpaid", delta_color="inverse")
    m4.metric("Collection Efficiency", f"{rate:.1f}%")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- MAIN GRAPHS: ROW 1 ---
    g1, g2 = st.columns([1, 1])

    with g1:
        st.subheader("Monthly Revenue Stream ($)")
        # קיבוץ לפי חודש לגרף עמודות
        monthly = filtered_df.groupby('month_year')[['amount', 'received_amount']].sum().reset_index()
        fig_revenue = px.bar(monthly, x='month_year', y=['amount', 'received_amount'],
                             barmode='group', labels={'value': 'Amount ($)', 'month_year': 'Month'},
                             color_discrete_map={'amount': '#3b82f6', 'received_amount': '#10b981'})
        fig_revenue.update_layout(legend_title_text='Type')
        st.plotly_chart(fig_revenue, use_container_width=True)

    with g2:
        st.subheader("Collection Breakdown (Status)")
        # גרף עוגה של סכומי הסטטוסים
        status_sum = filtered_df.groupby('status')['amount'].sum().reset_index()
        fig_status = px.pie(status_sum, names='status', values='amount',
                            hole=0.5, color='status',
                            color_discrete_map={'Paid': '#10b981', 'Overdue': '#ef4444', 'Sent': '#3b82f6', 'Partial': '#f59e0b'})
        st.plotly_chart(fig_status, use_container_width=True)

    st.divider()

    # --- MAIN GRAPHS: ROW 2 ---
    g3, g4 = st.columns([1, 1])

    with g3:
        st.subheader("Aging Report (Top 10 Debts)")
        # הצגת הלקוחות עם החוב הגבוה ביותר
        debts = filtered_df[filtered_df['balance'] > 0].groupby('company')['balance'].sum().nlargest(10).reset_index()
        fig_debts = px.bar(debts, x='balance', y='company', orientation='h',
                           text_auto='.2s', color='balance', color_continuous_scale='Reds')
        fig_debts.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_debts, use_container_width=True)

    with g4:
        st.subheader("Collection vs. Goal")
        # גרף Gauge שמראה אחוז גבייה
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = rate,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Collection Rate %"},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#1E3A8A"},
                'steps': [
                    {'range': [0, 50], 'color': "#fee2e2"},
                    {'range': [50, 80], 'color': "#fef3c7"},
                    {'range': [80, 100], 'color': "#d1fae5"}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 95}
            }
        ))
        st.plotly_chart(fig_gauge, use_container_width=True)

    # --- DATA TABLE VIEW ---
    st.subheader("Detailed Analytics Data")
    st.dataframe(filtered_df[['company', 'date', 'amount', 'received_amount', 'balance', 'status']].sort_values(by='amount', ascending=False), 
                 use_container_width=True, hide_index=True)

else:
    st.info("No data available to generate charts. Start by uploading invoices.")

st.divider()
if st.button("🔄 Reload Engine"):
    st.rerun()
