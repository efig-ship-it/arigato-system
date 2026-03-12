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

# --- TOP FILTERS & UPLOADS ---
col_up, col_due = st.columns([2, 1])
with col_up: 
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with col_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)

uploaded_files = st.file_uploader("Drop Invoices Here", accept_multiple_files=True)

# --- RISK & DETECTIVE LOGIC ---
risk_cleared, detective_cleared = True, True
if up_ex:
    df_history = get_cloud_history()
    try:
        df_ex = pd.read_excel(up_ex)
        current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        
        # Risk Control (30+ Days Overdue)
        risk_threshold = date.today() - timedelta(days=30)
        bad = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
        
        if not bad.empty:
            risk_ack = st.checkbox("🚨 I confirm background check for overdue debts", value=False)
            if not risk_ack:
                st.markdown(f'''<div class="risk-box">⚠️ <b>Risk Alert:</b> {len(bad)} companies are 30+ days overdue. 
                            Please verify payment status before proceeding.</div>''', unsafe_allow_html=True)
                risk_cleared = False
        
        # Detective Alert (Missing Files)
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
        if missing:
            det_ack = st.checkbox("🕵️‍♂️ I confirm file review (Missing files accounted for)", value=False)
            if not det_ack:
                st.markdown(f'<div class="detective-box">🔍 <b>Detective Alert:</b> Missing invoices for: <b>{", ".join(missing)}</b></div>', unsafe_allow_html=True)
                detective_cleared = False
    except: pass

st.divider()

# --- AUTHENTICATION & GUIDE ---
st.subheader("Authentication Settings")

with st.expander("🔐 Need a Gmail App Password? (Click for guide)", expanded=False):
    st.markdown("""
    1. Go to your **[Google Account Settings](https://myaccount.google.com/)**.
    2. Search for **"App Passwords"** (2FA must be enabled on your account).
    3. Name it **"Tuesday Billing"** and click **Create**.
    4. **Copy the 16-character code** and paste it into the field below.
    """)
    st.info("💡 Once generated, you can use the same code every time you send invoices.")

sc1, sc2 = st.columns(2)
u_m = sc1.text_input("Gmail Account (Sender)")
u_p = sc2.text_input("App Password", type="password", help="Enter the 16-character code from Google")

# --- DISPATCH ACTION ---
if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (up_ex and uploaded_files and risk_cleared and detective_cleared)):
    try:
        df_master = pd.read_excel(up_ex).dropna(how='all')
        due_col = [c for c in df_master.columns if 'due' in c.lower()]
        
        # Connect to Gmail
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        sh = st.empty()
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            with st.spinner("Dispatching Invoices..."):
                for _, row in df_master.iterrows():
                    comp = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    day_val = int(row[due_col[0]]) if due_col and pd.notna(row[due_col[0]]) else 15
                    
                    # Match files to company
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    amt = sum([extract_total_amount_from_file(f) for f in files])
                    
                    if emails and files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Dear {comp},\nPlease find your invoices for {sel_m} {sel_y} attached.\n\nBest regards,\nTuesday Team", 'plain'))
                        
                        for f in files:
                            msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        
                        server.send_message(msg)
                        
                        # Update Cloud Database
                        it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        dv = f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                        supabase.table("billing_history").insert({
                            "date": it, 
                            "company": comp, 
                            "amount": amt, 
                            "status": "Sent", 
                            "due_date": dv, 
                            "sender": u_m, 
                            "received_amount": 0
                        }).execute()
        
        server.quit()
        sh.empty()
        st.balloons()
        st.success(f"SUCCESS: All invoices for {comp} and others have been dispatched.")
        time.sleep(2)
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during dispatch: {e}")
