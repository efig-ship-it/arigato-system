import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from supabase import create_client

# --- 1. CORE FUNCTIONS ---
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
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['due_date_obj'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
    return df

def extract_total_amount_from_file(file_bytes):
    try:
        # ניסיון לקרוא טקסט מהקובץ (עובד על קבצי PDF טקסטואליים של iCount)
        text = file_bytes.decode('utf-8', errors='ignore')
        # מחפש את הסכום בשקלים או סה"כ
        match = re.search(r"(?:סה\"כ|Total|Amount|₪)[:\s]*([\d,]+\.\d{2})", text)
        if match:
            return float(match.group(1).replace(',', ''))
    except:
        pass
    return 0.0

# --- 2. CSS & STYLES ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .risk-box { background-color: #FEE2E2; border: 1px solid #EF4444; padding: 15px; border-radius: 10px; color: #991B1B; margin: 10px 0; }
    .detective-box { background-color: #FEF3C7; border: 1px solid #F59E0B; padding: 15px; border-radius: 10px; color: #92400E; margin: 10px 0; }
    .suitcase-container { display: flex; justify-content: center; align-items: center; padding: 40px; }
    .big-suitcase { font-size: 100px; animation: suitcase-move 1.5s infinite ease-in-out; }
    @keyframes suitcase-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.15) translateY(-20px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- 3. MAIN LAYOUT ---
st.title("Invoicing Dispatch 📧")

# SECTION 1: UPLOADS
st.subheader("1. Load Data")
c_up, c_due = st.columns([2, 1])
with c_up: 
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with c_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)

uploaded_files = st.file_uploader("Drop Invoices Here (PDF)", accept_multiple_files=True)

# לוגיקת בדיקות
risk_cleared = True
detective_cleared = True

if up_ex:
    df_history = get_cloud_history()
    df_ex = pd.read_excel(up_ex).dropna(how='all')
    current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
    file_names = [f.name for f in uploaded_files] if uploaded_files else []

    # --- הבלש (Detective) ---
    missing_files = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
    extra_files = [fn for fn in file_names if not any(c.lower() in fn.lower() for c in current_companies)]
    
    if missing_files or extra_files:
        st.markdown("### 🕵️‍♂️ Detective Insights")
        det_ack = st.checkbox("I have reviewed the file discrepancies", key="det_ack")
        if not det_ack:
            detective_cleared = False
            if missing_files:
                st.markdown(f'<div class="detective-box">🔍 <b>Missing:</b> {", ".join(missing_files)}</div>', unsafe_allow_html=True)
            if extra_files:
                st.markdown(f'<div class="detective-box">📁 <b>Unrecognized:</b> {", ".join(extra_files)}</div>', unsafe_allow_html=True)

    # --- ניהול סיכונים (Risk) ---
    risk_threshold = date.today() - timedelta(days=30)
    bad_debts = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
    
    if not bad_debts.empty:
        st.markdown("### 🚨 Risk Alert")
        risk_ack = st.checkbox(f"I acknowledge {len(bad_debts)} critical overdue debts", key="risk_ack")
        if not risk_ack:
            st.markdown('<div class="risk-box">⚠️ <b>Risk:</b> Some companies in this list have debts older than 30 days.</div>', unsafe_allow_html=True)
            risk_cleared = False

# SECTION 2: AUTH
st.subheader("2. Authenticate")
c_auth1, c_auth2 = st.columns(2)
with c_auth1: u_m = st.text_input("Gmail Account")
with c_auth2: u_p = st.text_input("App Password", type="password")

st.divider()

# SECTION 3: DISPATCH
# וידוא שכל התנאים מתקיימים
can_send = up_ex and uploaded_files and risk_cleared and detective_cleared and u_m and u_p

if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not can_send):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        status_placeholder = st.empty()
        with status_placeholder.container():
            st.markdown('<div class="suitcase-container"><div class="big-suitcase">💼</div></div>', unsafe_allow_html=True)
            
            for _, row in df_ex.iterrows():
                comp = str(row.iloc[0]).strip()
                comp_email = str(row.iloc[1]).strip()
                # מוצא קבצים ששם החברה מופיע בשם הקובץ שלהם
                comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                
                if comp_files:
                    total_amt = 0.0
                    msg = MIMEMultipart()
                    msg['Subject'] = f"Invoice - {comp}"
                    msg['To'] = comp_email
                    msg.attach(MIMEText(f"Dear {comp},\nPlease find the attached invoices for {sel_m} {sel_y}.", 'plain'))
                    
                    for f in comp_files:
                        f_content = f.getvalue()
                        # חילוץ סכום
                        total_amt += extract_total_amount_from_file(f_content)
                        part = MIMEApplication(f_content, Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.send_message(msg)
                    
                    # בניית תאריך יעד (Due Date)
                    try:
                        day_val = int(row.iloc[2]) if len(row) > 2 else 15
                    except: day_val = 15
                    dv_str = f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                    
                    # שמירה ל-Supabase כולל הסכום שחולץ!
                    supabase.table("billing_history").insert({
                        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "company": comp,
                        "amount": total_amt,
                        "received_amount": 0.0,
                        "status": "Sent",
                        "due_date": dv_str,
                        "sender": u_m
                    }).execute()
        
        server.quit()
        st.balloons()
        st.success("Dispatch Completed! All amounts synced to Control Center.")
        time.sleep(2); st.rerun()
    except Exception as e:
        st.error(f"Error during dispatch: {e}")
