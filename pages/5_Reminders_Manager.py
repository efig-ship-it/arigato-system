import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. CORE CONNECTION ---
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_overdue_data():
    # שליפת נתונים ישירה מהענן ללא פילטרים מורכבים כדי למנוע טעויות סנכרון
    res = supabase.table("billing_history").select("*").execute()
    full_df = pd.DataFrame(res.data)
    
    if not full_df.empty:
        # ניקוי עמודת הסטטוס לצרכי חיפוש בלבד
        full_df['status_check'] = full_df['status'].astype(str).str.strip().str.lower()
        
        # סינון: מציג רק את אלו שבסטטוס overdue
        df = full_df[full_df['status_check'] == 'overdue'].copy()
        
        if not df.empty:
            # חישובי יתרה
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
            df['balance'] = df['amount'] - df['received_amount']
            return df
    return pd.DataFrame()

# --- 2. UI STYLE ---
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
    if st.button("🔄 Sync with Cloud"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# --- 3. MAILING LIST & CREDS ---
with st.expander("🛠️ Email Settings & Mailing List", expanded=True):
    up_contacts = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("Your Gmail")
    gmail_pass = c2.text_input("App Password", type="password")

# --- 4. PROCESSING ---
df_overdue = get_overdue_data()

if df_overdue.empty:
    st.success("Clean Slate! No 'Overdue' transactions found in Cloud. ☕")
    st.info("Tip: Ensure the status on Page 4 is set exactly to 'Overdue' and saved.")
    st.stop()

if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        
        # איתור עמודות
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]

        # הצלבת המיילים
        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.subheader(f"Found {len(df_final)} Overdue Transactions")
        
        # הצ'קלקלה
        selected_indices = []
        st.markdown("---")
        
        h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
        h2.write("**Company**")
        h3.write("**Balance Outstanding**")
        h4.write("**Email**")

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
                    email_display = row[email_col] if pd.notna(row[email_col]) else "⚠️ No Email"
                    st.write(f"`{email_display}`")
                
                if is_selected:
                    selected_indices.append(idx)

        st.divider()

        # --- 5. SENDING ---
        if st.button("🚀 EXECUTE REMINDERS", use_container_width=True, type="primary"):
            if not selected_indices:
                st.warning("Please select at least one company.")
            elif not gmail_user or not gmail_pass:
                st.error("Missing Gmail credentials.")
            else:
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

                    prog = st.progress(0)
                    for i, idx in enumerate(selected_indices):
                        row = df_final.iloc[idx]
                        target_email = str(row[email_col])
                        if "@" not in target_email: continue

                        msg = MIMEMultipart()
                        msg['Subject'] = f"FOLLOW UP: Payment Status - {row['company']}"
                        msg['To'] = target_email
                        body = f"Hello {row['company']} Team,\n\nOur system shows an unpaid balance of ₪{row['balance']:,.2f}.\n\nRegards,"
                        msg.attach(MIMEText(body, 'plain'))
                        server.send_message(msg)

                        # עדכון הענן: הופך ל-'Sent Reminder' כדי שייצא מהרשימה הנוכחית
                        supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                        prog.progress((i + 1) / len(selected_indices))

                    server.quit()
                    st.balloons()
                    st.success("Reminders sent! Data synced with Cloud.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    except Exception as e:
        st.error(f"Excel Error: {e}")
else:
    st.info("Waiting for Mailing List to start.")
