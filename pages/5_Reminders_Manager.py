import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. CORE CONNECTION ---
# ה-init_connection נשאר עם cache_resource כדי לא לפתוח אלף חיבורים לענן
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

# כאן הורדנו את ה-Cache כדי שכל פעם שתעבור לעמוד הזה, הוא יבדוק מה המצב בענן
def get_overdue_from_cloud():
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
    </style>
""", unsafe_allow_html=True)

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.markdown('<p class="recovery-title">Overdue Reminders (Page 5) 🚨</p>', unsafe_allow_html=True)
with col_refresh:
    if st.button("🔄 Refresh Data"):
        st.rerun()

# --- 3. INPUTS ---
with st.expander("🛠️ Email Settings & Contacts", expanded=True):
    up_contacts = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("Your Gmail")
    gmail_pass = c2.text_input("App Password", type="password")

# --- 4. LOGIC ---
df_overdue = get_overdue_from_cloud()

if df_overdue.empty:
    st.success("Clean Slate! No Overdue transactions to handle. ☕")
    st.stop()

if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]

        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.subheader(f"Found {len(df_final)} Overdue Transactions")
        
        selected_indices = []
        st.markdown("---")
        
        # כותרות הטבלה (צ'קלקלה)
        h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
        h2.write("**Company**")
        h3.write("**Balance**")
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

        if st.button("🚀 EXECUTE REMINDERS", use_container_width=True, type="primary"):
            if not selected_indices:
                st.warning("Please select at least one row.")
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
                        
                        body = f"Hello {row['company']} Team,\n\nOur records show an unpaid balance of ₪{row['balance']:,.2f}.\n\nPlease update us on the status.\n\nRegards,"
                        msg.attach(MIMEText(body, 'plain'))
                        server.send_message(msg)

                        # עדכון הענן: משנים סטטוס כדי שיצא מרשימת ה-Overdue הפשוטה
                        supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()

                        prog.progress((i + 1) / len(selected_indices))

                    server.quit()
                    st.balloons()
                    st.success("Reminders sent and Cloud Updated!")
                    time.sleep(1); st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Upload Mailing List to start.")
