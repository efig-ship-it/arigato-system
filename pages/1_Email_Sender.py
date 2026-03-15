import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app import get_cloud_history, supabase # שים לב: הורדתי את ה-extract_total מהקובץ כי אנחנו עוברים לאקסל

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
        # קריאה ראשונית לבדיקות הבלש והסיכונים
        df_ex = pd.read_excel(up_ex)
        df_ex.columns = [str(c).lower().strip() for c in df_ex.columns] # נירמול עמודות
        
        current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
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
        # לוגיקה חדשה: סכימת ה-Amount מתוך האקסל
        df_master = pd.read_excel(up_ex).dropna(how='all')
        df_master.columns = [str(c).lower().strip() for c in df_master.columns] # חשוב למציאת עמודת 'amount'
        
        # זיהוי עמודת התאריך
        due_col = [c for c in df_master.columns if 'due' in c.lower()]
        
        # --- סכימת הנתונים לפי חברה ---
        # מקבצים לפי חברה (עמודה ראשונה), סוכמים amount, ולוקחים את המייל (עמודה שנייה)
        summary = df_master.groupby(df_master.columns[0]).agg({
            'amount': 'sum',
            df_master.columns[1]: 'first'
        }).reset_index()
        
        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(u_m.strip(), u_p.strip().replace(" ",""))
        sh = st.empty()
        
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            with st.spinner("Dispatching..."):
                for _, row in summary.iterrows():
                    comp = str(row.iloc[0]).strip()
                    email_list = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    
                    # חישוב הסכום שכבר סכמנו מקודם
                    total_amt = float(row['amount'])
                    
                    # מציאת הקבצים עבור החברה
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    
                    if email_list and files:
                        # שליחת המייל (MIME)
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = ", ".join(email_list)
                        msg.attach(MIMEText(f"Attached invoices for {comp}. Total amount: {total_sum:,.2f}", 'plain'))
                        
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        # הכנת נתונים ל-Supabase
                        it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        
                        # מציאת ה-due day מהשורה המקורית (לוקחים את הראשון)
                        orig_row = df_master[df_master.iloc[:, 0].astype(str).str.strip() == comp].iloc[0]
                        day_val = int(orig_row[due_col[0]]) if due_col and pd.notna(orig_row[due_col[0]]) else 15
                        dv = f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                        
                        # הכנסה ל-Supabase עם ה-Amount הנכון
                        supabase.table("billing_history").insert({
                            "date": it, 
                            "company": comp, 
                            "amount": total_amt, 
                            "status": "Sent", 
                            "due_date": dv, 
                            "sender": u_m, 
                            "received_amount": 0
                        }).execute()
                        
        server.quit(); sh.empty(); st.balloons(); st.success("Done!"); time.sleep(1); st.rerun()
    except Exception as e: st.error(f"Error: {e}")
