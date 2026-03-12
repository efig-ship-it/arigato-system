import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app import get_cloud_history, supabase

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS & AUDIO SCRIPT ---
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
        box-shadow: 0 0 30px rgba(255, 0, 0, 0.8);
        animation: police-flash 0.3s linear infinite, suitcase-move 1.5s infinite ease-in-out;
    }
    @keyframes police-flash { 0% { background-position: 0% 50%; } 100% { background-position: 100% 50%; } }
    @keyframes suitcase-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.15) translateY(-30px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
    
    <script>
    function playSiren() {
        var audio = new Audio('https://www.soundjay.com/buttons/beep-01a.mp3'); // צליל ביפ/סירנה
        audio.play();
    }
    </script>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Reminders Manager 🚨")
    
    # --- 1. LOAD DATA ---
    st.subheader("1. Load Mailing List & Overdue Data")
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    
    df_history = get_cloud_history()

    if df_history.empty:
        st.info("No billing history found.")
    else:
        today = datetime.now().date()
        overdue_df = df_history[(df_history['status'] != 'Paid') & (df_history['due_date_obj'] < today)].copy()

        if overdue_df.empty:
            st.success("All clear! No overdue payments. ☕")
        else:
            st.warning(f"🚨 ALERT: {len(overdue_df)} Overdue Invoices.")
            
            overdue_df['Select'] = True
            edited_df = st.data_editor(
                overdue_df[['Select', 'company', 'amount', 'due_date', 'balance']],
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=["company", "amount", "due_date", "balance"],
                hide_index=True, use_container_width=True
            )

            st.divider()

            # --- 2. AUTHENTICATION ---
            st.subheader("2. Execute Collection")
            c_auth, c_guide = st.columns([1.5, 1])
            with c_auth:
                u_m = st.text_input("Gmail Account")
                u_p = st.text_input("App Password", type="password")
            with c_guide:
                with st.expander("🔐 Guide"):
                    st.markdown("[Google App Passwords](https://myaccount.google.com/apppasswords)")

            # --- EXECUTE ---
            if st.button("🚨 EXECUTE COLLECTION DISPATCH", use_container_width=True):
                selected = edited_df[edited_df['Select'] == True]
                
                if selected.empty or not u_m or not u_p or not up_ex:
                    st.error("Please fill all details.")
                else:
                    # הפעלת הצליל באמצעות JS
                    st.components.v1.html("<script>parent.playSiren();</script>", height=0)
                    
                    try:
                        df_mails = pd.read_excel(up_ex)
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                        server.login(u_m.strip(), u_p.strip().replace(" ",""))
                        
                        status_msg = st.empty() 
                        
                        for i, row in selected.iterrows():
                            comp = row['company']
                            # מציאת מייל
                            try:
                                client_email_row = df_mails[df_mails.iloc[:, 0].str.contains(comp, case=False, na=False)]
                                recipient_email = str(client_email_row.iloc[0, 1])
                            except: recipient_email = None

                            if not recipient_email or "@" not in recipient_email: continue

                            dt_obj = datetime.strptime(str(row['due_date']), "%Y-%m-%d")
                            month_name = dt_obj.strftime("%B")
                            year_val = dt_obj.year
                            
                            # הצגת הצ'קלקה הרוקדת
                            with status_msg.container():
                                st.markdown('<div class="police-container"><div class="big-police-light"></div></div>', unsafe_allow_html=True)
                                st.write(f"🕵️‍♂️ **Collecting from:** {comp}...")
                            
                            # שליחת מייל (טמפלט עברית)
                            email_body = f"שלום,\nנכון להיום, התשלום עבור חודש {month_name} {year_val} טרם הוסדר..."
                            msg = MIMEMultipart()
                            msg['Subject'] = f"דרישת תשלום מיידית - {comp}"
                            msg['To'] = recipient_email
                            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
                            server.send_message(msg)
                            
                            supabase.table("billing_history").update({"status": "Reminder Sent"}).eq("company", comp).eq("due_date", row['due_date']).execute()
                            time.sleep(1) 
                        
                        server.quit()
                        status_msg.empty() 
                        st.balloons()
                        st.success("Reminders sent!")
                        time.sleep(2); st.rerun()
                        
                    except Exception as e: st.error(f"Error: {e}")
