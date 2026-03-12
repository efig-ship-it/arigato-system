import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app import get_cloud_history, supabase, extract_total_amount_from_file

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.title("Invoicing Dispatch 📧")

# --- SECTION 1: UPLOADS & CONFIG ---
col_up, col_due = st.columns([2, 1])
with col_up: 
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with col_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)

uploaded_files = st.file_uploader("Drop Invoices Here", accept_multiple_files=True)

# --- SECTION 2: THE DETECTIVE & RISK ENGINE ---
risk_cleared, detective_cleared = True, True

if up_ex:
    df_history = get_cloud_history()
    try:
        df_ex = pd.read_excel(up_ex)
        current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        
        # Risk Control
        risk_threshold = date.today() - timedelta(days=30)
        bad_debts = df_history[
            (df_history['company'].isin(current_companies)) & 
            (df_history['status'] != 'Paid') & 
            (df_history['due_date_obj'] < risk_threshold)
        ]
        
        if not bad_debts.empty:
            st.markdown(f'<div class="risk-box">⚠️ <b>Risk Alert:</b> {len(bad_debts)} companies are 30+ days overdue.</div>', unsafe_allow_html=True)
            risk_ack = st.checkbox("🚨 I confirm background check", value=False)
            if not risk_ack: risk_cleared = False
        
        # Detective Alert
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing_files = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
        
        if missing_files:
            st.markdown(f'<div class="detective-box">🔍 <b>Detective Alert:</b> Missing: <b>{", ".join(missing_files)}</b></div>', unsafe_allow_html=True)
            det_ack = st.checkbox("🕵️‍♂️ I confirm file review", value=False)
            if not det_ack: detective_cleared = False
                
    except: pass

st.divider()

# --- SECTION 3: AUTHENTICATION & GUIDE (SIDE-BY-SIDE) ---
st.subheader("Authentication")

# יצירת שתי עמודות: שמאל לשדות, ימין למדריך
col_auth, col_guide = st.columns([1.5, 1], gap="medium")

with col_auth:
    u_m = st.text_input("Gmail Account (Sender)")
    u_p = st.text_input("App Password", type="password")

with col_guide:
    with st.expander("🔐 Password Guide", expanded=True):
        st.markdown("""
        1. Open **[Google App Passwords](https://myaccount.google.com/apppasswords)**.
        2. Name it **"Tuesday Billing"**.
        3. Click **Create**.
        4. Copy the **16-character code** to the left.
        """)

st.divider()

# --- SECTION 4: DISPATCH ---
can_send = up_ex and uploaded_files and risk_cleared and detective_cleared and u_m and u_p
if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not can_send):
    try:
        df_master = pd.read_excel(up_ex).dropna(how='all')
        due_col = [c for c in df_master.columns if 'due' in c.lower()]
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        status_placeholder = st.empty()
        with status_placeholder.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            with st.spinner("Tuesday is dispatching..."):
                for _, row in df_master.iterrows():
                    comp = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    day_val = int(row[due_col[0]]) if due_col and pd.notna(row[due_col[0]]) else 15
                    comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    total_amt = sum([extract_total_amount_from_file(f) for f in comp_files])
                    
                    if emails and comp_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Dear {comp},\n\nAttached are your invoices.\n\nBest, Tuesday Team", 'plain'))
                        for f in comp_files:
                            msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        server.send_message(msg)
                        
                        it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        dv = f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                        supabase.table("billing_history").insert({
                            "date": it, "company": comp, "amount": total_amt, "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0
                        }).execute()
        
        server.quit()
        status_placeholder.empty()
        st.balloons()
        st.success("SUCCESS!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
