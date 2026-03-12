import streamlit as st
import pandas as pd
import time
from app import get_cloud_history, supabase

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS (The Bell - Same size and motion as the Suitcase) ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    
    .bell-container {
        display: flex; justify-content: center; align-items: center; 
        padding: 40px; margin: 20px 0;
    }
    
    .big-bell {
        font-size: 100px; /* אותו גודל כמו המזוודה */
        animation: bell-move 1.5s infinite ease-in-out;
    }
    
    @keyframes bell-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.15) translateY(-20px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Proactive T-7 Alerts 🔔")
    st.write("Prevent delays by reminding clients 7 days before the due date.")
    st.markdown("---")

    # נתוני דוגמה/שליפה לפי המבנה שלך
    test_due = "2026-03-15"
    test_data = pd.DataFrame([
        {'Select': False, 'company': 'ARBITRIP', 'due_date': test_due, 'balance': 4500.0, 'id': 7771},
        {'Select': False, 'company': 'ARBITRIP', 'due_date': test_due, 'balance': 2300.0, 'id': 7772}
    ])

    st.info(f"Proactive Reminders for: **{test_due}**")
    
    # עריכת הנתונים (בחירת לקוחות)
    sel_up = st.data_editor(test_data, hide_index=True, use_container_width=True)
    
    # העלאת אקסל לשחרור הנעילה
    mf_up = st.file_uploader("Upload Mailing List to unlock", type=['xlsx'], key="up_f")

    # לוגיקת הכפתור
    can_send_up = (mf_up is not None) and (sel_up['Select'].any())
    
    if st.button("🚀 Send Proactive Reminders", use_container_width=True, disabled=not can_send_up):
        sh_up = st.empty()
        with sh_up.container():
            # ספינר הפעמון הגדול
            st.markdown('<div class="bell-container"><div class="big-bell">🛎️</div></div>', unsafe_allow_html=True)
            with st.spinner("Ringing the Proactive Bell..."):
                time.sleep(2) # זמן האנימציה
                
        sh_up.empty()
        st.balloons()
        st.success("Proactive Reminders Sent Successfully!")
        time.sleep(1)
        st.rerun()

    st.divider()
    st.caption("Proactive alerts help maintain a healthy cash flow by ensuring clients are ready for payment.")
