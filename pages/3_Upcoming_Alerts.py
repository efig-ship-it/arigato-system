import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app import get_cloud_history, supabase

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS (The Dancing Reception Bell) ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    
    .bell-container {
        display: flex; justify-content: center; align-items: center; 
        padding: 50px; margin: 20px 0;
    }
    
    .big-bell {
        font-size: 100px;
        animation: bell-move 1.5s infinite ease-in-out;
    }
    
    @keyframes bell-move {
        0% { transform: scale(1) translateY(0) rotate(0deg); }
        25% { transform: rotate(10deg); }
        50% { transform: scale(1.15) translateY(-20px) rotate(-10deg); }
        75% { transform: rotate(10deg); }
        100% { transform: scale(1) translateY(0) rotate(0deg); }
    }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Upcoming Alerts & Status 🔔")
    st.write("Keep track of invoices reaching their due date in the next 7 days.")
    st.markdown("---")

    # הצגת הפעמון הרוקד בזמן טעינת הנתונים
    status_placeholder = st.empty()
    with status_placeholder.container():
        st.markdown('<div class="bell-container"><div class="big-bell">🛎️</div></div>', unsafe_allow_html=True)
        with st.spinner("Tuesday is checking the schedule..."):
            df_history = get_cloud_history()
            
    # ניקוי הפעמון לאחר הטעינה (או השארתו אם תרצה)
    status_placeholder.empty()

    if df_history.empty:
        st.info("No data available to track.")
    else:
        # לוגיקה: סינון חשבוניות שמועד פירעונן בשבוע הקרוב
        today = datetime.now().date()
        next_week = today + timedelta(days=7)
        
        upcoming_df = df_history[
            (df_history['status'] != 'Paid') & 
            (df_history['due_date_obj'] >= today) & 
            (df_history['due_date_obj'] <= next_week)
        ].copy()

        if upcoming_df.empty:
            st.success("Relax! No urgent due dates in the next 7 days. ☕")
        else:
            st.warning(f"Attention: {len(upcoming_df)} Invoices are due soon!")
            
            # הצגת הנתונים בפורמט יוקרתי
            for _, row in upcoming_df.iterrows():
                days_left = (row['due_date_obj'] - today).days
                with st.expander(f"📅 {row['company']} | Due in {days_left} days", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Amount", f"${row['amount']:,.2f}")
                    c2.metric("Due Date", row['due_date'])
                    c3.metric("Status", row['status'])
                    
    st.divider()
    
    # כפתור רענון עם אנימציה
    if st.button("🔔 Refresh Status Board", use_container_width=True):
        st.rerun()
