import streamlit as st
import pandas as pd
import smtplib, time, base64
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app import get_cloud_history, supabase

# --- פונקציית הזרקת סאונד עוקפת חסימות ---
def play_siren_forcefully():
    audio_url = "https://www.soundjay.com/misc/sounds/siren-1.mp3"
    audio_html = f"""
        <iframe src="{audio_url}" allow="autoplay" style="display:none" id="iframeAudio">
        </iframe>
        <audio autoplay>
            <source src="{audio_url}" type="audio/mp3">
        </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS (מיתוג Tuesday + צ'קלקה רוקדת) ---
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
        width: 260px; height: 80px;
        background: linear-gradient(90deg, #ff0000, #0000ff, #ff0000, #0000ff);
        background-size: 300% 300%;
        border-radius: 40px;
        box-shadow: 0 0 50px rgba(255, 0, 0, 0.9);
        animation: police-flash 0.2s linear infinite, suitcase-move 1.5s infinite ease-in-out;
    }
    @keyframes police-flash { 0% { background-position: 0% 50%; } 100% { background-position: 100% 50%; } }
    @keyframes suitcase-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.1) translateY(-30px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT (ריכוז לאורך) ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Reminders Manager 🚨")
    
    # --- 1. LOAD DATA & MAILING LIST ---
    st.subheader("1. Load Mailing List & Overdue Data")
    up_ex = st.file_uploader("Upload Mailing List (Excel) to sync emails", type=['xlsx'])
    
    df_history = get_cloud_history()

    if df_history.empty:
        st.info("No billing history found in the cloud.")
    else:
        today = datetime.now().date()
        overdue_df = df_history[(df_history['status'] != 'Paid') & (df_history['due_date_obj'] < today)].copy()

        if overdue_df.empty:
            st.success("All clear! No overdue payments. ☕")
        else:
            st.warning(f"🚨 ALERT: {len(overdue_df)} Overdue Invoices Detected!")
            
            overdue_df['Select'] = True
            edited_df = st.data_editor(
                overdue_df[['Select', 'company', 'amount', 'due_date', 'balance']],
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=["company", "amount", "due_date", "balance"],
                hide_index=True, use_container_width=True
            )

            st.divider()

            # --- 2. AUTHENTICATION & GUIDE (Side-by-Side) ---
            st.subheader("2. Execute Collection")
            
            c_auth, c_guide = st.columns([1.5, 1], gap="medium")
            with c_auth:
                u_m = st.text_input("Gmail Account (Sender)")
                u_p = st.text_input("App Password", type="password")
            with c_guide:
                with st.expander("🔐 Password Guide", expanded=True):
                    st.markdown("[Google App Passwords](https://myaccount.google.com/apppasswords)")

            # --- EXECUTE ---
            if st.button("🚨 EXECUTE COLLECTION DISPATCH", use_container_width=True):
                selected = edited_df[edited_df['Select'] == True]
                
                if selected.empty or not u_m or not u_p or not up_ex:
                    st.error("Missing selection, credentials, or Mailing List Excel.")
                else:
                    # הפעלת הסאונד ברגע הלחיצה
                    play_siren_forcefully()
                    
                    try:
                        df_mails = pd.read_excel(up_ex)
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                        server.login(u_m.strip(), u_p.strip().replace(" ",""))
                        
                        status_msg = st.empty() 
                        
                        for i, row in selected.iterrows():
                            comp = row['company']
                            
                            # שליפת מייל לקוח מהאקסל
                            try:
                                client_email_row = df_mails[df_mails.iloc[:, 0].str.contains(comp, case=False, na=False)]
                                recipient_email = str(client_email_row.iloc[0, 1])
                            except: recipient_email = None

                            if not recipient_email or "@" not in recipient_email:
                                continue

                            # חילוץ חודש ושנה לטמפלט
                            dt_obj = datetime.strptime(str(row['due_date']), "%Y-%m-%d")
                            month_name = dt_obj.strftime("%B")
                            year_val = dt_obj.year
                            
                            # הצגת הצ'קלקה הרוקדת
                            with status_msg.container():
                                st.markdown('<div class="police-container"><div class="big-police-light"></div></div>', unsafe_allow_html=True)
                                st.write(f"🕵️‍♂️ **Tuesday is collecting from:** {comp}...")
                            
                            # בניית המייל (טמפלט עברית)
                            email_body = f"""שלום,
נכון להיום, התשלום עבור חודש {month_name} {year_val} טרם הוסדר, וזאת על אף שמועד התשלום חלף.
דוח חשבוניות פתוחות לתשלום נשלח בתחילת החודש.

אנא הסדירו את התשלום באופן מיידי ועדכנו אותנו עם ביצוע ההעברה.
אי־הסדרת התשלום עלולה להוביל לסגירת החשבון ולהפסקת השירות.

במידה והתשלום בוצע בימים האחרונים, אנא שלחו אישור העברה ופירוט חשבוניות רלוונטיות.

בברכה,
Tuesday Team"""

                            msg = MIMEMultipart()
                            msg['Subject'] = f"דרישת תשלום מיידית - {comp}"
                            msg['To'] = recipient_email
                            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
                            server.send_message(msg)
                            
                            # עדכון דאטה בייס
                            supabase.table("billing_history").update({"status": "Reminder Sent"}).eq("company", comp).eq("due_date", row['due_date']).execute()
                            time.sleep(1.5) # השהייה קלה לסנכרון האנימציה
                        
                        server.quit()
                        status_msg.empty() 
                        st.balloons()
                        st.success("Reminders sent successfully!")
                        time.sleep(2); st.rerun()
                        
                    except Exception as e: st.error(f"Error: {e}")
