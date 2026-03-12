import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app import get_cloud_history, supabase

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS (The Dancing Bell) ---
st.markdown("""
    <style>
    .bell-container {
        display: flex; justify-content: center; align-items: center; 
        padding: 40px; margin: 10px 0;
    }
    .big-bell {
        font-size: 100px;
        animation: bell-move 1.5s infinite ease-in-out;
    }
    @keyframes bell-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.1) translateY(-20px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Upcoming Alerts 🔔")
    st.markdown("---")

    # הצגת הפעמון כספינר מרכזי
    status_placeholder = st.empty()
    with status_placeholder.container():
        st.markdown('<div class="bell-container"><div class="big-bell">🛎️</div></div>', unsafe_allow_html=True)
        with st.spinner("Tuesday is checking upcoming tasks..."):
            df_history = get_cloud_history()
            time.sleep(1) # השהייה קלה לצורך האנימציה

    if df_history.empty:
        st.info("No data available.")
    else:
        # לוגיקה פשוטה: מציגת את כל מה שטרם שולם
        st.subheader("Unpaid Invoices Status")
        unpaid_df = df_history[df_history['status'] != 'Paid'].copy()
        
        if unpaid_df.empty:
            st.success("All invoices are paid! ☕")
        else:
            st.dataframe(unpaid_df[['date', 'company', 'amount', 'due_date', 'status']], use_container_width=True)

    st.divider()
    if st.button("Refresh Board", use_container_width=True):
        st.rerun()
