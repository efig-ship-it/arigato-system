import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app import get_cloud_history, supabase, extract_total_amount_from_file

st.title("Invoicing Dispatch 📧")
col_up, col_due = st.columns([2, 1])
with col_up: up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with col_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)
uploaded_files = st.file_uploader("Drop Invoices Here", accept_multiple_files=True)

risk_cleared, detective_cleared = True, True
if up_ex:
    df_history = get_cloud_history()
    try:
        df_ex = pd.read_excel(up_ex); current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        risk_threshold = date.today() - timedelta(days=30)
        bad = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
        if not bad.empty:
            risk_ack = st.checkbox("🚨 I confirm background check for overdue debts", value=False)
            if not risk_ack:
                st.markdown(f'<div class="risk-box">⚠️ <b>Risk Alert:</b> Overdue debtors: {", ".join(bad["company"].unique())}</div>', unsafe_allow_html=True)
                risk_cleared = False
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
        if missing:
            det_ack = st.checkbox("🕵️‍♂️ I confirm file review (Missing files accounted for)", value=False)
            if not det_ack:
                st.markdown(f'<div class="detective-box">🔍 <b>Detective Alert:</b> Missing invoices for: <b>{", ".join(missing)}</b></div>', unsafe_allow_html=True)
                detective_cleared = False
    except: pass

sc1, sc2 = st.columns(2); u_m = sc1.text_input("Gmail Account"); u_p = sc2.text_input("App Password", type="password")
if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (up_ex and uploaded_files and risk_cleared and detective_cleared)):
    try:
        df_master = pd.read_excel(up_ex).dropna(how='all')
        due_col = [c for c in df_master.columns if 'due' in c.lower()]
        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(u_m.strip(), u_p.strip().replace(" ",""))
        sh = st.empty()
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            with st.spinner("Dispatching..."):
                for _, row in df_master.iterrows():
                    comp, emails = str(row.iloc[0]).strip(), [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    day_val = int(row[due_col[0]]) if due_col and pd.notna(row[due_col[0]]) else 15
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    amt = sum([extract_total_amount_from_file(f) for f in files])
                    if emails and files:
                        it, dv = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M"), f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                        supabase.table("billing_history").insert({"date": it, "company": comp, "amount": amt, "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0}).execute()
        server.quit(); sh.empty(); st.balloons(); st.rerun()
    except Exception as e: st.error(f"Error: {e}")
