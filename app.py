import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Tuesday | Command Center", page_icon="💼", layout="wide")

# --- 2. DATABASE CONNECTION ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

# --- 3. DATA FETCHING ---
def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = df['amount'].astype(float)
        df['received_amount'] = df['received_amount'].astype(float)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_obj'] = pd.to_datetime(df['due_date']).dt.date
    return df

# --- 4. CSS STYLES ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .overdue-card {
        background-color: #FFF5F5; border: 2px solid #FC8181; padding: 25px; border-radius: 15px; text-align: center;
    }
    .forecast-card {
        background-color: #F0FFF4; border: 2px solid #68D391; padding: 25px; border-radius: 15px; text-align: center;
    }
    .last-action-box {
        background-color: #F1F5F9; border-right: 5px solid #1E3A8A; padding: 20px; margin-bottom: 30px; border-radius: 10px;
        direction: rtl; text-align: right; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .red-val { color: #E53E3E; font-weight: bold; font-size: 36px; margin: 0; }
    .green-val { color: #38A169; font-weight: bold; font-size: 36px; margin: 0; }
    .metric-label { color: #4A5568; font-weight: bold; font-size: 16px; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

l_pad, home_col, r_pad = st.columns([0.1, 0.8, 0.1])

with home_col:
    st.title("Tuesday Dashboard 🏠")
    
    df = get_cloud_history()
    
    if not df.empty:
        # --- חישובי מדדים ---
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        
        total_invoiced = df['amount'].sum()
        total_received = df['received_amount'].sum()
        reminders_sent = len(df[df['status'] == 'Reminder Sent'])
        
        total_overdue = df[(df['status'] != 'Paid') & (df['due_date_obj'] < today)]['balance'].sum()
        forecast_7d = df[(df['status'] != 'Paid') & (df['due_date_obj'] >= today) & (df['due_date_obj'] <= next_week)]['balance'].sum()

        # שורת פעילות אחרונה (בלי הרשימה למטה)
        last_entry = df.iloc[0]
        st.markdown(f"""
            <div class="last-action-box">
                <span style="font-size: 18px;">🕒 <b>פעילות אחרונה במערכת:</b></span><br>
                השולח: <b>{last_entry.get('sender', 'System')}</b> | 
                לקוח: <b>{last_entry['company']}</b> | 
                סכום: <b>₪{last_entry['amount']:,.0f}</b> | 
                בתאריך: <b>{last_entry['date']}</b>
            </div>
        """, unsafe_allow_html=True)

        # תצוגת הקארדים המודגשים (אדום וירוק)
        col_red, col_green = st.columns(2)
        with col_red:
            st.markdown(f"""
                <div class="overdue-card">
                    <p class="metric-label">🚨 Total Overdue</p>
                    <p class="red-val">₪{total_overdue:,.0f}</p>
                </div>
            """, unsafe_allow_html=True)
        with col_green:
            st.markdown(f"""
                <div class="forecast-card">
                    <p class="metric-label">🟢 Next 7d Forecast</p>
                    <p class="green-val">₪{forecast_7d:,.0f}</p>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # מדדי סיכום (Metrics)
        st.subheader("📊 סיכום פיננסי")
        m1, m2, m3 = st.columns(3)
        m1.metric("סה\"כ נשלח לגבייה", f"₪{total_invoiced:,.0f}")
        m2.metric("סה\"כ התקבל (שולם)", f"₪{total_received:,.0f}", delta=f"{(total_received/total_invoiced*100):.1f}%")
        m3.metric("תזכורות שנשלחו", f"{reminders_sent}")

    else:
        st.info("אין נתונים זמינים כרגע. התחל לשלוח חשבוניות כדי לראות את הדשבורד.")

    st.divider()
    if st.button("🔄 רענן וסנכרן נתונים"):
        st.rerun()
