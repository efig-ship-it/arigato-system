import streamlit as st
import pandas as pd
import smtplib
import time
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

# --- 2. CSS & ANIMATIONS ---
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

st.title("Invoicing Dispatch 📧")

# --- 3. LOADING & LOGIC ---
st.subheader("1. Load Data")
c_up, c_due = st.columns([2, 1])
with c_up: 
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with c_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)

uploaded_files = st.file_uploader("Drop Invoices Here (PDF)", accept_multiple_files=True)

risk_cleared = True
detective_cleared = True
df_to_dispatch = pd.DataFrame()

if up_ex:
    df_history = get_cloud_history()
    df_raw = pd.read_excel(up_ex).dropna(how='all')
    
    # נירמול שמות עמודות (מוריד רווחים והופך לקטן)
    df_raw.columns = [str(c).lower().strip() for c in df_raw.columns]
    
    # זיהוי עמודת מייל באופן גמיש
    email_col = next((c for c in df_raw.columns if 'email' in c or 'mail' in c), None)
    
    if 'company' not in df_raw.columns or 'amount' not in df_raw.columns or not email_col:
        st.error("❌ חסרות עמודות באקסל! וודא שיש עמודות בשם: company, amount ו-email.")
    else:
        # --- לוגיקת סכימה (SUM) לפי חברה ---
        df_to_dispatch = df_raw.groupby('company').agg({
            'amount': 'sum',
            email_col: 'first'
        }).reset_index()
        
        st.write("### 📊 Preview: Summary to Dispatch")
        st.dataframe(df_to_dispatch, use_container_width=True, hide_index=True)

        # --- הבלש (Detective) ---
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing = [c for c in df_to_dispatch['company'] if not any(str(c).lower() in fn.lower() for fn in file_names)]
        if missing:
            st.markdown(f'<div class="detective-box">🕵️‍♂️ <b>Detective:</b> missing files for: {", ".join(missing)}</div>', unsafe_allow_html=True)
            det_ack = st.checkbox("I acknowledge the missing files")
            if not det_ack: detective_cleared = False

        # --- ניהול סיכונים (Risk) ---
        risk_threshold = date.today() - timedelta(days=30)
        bad_debts = df_history[(df_history['company'].isin(df_to_dispatch['company'])) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
        if not bad_debts.empty:
            st.markdown(f'<div class="risk-box">🚨 <b>Risk:</b> Overdue debts detected for companies in this list.</div>', unsafe_allow_html=True)
            risk_ack = st.checkbox(f"Confirm sending despite {len(bad_debts)} overdue records")
            if not risk_ack: risk_cleared = False

# --- 4. AUTHENTICATION ---
st.subheader("2. Authenticate")
c_auth1, c_auth2 = st.columns(2)
with c_auth1: u_m = st.text_input("Gmail Account")
with c_auth2: u_p = st.text_input("App Password", type="password")

st.divider()

# --- 5. DISPATCH EXECUTION ---
if up_ex and uploaded_files and u_m and u_p and not df_to_dispatch.empty:
    if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (risk_cleared and detective_cleared)):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(u_m.strip(), u_p.strip().replace(" ",""))
            
            sh = st.empty()
            with sh.container():
                st.markdown('<div class="suitcase-container"><div class="big-suitcase">💼</div></div>', unsafe_allow_html=True)
                
                for _, row in df_to_dispatch.iterrows():
                    comp = str(row['company']).strip()
                    target_email = str(row[email_col]).strip()
                    total_sum = float(row['amount'])
                    
                    # הצלבת קבצים (שם חברה מופיע בשם הקובץ)
                    comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    
                    if comp_files:
                        with st.spinner(f"Sending to {comp}..."):
                            msg = MIMEMultipart()
                            msg['Subject'] = f"Invoice - {comp}"
                            msg['To'] = target_email
                            msg.attach(MIMEText(f"Hello,\nPlease find attached invoices. Total: ₪{total_sum:,.2f}", 'plain'))
                            
                            for f in comp_files:
                                part = MIMEApplication(f.getvalue(), Name=f.name)
                                part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                                msg.attach(part)
                            
                            server.send_message(msg)
                            
                            # שמירה ל-Supabase עם הסכום שנסכם מהאקסל
                            due_str = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                            supabase.table("billing_history").insert({
                                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "company": comp,
                                "amount": total_sum,
                                "received_amount": 0.0,
                                "status": "Sent",
                                "due_date": due_str
                            }).execute()
            
            server.quit()
            sh.empty()
            st.balloons()
            st.success("Dispatch Completed! Amounts updated in Control Center.")
            time.sleep(1)
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {e}")
