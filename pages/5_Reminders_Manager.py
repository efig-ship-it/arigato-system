import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. חיבור לענן (Supabase) ---
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_overdue_list():
    # שליפת כל הנתונים מהענן כדי למנוע בעיות סנכרון ו-Cache
    res = supabase.table("billing_history").select("*").execute()
    full_df = pd.DataFrame(res.data)
    
    if not full_df.empty:
        # סינון חכם: מחפש 'Overdue' בלי קשר לאותיות גדולות/קטנות
        mask = full_df['status'].str.contains('Overdue', case=False, na=False)
        df = full_df[mask].copy()
        
        if not df.empty:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
            df['balance'] = df['amount'] - df['received_amount']
            return df
    return pd.DataFrame()

# --- 2. עיצוב הממשק ---
st.set_page_config(page_title="Tuesday | Recovery", layout="wide")

st.markdown("""
    <style>
    .recovery-title { font-size: 32px; font-weight: 800; color: #DC2626; margin-bottom: 10px; }
    .stCheckbox { transform: scale(1.2); }
    </style>
""", unsafe_allow_html=True)

t_col, r_col = st.columns([5, 1])
with t_col:
    st.markdown('<p class="recovery-title">Overdue Reminders 🚨</p>', unsafe_allow_html=True)
with r_col:
    if st.button("🔄 Sync Now"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# --- 3. הגדרות שליחה וקובץ מיילים ---
with st.expander("🛠️ Email & Mailing List Setup", expanded=True):
    up_contacts = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("Gmail Address (Sender)")
    gmail_pass = c2.text_input("App Password", type="password")

# --- 4. עיבוד הנתונים והצגת הצ'קלקלה ---
df_ov = get_overdue_list()

if df_ov.empty:
    st.success("Everything is paid! No 'Overdue' transactions found in Cloud. 🎉")
    st.info("If you just updated Page 4, make sure you clicked 'Save' and then click 'Sync Now' here.")
    st.stop()

if up_contacts:
    try:
        # קריאת קובץ אנשי הקשר
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        
        # איתור עמודת מייל וחברה באופן גמיש
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0] # מניח שחברה היא בעמודה הראשונה

        # הצלבת נתוני הגבייה עם המיילים
        df_final = pd.merge(df_ov, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.info(f"Showing {len(df_final)} Overdue transactions found in Cloud")

        # רשימת הבחירה (צ'קלקלה)
        selected_rows = []
        
        # כותרות הטבלה
        h1, h2, h3, h4 = st.columns([0.5, 2, 1.5, 2])
        h2.write("**Company**")
        h3.write("**Balance Due**")
        h4.write("**Contact Email**")

        for idx, row in df_final.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([0.5, 2, 1.5, 2])
                with c1:
                    is_sel = st.checkbox("", key=f"ov_check_{idx}")
                with c2:
                    st.write(row['company'])
                with c3:
                    st.write(f"₪{row['balance']:,.2f}")
                with c4:
                    email_val = row[email_col] if pd.notna(row[email_col]) else "⚠️ Email Not Found"
                    st.write(f"`{email_val}`")
                
                if is_sel:
                    selected_rows.append(row)

        st.divider()

        # --- 5. מנגנון השליחה ---
        if st.button("🚀 SEND SELECTED REMINDERS", use_container_width=True, type="primary"):
            if not selected_rows:
                st.warning("Please select at least one company from the list.")
            elif not gmail_user or not gmail_pass:
                st.error("Please provide Gmail credentials to send emails.")
            else:
                try:
                    # התחברות לשרת Gmail
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

                    prog = st.progress(0)
                    for i, row in enumerate(selected_rows):
                        target = str(row[email_col])
                        if "@" not in target or pd.isna(target):
                            st.warning(f"Skipping {row['company']} - No valid email.")
                            continue

                        # יצירת המייל
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Friendly Reminder: Outstanding Payment - {row['company']}"
                        msg['From'] = gmail_user
                        msg['To'] = target
                        
                        body = f"""
Hello {row['company']} Team,

This is a reminder regarding your outstanding balance of ₪{row['balance']:,.2f}.
Our records show that the payment date has passed.

Please settle the balance or contact us if there's any issue.

Best regards,
Accounts Receivable Team
                        """
                        msg.attach(MIMEText(body, 'plain'))
                        server.send_message(msg)

                        # עדכון הענן: משנים סטטוס ל-Sent Reminder כדי שייצא מהרשימה הנוכחית
                        supabase.table("billing_history").update({
                            "status": "Sent Reminder",
                            "notes": f"Reminder sent on {datetime.now().strftime('%d/%m/%Y')}"
                        }).eq("id", row['id']).execute()
                        
                        prog.progress((i + 1) / len(selected_rows))

                    server.quit()
                    st.balloons()
                    st.success("Reminders sent successfully and Cloud updated!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error sending email: {e}")

    except Exception as e:
        st.error(f"Excel matching error: {e}")
else:
    st.info("Waiting for Mailing List Excel upload...")
