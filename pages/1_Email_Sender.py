import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
# ייבוא פונקציות המנוע מקובץ ה-app הראשי
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

uploaded_files = st.file_uploader("Drop Invoices (PDF/Excel) Here", accept_multiple_files=True)

# --- SECTION 2: THE DETECTIVE & RISK ENGINE ---
risk_cleared, detective_cleared = True, True

if up_ex:
    df_history = get_cloud_history()
    try:
        df_ex = pd.read_excel(up_ex)
        # זיהוי חברות מהאקסל (עמודה ראשונה)
        current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        
        # --- RISK ALERT: חובות מעל 30 יום ---
        risk_threshold = date.today() - timedelta(days=30)
        bad_debts = df_history[
            (df_history['company'].isin(current_companies)) & 
            (df_history['status'] != 'Paid') & 
            (df_history['due_date_obj'] < risk_threshold)
        ]
        
        if not bad_debts.empty:
            st.markdown(f'''<div class="risk-box">⚠️ <b>Risk Alert:</b> {len(bad_debts)} companies have critical overdue debts (30+ days).</div>''', unsafe_allow_html=True)
            risk_ack = st.checkbox("🚨 I confirm background check for these overdue debts", value=False)
            if not risk_ack:
                risk_cleared = False
        
        # --- DETECTIVE ALERT: בדיקת התאמה בין אקסל לקבצים המצורפים ---
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing_files = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
        
        if missing_files:
            st.markdown(f'<div class="detective-box">🔍 <b>Detective Alert:</b> Missing invoices for: <b>{", ".join(missing_files)}</b></div>', unsafe_allow_html=True)
            det_ack = st.checkbox("🕵️‍♂️ I confirm file review (Missing files are accounted for)", value=False)
            if not det_ack:
                detective_cleared = False
                
    except Exception as e:
        st.error(f"Error analyzing files: {e}")

st.divider()

# --- SECTION 3: AUTHENTICATION & DIRECT GUIDE ---
st.subheader("Authentication Settings")

with st.expander("🔐 Need a Gmail App Password? (Direct Link)", expanded=False):
    st.markdown("""
    1. Open the **[Google App Passwords Settings](https://myaccount.google.com/apppasswords)**.
    2. Sign in to your Gmail account.
    3. Under "App name", type **"Tuesday Billing"**.
    4. Click **Create** and **Copy the 16-character code**.
    5. Paste it into the field below.
    """)
    st.info("💡 Tip: You only need to do this once. Keep the code safe!")

sc1, sc2 = st.columns(2)
u_m = sc1.text_input("Gmail Account (Sender)")
u_p = sc2.text_input("App Password", type="password", help="The 16-character code from Google settings")

# --- SECTION 4: THE DISPATCHER (THE ACTION) ---
can_send = up_ex and uploaded_files and risk_cleared and detective_cleared and u_m and u_p

if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not can_send):
    try:
        df_master = pd.read_excel(up_ex).dropna(how='all')
        due_col = [c for c in df_master.columns if 'due' in c.lower()]
        
        # התחברות לשרת הג'ימייל
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        # יצירת אנימציית המזוודה
        status_placeholder = st.empty()
        with status_placeholder.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            with st.spinner("Tuesday is dispatching your invoices..."):
                for _, row in df_master.iterrows():
                    comp = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    day_val = int(row[due_col[0]]) if due_col and pd.notna(row[due_col[0]]) else 15
                    
                    # הצמדת קבצים רלוונטיים לחברה
                    comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    
                    # חישוב סכום אוטומטי (מהבטחת החוזה)
                    total_amt = sum([extract_total_amount_from_file(f) for f in comp_files])
                    
                    if emails and comp_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = ", ".join(emails)
                        
                        body = f"Dear {comp},\n\nPlease find attached your invoices for {sel_m} {sel_y}.\n\nBest regards,\nTuesday Team"
                        msg.attach(MIMEText(body, 'plain'))
                        
                        for f in comp_files:
                            msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        
                        server.send_message(msg)
                        
                        # עדכון ה-Database בענן
                        sent_date = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        due_date_str = f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                        
                        supabase.table("billing_history").insert({
                            "date": sent_date, 
                            "company": comp, 
                            "amount": total_amt, 
                            "status": "Sent", 
                            "due_date": due_date_str, 
                            "sender": u_m, 
                            "received_amount": 0
                        }).execute()
        
        server.quit()
        status_placeholder.empty()
        st.balloons()
        st.success("SUCCESS: Invoices dispatched and documented in the cloud.")
        time.sleep(2)
        st.rerun()
        
    except Exception as e:
        st.error(f"Dispatch Error: {e}")

# הערה קטנה למשתמש אם הכפתור חסום
if not can_send and up_ex:
    st.caption("🔒 Button will unlock once files are uploaded and alerts are acknowledged.")
