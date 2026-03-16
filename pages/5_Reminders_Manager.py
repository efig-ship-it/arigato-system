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

def get_overdue_from_cloud():
    # שליפה ישירה ללא Cache כדי להבטיח סנכרון עם עמוד 4
    try:
        res = supabase.table("billing_history").select("*").eq("status", "Overdue").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
            df['balance'] = df['amount'] - df['received_amount']
        return df
    except Exception as e:
        st.error(f"Error fetching from Cloud: {e}")
        return pd.DataFrame()

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
    if st.button("🔄 Sync Cloud"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# --- 3. INPUTS ---
with st.expander("🛠️ Email Settings & Contacts", expanded=True):
    up_contacts = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("Your Gmail")
    gmail_pass = c2.text_input("App Password", type="password")

# --- 4. DATA PROCESSING ---
df_overdue = get_overdue_from_cloud()

if df_overdue.empty:
    st.success("Clean Slate! No Overdue transactions found in Cloud. ☕")
    st.stop()

if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]

        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.subheader(f"Pending Actions: {len(df_final)}")
        
        selected_indices = []
        # כותרות הטבלה
        h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
        h2.write("**Company**")
        h3.write("**Balance**")
        h4.write("**Email**")

        for idx, row in df_final.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([0.5, 2, 2, 2])
                with c1:
                    is_selected = st.checkbox("", key=f"overdue_{idx}")
                with c2:
                    st.write(f"**{row['company']}**")
                with c3:
                    st.write(f"₪{row['balance']:,.2f}")
                with c4:
                    email_display = row[email_col] if pd.notna(row[email_col]) else "⚠️ No Email"
                    st.write(f"`{email_display}`")
                
                if is_selected:
                    selected_indices.append(idx)

        st.divider()

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
                    for i, idx_in_final in enumerate(selected_indices):
                        row = df_final.iloc[idx_in_final]
                        target = str(row[email_col])
                        if "@" not in target: continue

                        msg = MIMEMultipart()
                        msg['Subject'] = f"FOLLOW UP: Payment Status - {row['company']}"
                        msg['From'] = gmail_user
                        msg['To'] = target
                        body = f"Hello {row['company']},\n\nPlease settle your outstanding balance of ₪{row['balance']:,.2f}.\n\nRegards,"
                        msg.attach(MIMEText(body, 'plain'))
                        server.send_message(msg)

                        # עדכון סטטוס בענן - כדי שייצא מהרשימה
                        supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                        prog.progress((i + 1) / len(selected_indices))

                    server.quit()
                    st.balloons()
                    st.success("Reminders sent and Cloud updated!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"SMTP Error: {e}")
    except Exception as e:
        st.error(f"Excel Error: {e}")
else:
    st.info("Please upload your contacts Excel to link emails.")
