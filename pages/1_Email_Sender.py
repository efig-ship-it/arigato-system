import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from supabase import create_client

# --- 1. CORE FUNCTIONS (הטמעה ישירה למניעת ImportError) ---

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

# --- 2. UI & STYLES ---
st.set_page_config(page_title="Tuesday | Dispatch", page_icon="📧", layout="wide")

st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .risk-box { background-color: #FEE2E2; border: 1px solid #EF4444; padding: 15px; border-radius: 10px; color: #991B1B; margin: 10px 0; }
    .detective-box { background-color: #FEF3C7; border: 1px solid #F59E0B; padding: 15px; border-radius: 10px; color: #92400E; margin: 10px 0; }
    .suitcase-anim { font-size: 100px; text-align: center; animation: move 1.5s infinite ease-in-out; }
    @keyframes move { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1) translateY(-20px); } }
    </style>
""", unsafe_allow_html=True)

st.title("Invoicing Dispatch 📧")

# --- 3. LAYOUT & UPLOADS ---
col_up, col_due = st.columns([2, 1])
with col_up: 
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with col_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)

uploaded_files = st.file_uploader("Drop Invoices Here", accept_multiple_files=True)

# --- 4. VALIDATIONS (RISK & DETECTIVE) ---
risk_cleared, detective_cleared = True, True

if up_ex:
    df_history = get_cloud_history()
    try:
        df_ex = pd.read_excel(up_ex)
        df_ex.columns = [str(c).lower().strip() for c in df_ex.columns] # נירמול שמות עמודות
        
        current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        
        # בדיקת חובות (Risk)
        risk_threshold = date.today() - timedelta(days=30)
        bad = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
        
        if not bad.empty:
            risk_ack = st.checkbox("🚨 I confirm background check for overdue debts", value=False)
            if not risk_ack:
                st.markdown(f'<div class="risk-box">⚠️ <b>Risk Alert:</b> Overdue debtors: {", ".join(bad["company"].unique())}</div>', unsafe_allow_html=True)
                risk_cleared = False
        
        # בדיקת קבצים חסרים (Detective)
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
        
        if missing:
            det_ack = st.checkbox("🕵️‍♂️ I confirm file review (Missing files accounted for)", value=False)
            if not det_ack:
                st.markdown(f'<div class="detective-box">🔍 <b>Detective Alert:</b> Missing invoices for: <b>{", ".join(missing)}</b></div>', unsafe_allow_html=True)
                detective_cleared = False
    except Exception as e:
        st.error(f"Error loading Excel: {e}")

# --- 5. AUTHENTICATION ---
sc1, sc2 = st.columns(2)
u_m = sc1.text_input("Gmail Account")
u_p = sc2.text_input("App Password", type="password")

# --- 6. DISPATCH LOGIC ---
if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (up_ex and uploaded_files and risk_cleared and detective_cleared)):
    try:
        # קריאת האקסל וסכימה
        df_master = pd.read_excel(up_ex).dropna(how='all')
        df_master.columns = [str(c).lower().strip() for c in df_master.columns]
        
        # זיהוי עמודות
        due_col = [c for c in df_master.columns if 'due' in c.lower()]
        amt_col = 'amount' # אנחנו מחפשים עמודה בשם amount
        
        if amt_col not in df_master.columns:
            st.error("Missing 'amount' column in Excel!")
            st.stop()

        # סכימה לפי חברה
        summary = df_master.groupby(df_master.columns[0]).agg({
            amt_col: 'sum',
            df_master.columns[1]: 'first' # המייל בעמודה השנייה
        }).reset_index()

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        sh = st.empty()
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            with st.spinner("Dispatching..."):
                for _, row in summary.iterrows():
                    comp = str(row.iloc[0]).strip()
                    email_list = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    total_amt = float(row[amt_col])
                    
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    
                    if email_list and files:
                        # יצירת המייל
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = ", ".join(email_list)
                        
                        # הטמפלט החדש שלך עם סכום
                        body = f"Hello {comp},\n\nPlease find attached invoices. Total amount: ₪{total_amt:,.2f}"
                        msg.attach(MIMEText(body, 'plain'))
                        
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        # הכנת תאריכים
                        it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        orig_row = df_master[df_master.iloc[:, 0].astype(str).str.strip() == comp].iloc[0]
                        day_val = int(orig_row[due_col[0]]) if due_col and pd.notna(orig_row[due_col[0]]) else 15
                        dv = f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                        
                        # שמירה ל-Supabase
                        supabase.table("billing_history").insert({
                            "date": it, 
                            "company": comp, 
                            "amount": total_amt, 
                            "status": "Sent", 
                            "due_date": dv, 
                            "sender": u_m, 
                            "received_amount": 0
                        }).execute()
        
        server.quit()
        sh.empty()
        st.balloons()
        st.success("Dispatch Completed!")
        time.sleep(1)
        st.rerun()
        
    except Exception as e: 
        st.error(f"Error: {e}")
