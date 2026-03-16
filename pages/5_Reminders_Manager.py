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
    res = supabase.table("billing_history").select("*").execute()
    full_df = pd.DataFrame(res.data)
    if not full_df.empty:
        full_df['status_check'] = full_df['status'].astype(str).str.strip().str.lower()
        df = full_df[full_df['status_check'] == 'overdue'].copy()
        if not df.empty:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
            df['balance'] = df['amount'] - df['received_amount']
            return df
    return pd.DataFrame()

# --- 2. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Reminders", layout="wide")

st.markdown("""
    <style>
    .recovery-title { font-size: 32px; font-weight: 800; color: #DC2626; margin-bottom: 20px; }
    .stCheckbox { transform: scale(1.2); }
    </style>
""", unsafe_allow_html=True)

# Title & Sync
t_col, r_col = st.columns([5, 1])
with t_col:
    st.markdown('<p class="recovery-title">Payment Reminders Center 🚨</p>', unsafe_allow_html=True)
with r_col:
    if st.button("🔄 Sync Data"):
        st.cache_data.clear()
        st.rerun()

# --- 3. MAILING SETUP (TOP) ---
st.markdown("### 🛠️ Step 1: Mailing Setup")
c_mail, c_pass = st.columns(2)

with c_mail:
    gmail_user = st.text_input("Your Gmail Address", placeholder="example@gmail.com")
    up_contacts = st.file_uploader("📁 Upload Mailing List (Excel)", type=['xlsx'])

with c_pass:
    gmail_pass = st.text_input("Gmail App Password", type="password")
    with st.expander("💡 How to get an App Password?", expanded=False):
        st.markdown(f"""
        1. Go to your [Google Account Security](https://myaccount.google.com/security).
        2. Ensure **2-Step Verification** is ON.
        3. Search for **"App Passwords"** in the top search bar.
        4. Create a password (name it 'Tuesday') and copy the 16-character code here.
        """)

st.divider()

# --- 4. THE MASTER TABLE ---
st.markdown("### 🚀 Step 2: Select & Send Reminders")
df_overdue = get_overdue_data()

if df_overdue.empty:
    st.success("No overdue transactions found in the cloud! 🎉")
    st.stop()

# Load and Merge Emails if file exists
email_map = {}
if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]
        if email_col:
            email_map = pd.Series(df_emails[email_col].values, index=df_emails[comp_col]).to_dict()
    except Exception as e:
        st.error(f"Error reading Excel: {e}")

# Display Unified Table
selected_rows = []
h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
h2.write("**Company**")
h3.write("**Balance Due**")
h4.write("**Email Address**")

for idx, row in df_overdue.iterrows():
    col1, col2, col3, col4 = st.columns([0.5, 2, 2, 2])
    target_email = email_map.get(row['company'], None)
    
    with col1:
        is_selected = st.checkbox("", key=f"send_check_{idx}")
    with col2:
        st.write(row['company'])
    with col3:
        st.write(f"₪{row['balance']:,.2f}")
    with col4:
        if up_contacts:
            st.write(f"`{target_email}`" if target_email else "⚠️ Not found in file")
        else:
            st.write("*Upload file to see email*")
    
    if is_selected:
        row_with_email = row.to_dict()
        row_with_email['email_contact'] = target_email
        selected_rows.append(row_with_email)

st.divider()

# --- 5. EXECUTION ---
# Button is only active if file is uploaded AND password is provided
can_send = up_contacts is not None and len(gmail_pass) > 0

if st.button("SEND REMINDERS", use_container_width=True, type="primary", disabled=not can_send):
    if not selected_rows:
        st.warning("Please select at least one company.")
    else:
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, row in enumerate(selected_rows):
                target = str(row['email_contact'])
                if not target or "@" not in target or target == "None":
                    st.warning(f"Skipping {row['company']} - No valid email.")
                    continue
                
                month_name = pd.to_datetime(row['due_date']).strftime('%B')
                msg = MIMEMultipart()
                msg['Subject'] = f"Payment Reminder: {row['company']}"
                msg['To'] = target
                
                body = f"""Dear {row['company']} Team,

As of today, the payment for the month of {month_name} has not yet been settled, even though the payment due date has passed.
An open invoice report was sent at the beginning of the month.

Please settle the payment immediately and update us once the transfer is completed.
Failure to settle the payment may lead to account suspension and service disruption.

If the payment was made in the last few days, please send us the transfer confirmation.

Best regards,
Tuesday Accounts Team"""
                
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                server.send_message(msg)

                # Update Cloud
                supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                
                # Update Progress
                percent = (i + 1) / len(selected_rows)
                progress_bar.progress(percent)
                status_text.text(f"Sending to {row['company']} ({i+1}/{len(selected_rows)})...")

            server.quit()
            st.balloons()
            st.success("Reminders sent successfully!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

if not can_send:
    st.info("ℹ️ To enable sending, please upload the Mailing List and enter your App Password.")
