import streamlit as st
import pandas as pd
import time
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. CORE FUNCTIONS (עצמאי למניעת שגיאות Import) ---

@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = df['amount'].astype(float)
        df['received_amount'] = df['received_amount'].astype(float)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_obj'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
    return df

def add_log_entry(record_id, note_text):
    try:
        res = supabase.table("billing_history").select("notes").eq("id", record_id).single().execute()
        current_notes = res.data.get("notes", "") if res.data else ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"[{timestamp}] {note_text}"
        updated_notes = f"{current_notes}\n{new_entry}" if current_notes else new_entry
        supabase.table("billing_history").update({"notes": updated_notes}).eq("id", record_id).execute()
    except: pass

# --- 2. SIDEBAR & CSS ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

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
        font-size: 100px;
        animation: bell-move 1.5s infinite ease-in-out;
    }
    @keyframes bell-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.15) translateY(-20px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Proactive T-7 Alerts 🔔")
    st.write("Prevent delays by reminding clients 7 days before the due date.")
    st.markdown("---")

    # שליפת נתונים אמיתיים מ-Supabase
    df_history = get_cloud_history()
    
    # סינון: רק מה שלא שולם ומועד התשלום קרוב (למשל ב-10 הימים הקרובים)
    today = datetime.now().date()
    future_limit = today + pd.Timedelta(days=10)
    
    df_proactive = df_history[
        (df_history['status'] != 'Paid') & 
        (df_history['due_date_obj'] >= today) & 
        (df_history['due_date_obj'] <= future_limit)
    ].copy()

    if not df_proactive.empty:
        df_proactive['Select'] = False
        st.info(f"Detected **{len(df_proactive)}** upcoming payments in the next 10 days.")
        
        # עריכת הנתונים (בחירת לקוחות)
        sel_data = st.data_editor(
            df_proactive[['Select', 'company', 'due_date', 'balance', 'id']], 
            hide_index=True, 
            use_container_width=True
        )
        
        # פרטי אימות שליחה
        st.subheader("Authentication")
        c1, c2 = st.columns(2)
        u_m = c1.text_input("Gmail Account")
        u_p = c2.text_input("App Password", type="password")
        
        # העלאת אקסל (רשימת תפוצה) לשחרור המיילים
        mf_up = st.file_uploader("Upload Mailing List to match emails", type=['xlsx'])

        # לוגיקת הכפתור
        can_send = (mf_up is not None) and (sel_data['Select'].any()) and u_m and u_p
        
        if st.button("🚀 Send Proactive Reminders", use_container_width=True, disabled=not can_send):
            try:
                # טעינת מיילים מהאקסל
                df_emails = pd.read_excel(mf_up)
                email_map = dict(zip(df_emails.iloc[:, 0].astype(str).str.strip(), df_emails.iloc[:, 1].astype(str).str.strip()))
                
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(u_m.strip(), u_p.strip().replace(" ",""))
                
                sh_up = st.empty()
                with sh_up.container():
                    st.markdown('<div class="bell-container"><div class="big-bell">🛎️</div></div>', unsafe_allow_html=True)
                    
                    to_send = sel_data[sel_data['Select'] == True]
                    for _, row in to_send.iterrows():
                        comp = row['company']
                        due_date_str = row['due_date']
                        
                        if comp in email_map:
                            target_email = email_map[comp]
                            
                            # --- הטמפלט החדש שלך ---
                            body = f"""היי,
רק תזכורת לגבי התשלום שטרם הוסדר אצלנו במערכת, מועד התשלום הינו - {due_date_str}
נשמח אם תוכלו לבדוק ולעדכן אותנו לגבי מועד ההעברה הצפוי.

במידה והתשלום כבר בוצע – בבקשה תצרפו אישור ההעברה ופירוט חשבוניות רלוונטיות. 

תודה רבה על שיתוף הפעולה,
ושיהיה המשך יום מצוין!"""

                            msg = MIMEMultipart()
                            msg['Subject'] = f"תזכורת תשלום - {comp}"
                            msg['From'] = u_m
                            msg['To'] = target_email
                            msg.attach(MIMEText(body, 'plain', 'utf-8'))
                            
                            server.send_message(msg)
                            
                            # עדכון סטטוס והערה ב-Supabase
                            supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                            add_log_entry(row['id'], "Proactive Reminder Sent (T-7 Template)")

                server.quit()
                sh_up.empty()
                st.balloons()
                st.success("All Proactive Reminders Sent!")
                time.sleep(2)
                st.rerun()
                
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.success("No upcoming payments require proactive alerts right now. ☕")

    st.divider()
    st.caption("Proactive alerts help maintain a healthy cash flow by ensuring clients are ready for payment.")
