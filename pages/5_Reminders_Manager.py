import streamlit as st
import pandas as pd
import smtplib, time, random
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
    # פתרון קסם: הוספת סדר אקראי קטן (או מזהה זמן) מבטיח שהשאילתה תמיד תהיה "חדשה" לענן
    # זה מונע מכל מנגנון זיכרון בדרך להגיש לנו מידע ישן
    res = supabase.table("billing_history")\
        .select("*")\
        .eq("status", "Overdue")\
        .order("id")\
        .execute()
    
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
        df['balance'] = df['amount'] - df['received_amount']
    return df

# --- 2. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Recovery", layout="wide")

# פונקציית ריענון מובנית שתנקה את כל הזיכרון של הדף
def clear_all_and_refresh():
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

st.markdown("""
    <style>
    .recovery-title { font-size: 32px; font-weight: 800; color: #DC2626; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

col_title, col_refresh = st.columns([5, 1])
with col_title:
    st.markdown('<p class="recovery-title">Overdue Reminders (Page 5) 🚨</p>', unsafe_allow_html=True)
with col_refresh:
    if st.button("🔄 Sync with Cloud", help="לחץ כאן אם עדכנת סטטוס בעמוד אחר והוא לא מופיע"):
        clear_all_and_refresh()

# --- 3. INPUTS ---
with st.expander("🛠️ Email Settings & Contacts", expanded=True):
    up_contacts = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("Your Gmail")
    gmail_pass = c2.text_input("App Password", type="password")

# --- 4. LOGIC ---
df_overdue = get_overdue_from_cloud()

if df_overdue.empty:
    st.success("Clean Slate! No Overdue transactions found in Cloud. ☕")
    st.info("Check Page 4 to ensure status is set to 'Overdue'.")
    # אם בכל זאת אתה חושב שיש נתונים, הכפתור למעלה ינקה הכל
    st.stop()

if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]

        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.subheader(f"Pending Actions: {len(df_final)}")
        
        # צ'קלקלה
        selected_indices = []
        for idx, row in df_final.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([0.5, 2, 2, 2])
                with c1:
                    is_selected = st.checkbox("", key=f"overdue_{idx}")
                with c2:
                    st.write(f"**{row['company']}**")
                with c3:
                    st.write(f"Debt: ₪{row['balance']:,.2f}")
                with c4:
                    email_display = row[email_col] if pd.notna(row[email_col]) else "⚠️ No Email"
                    st.write(f"To: `{email_display}`")
                
                if is_selected:
                    selected_indices.append(idx)

        st.divider()

        if st.button("🚀 EXECUTE REMINDERS", use_container_width=True, type="primary"):
            if not selected_indices:
                st.warning("Select companies first.")
            elif not gmail_user or not gmail_pass:
                st.error("Credentials missing.")
            else:
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

                    for i in selected_indices:
                        row = df_final.iloc[i]
                        target = str(row[email_col])
                        if "@" not in target: continue

                        msg = MIMEMultipart()
                        msg['Subject'] = f"FOLLOW UP: Payment Status - {row['company']}"
                        msg['To'] = target
                        msg.attach(MIMEText(f"Hello,\n\nPlease settle your balance of ₪{row['balance']:,.2f}.", 'plain'))
                        server.send_message(msg)

                        # עדכון מידי לענן
                        supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()

                    server.quit()
                    st.balloons()
                    st.success("Done! Records moved to 'Sent Reminder' status.")
                    time.sleep(1)
                    clear_all_and_refresh()
                except Exception as e:
                    st.error(
