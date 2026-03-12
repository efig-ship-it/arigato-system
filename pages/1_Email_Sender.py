import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
# ייבוא פונקציות הליבה
from app import get_cloud_history, supabase, extract_total_amount_from_file

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS STYLES (כולל המזוודה הגדולה והזזה) ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .risk-box { background-color: #FEE2E2; border: 1px solid #EF4444; padding: 15px; border-radius: 10px; color: #991B1B; margin: 10px 0; }
    .detective-box { background-color: #FEF3C7; border: 1px solid #F59E0B; padding: 15px; border-radius: 10px; color: #92400E; margin: 10px 0; }
    
    /* אנימציית המזוודה הגדולה */
    .suitcase-container {
        display: flex; justify-content: center; align-items: center; 
        padding: 40px; margin: 20px 0;
    }
    .big-suitcase {
        font-size: 100px; /* גודל המזוודה */
        animation: suitcase-move 1.5s infinite ease-in-out;
    }
    @keyframes suitcase-move {
        0% { transform: scale(1) translateY(0); }
        50% { transform: scale(1.15) translateY(-20px); }
        100% { transform: scale(1) translateY(0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Invoicing Dispatch 📧")
    st.markdown("---")

    # --- SECTION 1: UPLOADS ---
    st.subheader("1. Load Data")
    c_up, c_due = st.columns([2, 1])
    with c_up: 
        up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with c_due:
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
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            
            # 1. RISK ALERT
            risk_threshold = date.today() - timedelta(days=30)
            bad_debts = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            if not bad_debts.empty:
                risk_ack = st.checkbox(f"🚨 Confirm check for {len(bad_debts)} overdue debts", key="risk_ack")
                if not risk_ack:
                    st.markdown(f'<div class="risk-box">⚠️ <b>Risk:</b> Critical overdue debts detected.</div>', unsafe_allow_html=True)
                    risk_cleared = False

            # 2. DETECTIVE ALERT (דו-כיווני)
            missing_in_files = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
            extra_files = [fn for fn in file_names if not any(c.lower() in fn.lower() for c in current_companies)]

            if missing_in_files or extra_files:
                det_ack = st.checkbox("🕵️‍♂️ Confirm discrepancies", key="det_ack")
                if not det_ack:
                    if missing_in_files:
                        st.markdown(f'<div class="detective-box">🔍 <b>Missing:</b> {", ".join(missing_in_files)}</div>', unsafe_allow_html=True)
                    if extra_files:
                        st.markdown(f'<div class="detective-box">📁 <b>Unrecognized:</b> {", ".join(extra_files)}</div>', unsafe_allow_html=True)
                    detective_cleared = False
        except: pass

    st.divider()

    # --- SECTION 3: AUTH & GUIDE ---
    st.subheader("2. Authenticate")
    col_auth, col_guide = st.columns([1.5, 1], gap="medium")
    with col_auth:
        u_m = st.text_input("Gmail Account")
        u_p = st.text_input("App Password", type="password")
    with col_guide:
        with st.expander("🔐 Guide", expanded=True):
            st.markdown("1. [Google App Passwords](https://myaccount.google.com/apppasswords)\n2. Name: **Tuesday**\n3. Copy **16-char code**")

    st.divider()

    # --- SECTION 4: DISPATCH ---
    can_send = up_ex and uploaded_files and risk_cleared and detective_cleared and u_m and u_p

    if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not can_send):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            due_col = [c for c in df_master.columns if 'due' in c.lower()]
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
            server.login(u_m.strip(), u_p.strip().replace(" ",""))
            
            status_placeholder = st.empty()
            with status_placeholder.container():
                # הצגת המזוודה הגדולה והזזה מהחוזה
                st.markdown('<div class="suitcase-container"><div class="big-suitcase">💼</div></div>', unsafe_allow_html=True)
                with st.spinner("Tuesday is dispatching..."):
                    for _, row in df_master.iterrows():
                        comp = str(row.iloc[0]).strip()
                        comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                        if comp_files:
                            total_amt = sum([extract_total_amount_from_file(f) for f in comp_files])
                            msg = MIMEMultipart()
                            msg['Subject'] = f"Invoice - {comp}"
                            msg['To'] = str(row.iloc[1])
                            msg.attach(MIMEText(f"Dear {comp}, attached invoices.", 'plain'))
                            for f in comp_files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                            server.send_message(msg)
                            
                            it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                            dv = f"{sel_y}-{months.index(sel_m)+1:02d}-{int(row[due_col[0]]) if due_col else 15:02d}"
                            supabase.table("billing_history").insert({"date": it, "company": comp, "amount": total_amt, "status": "Sent", "due_date": dv, "sender": u_m}).execute()
            
            server.quit(); status_placeholder.empty(); st.balloons(); st.success("Done!"); time.sleep(1); st.rerun()
        except Exception as e: st.error(f"Error: {e}")
