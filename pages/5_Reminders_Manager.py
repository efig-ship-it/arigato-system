import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. CORE CONNECTION ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_overdue_from_cloud():
    # מושך רק את אלו שבחריגה (עברו מעמוד 4)
    res = supabase.table("billing_history").select("*").eq("status", "Overdue").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
        df['balance'] = df['amount'] - df['received_amount']
    return df

# --- 2. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Recovery", layout="wide")
st.markdown("""
    <style>
    .recovery-title { font-size: 32px; font-weight: 800; color: #DC2626; margin-bottom: 10px; }
    .company-card { background: #FFFFFF; border: 1px solid #F87171; padding: 15px; border-radius: 10px; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="recovery-title">Overdue Reminders (Page 5) 🚨</p>', unsafe_allow_html=True)

# --- 3. MAILING LIST & CREDS ---
with st.expander("🛠️ Email Settings & Mailing List", expanded=True):
    up_contacts = st.file_uploader("Upload Mailing List (Excel with Company & Email)", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("Your Gmail")
    gmail_pass = c2.text_input("App Password", type="password")

# --- 4. PROCESSING DATA ---
df_overdue = get_overdue_from_cloud()

if df_overdue.empty:
    st.success("Clean Slate! No Overdue transactions to handle. ☕")
    st.stop()

if up_contacts:
    try:
        # קריאת קובץ המיילים
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        
        # זיהוי עמודות
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0] # מניח שעמודה ראשונה היא שם חברה

        # הצלבת המיילים לתוך נתוני החריגה
        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.subheader(f"Found {len(df_final)} Transactions in Overdue")
        
        # הצ'קלקלה - רשימת בחירה
        selected_indices = []
        st.markdown("---")
        
        # כותרות לטבלה הויזואלית
        h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
        h2.write("**Company**")
        h3.write("**Amount Outstanding**")
        h4.write("**Target Email**")

        for idx, row in df_final.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([0.5, 2, 2, 2])
                with col1:
                    is_selected = st.checkbox("", key=f"row_{idx}")
                with col2:
                    st.write(row['company'])
                with col3:
                    st.write(f"₪{row['balance']:,.2f}")
                with col4:
                    email_display = row[email_col] if pd.notna(row[email_col]) else "⚠️ Missing Email"
                    st.write(f"`{email_display}`")
                
                if is_selected:
                    selected_indices.append(idx)

        st.divider()

        # --- 5. SENDING ENGINE ---
        if st.button("🚀 EXECUTE REMINDERS (Send to Selected)", use_container_width=True, type="primary"):
            if not selected_indices:
                st.warning("Please select at least one company.")
            elif not gmail_user or not gmail_pass:
                st.error("Missing Gmail credentials.")
            else:
                try:
                    # התחברות לשרת
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

                    prog = st.progress(0)
                    for i, idx in enumerate(selected_indices):
                        row = df_final.iloc[idx]
                        target_email = str(row[email_col])
                        
                        if "@" not in target_email:
                            st.warning(f"Skipping {row['company']} - Invalid email address.")
                            continue

                        # בניית המייל
                        msg = MIMEMultipart()
                        msg['Subject'] = f"FOLLOW UP: Payment Status - {row['company']}"
                        msg['From'] = gmail_user
                        msg['To'] = target_email
                        
                        body = f"""
                        Hello {row['company']} Team,
                        
                        This is a friendly follow-up regarding your outstanding balance of ₪{row['balance']:,.2f}.
                        Our system shows that the payment date has passed.
                        
                        Please let us know if the payment has been sent or if you need any further information.
                        
                        Regards,
                        Accounts Receivable
                        """
                        msg.attach(MIMEText(body, 'plain'))
                        server.send_message(msg)

                        # עדכון סטטוס בענן כדי שלא יופיע שוב בעמוד 5
                        supabase.table("billing_history").update({
                            "status": "Reminder Sent",
                            "notes": f"Reminder triggered via Page 5 on {datetime.now().strftime('%d/%m/%Y')}"
                        }).eq("id", row['id']).execute()

                        prog.progress((i + 1) / len(selected_indices))

                    server.quit()
                    st.balloons()
                    st.success("All selected reminders sent successfully!")
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"SMTP Error: {e}")

    except Exception as e:
        st.error(f"Error processing contacts: {e}")
else:
    st.info("Waiting for Mailing List Excel to match contacts...")

# כפתור חזרה
if st.button("Back to Control (Page 4)"):
    st.switch_page("pages/4_Operations_Control.py")
