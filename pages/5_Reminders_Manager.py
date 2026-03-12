import streamlit as st
import pandas as pd
import smtplib, time, base64
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app import get_cloud_history, supabase

# פונקציית עזר להמרת אודיו לפורמט שסטרימליט יכול להזריק
def get_audio_html(url):
    return f"""
        <audio autoplay="true" style="display:none;">
            <source src="{url}" type="audio/mp3">
        </audio>
    """

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .police-container {
        display: flex; justify-content: center; align-items: center; 
        padding: 40px; margin: 20px 0;
    }
    .big-police-light {
        width: 200px; height: 60px;
        background: linear-gradient(90deg, #ff0000, #0000ff, #ff0000, #0000ff);
        background-size: 300% 300%;
        border-radius: 30px;
        box-shadow: 0 0 35px rgba(255, 0, 0, 0.9);
        animation: police-flash 0.2s linear infinite, suitcase-move 1.5s infinite ease-in-out;
    }
    @keyframes police-flash { 0% { background-position: 0% 50%; } 100% { background-position: 100% 50%; } }
    @keyframes suitcase-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.15) translateY(-30px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Reminders Manager 🚨")
    
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    df_history = get_cloud_history()

    if not df_history.empty:
        today = datetime.now().date()
        overdue_df = df_history[(df_history['status'] != 'Paid') & (df_history['due_date_obj'] < today)].copy()

        if not overdue_df.empty:
            st.warning(f"🚨 ALERT: {len(overdue_df)} Overdue Invoices.")
            overdue_df['Select'] = True
            edited_df = st.data_editor(
                overdue_df[['Select', 'company', 'amount', 'due_date', 'balance']],
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=["company", "amount", "due_date", "balance"],
                hide_index=True, use_container_width=True
            )

            st.divider()
            st.subheader("2. Execute Collection")
            c_auth, c_guide = st.columns([1.5, 1])
            with c_auth:
                u_m = st.text_input("Gmail Account")
                u_p = st.text_input("App Password", type="password")
            
            # --- EXECUTE ---
            if st.button("🚨 EXECUTE COLLECTION DISPATCH", use_container_width=True):
                selected = edited_df[edited_df['Select'] == True]
                
                if not selected.empty and u_m and u_p and up_ex:
                    # הזרקת הסאונד ישירות לתוך ה-Main App ברגע הלחיצה
                    st.markdown(get_audio_html("https://www.soundjay.com/misc/sounds/siren-1.mp3"), unsafe_allow_html=True)
                    
                    try:
                        df_mails = pd.read_excel(up_ex)
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                        server.login(u_m.strip(), u_p.strip().replace(" ",""))
                        
                        status_msg = st.empty() 
                        for i, row in selected.iterrows():
                            comp = row['company']
                            with status_msg.container():
                                st.markdown('<div class="police-container"><div class="big-police-light"></div></div>', unsafe_allow_html=True)
                                st.write(f"🕵️‍♂️ **Collecting from:** {comp}...")
                            
                            # (כאן בא קוד השליחה הרגיל שלך...)
                            time.sleep(1) # סימולציה של זמן שליחה
                        
                        server.quit()
                        st.balloons()
                        st.success("Done!")
                        time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
