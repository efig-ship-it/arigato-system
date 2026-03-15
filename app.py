import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import re

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Tuesday | Command Center", page_icon="💼", layout="wide")

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

# --- 3. CORE FUNCTIONS ---
def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = df['amount'].astype(float)
        df['received_amount'] = df['received_amount'].astype(float)
        df['balance'] = df['amount'] - df['received_amount']
        # המרת תאריכים בצורה בטוחה
        df['due_date_obj'] = pd.to_datetime(df['due_date']).dt.date
    return df

# --- 4. CSS STYLES (הדגשת צבעים ומיתוג) ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .overdue-card {
        background-color: #FFF5F5; border: 2px solid #FC8181; padding: 20px; border-radius: 12px; text-align: center;
    }
    .forecast-card {
        background-color: #F0FFF4; border: 2px solid #68D391; padding: 20px; border-radius: 12px; text-align: center;
    }
    .last-action-box {
        background-color: #F8FAFC; border-left: 5px solid #1E3A8A; padding: 15px; margin: 20px 0; border-radius: 4px;
    }
    .red-text { color: #E53E3E; font-weight: bold; font-size: 24px; }
    .green-text { color: #38A169; font-weight: bold; font-size: 24px; }
    </style>
""", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

l_pad, home_col, r_pad = st.columns([0.1, 0.8, 0.1])

with home_col:
    st.title("Tuesday Command Center 🏠")
    
    df = get_cloud_history()
    
    if not df.empty:
        # --- חישובי מדדים ---
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        
        # 1. Total Overdue (כל מה שעבר לו התאריך ולא שולם) - אדום
        total_overdue = df[(df['status'] != 'Paid') & (df['due_date_obj'] < today)]['balance'].sum()
        
        # 2. Next 7d Forecast (כל מה שצריך להיפרע בשבוע הקרוב) - ירוק
        forecast_7d = df[(df['status'] != 'Paid') & (df['due_date_obj'] >= today) & (df['due_date_obj'] <= next_week)]['balance'].sum()
        
        # --- תצוגת הקארדים מהתמונה ---
        col_red, col_green = st.columns(2)
        
        with col_red:
            st.markdown(f"""
                <div class="overdue-card">
                    <p style="color: #C53030; font-weight: bold; margin:0;">🚨 Total Overdue</p>
                    <p class="red-text">₪{total_overdue:,.0f}</p>
                </div>
            """, unsafe_allow_html=True)
            
        with col_green:
            st.markdown(f"""
                <div class="forecast-card">
                    <p style="color: #2F855A; font-weight: bold; margin:0;">🟢 Next 7d Forecast</p>
                    <p class="green-text">₪{forecast_7d:,.0f}</p>
                </div>
            """, unsafe_allow_html=True)

        st.divider()

        # --- שליחה אחרונה (Last Action) ---
        last_entry = df.iloc[0] # השורה הראשונה היא הכי חדשה לפי המיון
        st.markdown(f"""
            <div class="last-action-box">
                <p style="margin:0; font-weight:bold; color:#1E3A8A;">🕒 Last Dispatch Activity</p>
                <p style="margin:0; font-size: 18px;">
                    <b>Sender:</b> {last_entry['sender']} | 
                    <b>Client:</b> {last_entry['company']} | 
                    <b>Amount:</b> ₪{last_entry['amount']:,.0f} | 
                    <b>Date:</b> {last_entry['date']}
                </p>
            </div>
        """, unsafe_allow_html=True)

        # --- מדדים כלליים ---
        st.write("### Quick Stats")
        m1, m2, m3 = st.columns(3)
        total_collected = df['received_amount'].sum()
        m1.metric("Total Collected", f"₪{total_collected:,.0f}")
        m2.metric("Active Invoices", len(df[df['status'] != 'Paid']))
        m3.metric("Collection Rate", f"{(total_collected / df['amount'].sum() * 100):.1f}%")

        st.divider()
        st.write("### Recent History")
        st.dataframe(df[['date', 'company', 'amount', 'balance', 'status']].head(10), use_container_width=True, hide_index=True)
        
    else:
        st.info("Waiting for your first invoice dispatch...")

    if st.button("🔄 Sync with Cloud"):
        st.rerun()
