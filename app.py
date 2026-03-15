import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import re
import time

# --- 1. CONFIG & CONNECTION ---
st.set_page_config(page_title="Tuesday | Dashboard", page_icon="💼", layout="wide")

@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

# --- 2. DATA FETCHING ---
def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # המרת תאריכים והוספת עמודת יתרה
        df['due_date_obj'] = pd.to_datetime(df['due_date']).dt.date
        # וודא שהעמודות הן מסוג מספר
        df['amount'] = df['amount'].astype(float)
        df['received_amount'] = df['received_amount'].astype(float)
        df['balance'] = df['amount'] - df['received_amount']
    return df

# --- 3. UI BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .metric-box {
        background-color: #f1f5f9;
        padding: 20px;
        border-radius: 12px;
        border-right: 5px solid #1E3A8A;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. MAIN DASHBOARD ---
l_pad, home_col, r_pad = st.columns([0.1, 0.8, 0.1])

with home_col:
    st.title("Tuesday Business Overview 🏠")
    
    df_history = get_cloud_history()
    
    if not df_history.empty:
        # חישוב המספרים שביקשת
        total_invoiced = df_history['amount'].sum()
        total_received = df_history['received_amount'].sum()
        total_pending = df_history['balance'].sum()
        
        # תצוגת המדדים בראש הדף
        st.write("### Financial Performance")
        m1, m2, m3 = st.columns(3)
        
        with m1:
            st.markdown('<div class="metric-box">', unsafe_allow_html=True)
            st.metric("Total Invoiced", f"₪{total_invoiced:,.0f}")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with m2:
            st.markdown('<div class="metric-box">', unsafe_allow_html=True)
            # כמה קיבלנו - המדד שביקשת להוסיף
            st.metric("Total Received", f"₪{total_received:,.0f}", 
                      delta=f"{ (total_received/total_invoiced)*100:.1f}% Collected", delta_color="normal")
            st.markdown('</div>', unsafe_allow_html=True)
            
        with m3:
            st.markdown('<div class="metric-box">', unsafe_allow_html=True)
            st.metric("Pending Balance", f"₪{total_pending:,.0f}", delta_color="inverse")
            st.markdown('</div>', unsafe_allow_html=True)
            
        st.divider()
        
        # טבלה של הפעולות האחרונות
        st.write("### Recent Invoices")
        st.dataframe(
            df_history[['date', 'company', 'amount', 'received_amount', 'balance', 'status']].head(15),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No data available yet. Start by sending your first invoice!")

    if st.button("Refresh All Data"):
        st.rerun()
