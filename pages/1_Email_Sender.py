import streamlit as st
import pandas as pd
import smtplib, time, re
from datetime import datetime, timedelta, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from app import get_cloud_history, supabase

# --- UI STYLE ---
st.markdown("""
    <style>
    .risk-box { background-color: #FEE2E2; border: 1px solid #EF4444; padding: 15px; border-radius: 10px; color: #991B1B; margin: 10px 0; }
    .detective-box { background-color: #FEF3C7; border: 1px solid #F59E0B; padding: 15px; border-radius: 10px; color: #92400E; margin: 10px 0; }
    .suitcase-anim { font-size: 80px; text-align: center; animation: move 1.5s infinite; }
    @keyframes move { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
    </style>
""", unsafe_allow_html=True)

st.title("Invoicing Dispatch 📧")

# --- 1. UPLOADS (שני קבצים) ---
col_up1, col_up2 = st.columns(2)
with col_up1: 
    up_emails = st.file_uploader("1. Upload Mailing List (Emails)", type=['xlsx'])
with col_up2: 
    up_data = st.file_uploader("2. Upload Billing Data (Amounts)", type=['xlsx'])

col_due = st.columns([1])[0]
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
sel_y = st.selectbox("Year", ["2025", "2026", "2027"], index=1)

uploaded_files = st.file_uploader("Drop Invoices Here", accept_multiple_files=True)

risk_cleared, detective_cleared = True, True
df_final = pd.DataFrame()

if up_emails and up_data:
    try:
        # קריאת שני הקבצים
        df_e = pd.read_excel(up_emails).dropna(how='all')
        df_d = pd.read_excel(up_data).dropna(how='all')
        
        # נירמול עמודות למניעת שגיאות Case-Sensitive
        df_e.columns = [str(c).lower().strip() for c in df_e.columns]
        df_d.columns = [str(c).lower().strip() for c in df_d.columns]
        
        # וידוא קיום עמודות
        if 'company' in df_e.columns and 'company' in df_d.columns and 'amount' in df_d.columns:
            # א. סכימת סכומים מהקובץ השני
            df_summed = df_d.groupby('company')['amount'].sum().reset_index()
            
            # ב. מציאת עמודת המייל מהקובץ הראשון
            email_col = next((c for c in df_e.columns if 'email' in c or 'mail' in c), df_e.columns[1])
            
            # ג. חיבור בין הקבצים (Merge)
            df_final = pd.merge(df_summed, df_e[['company', email_col]], on='company', how='inner')
            
            st.write("### 📊 Preview: Summary to Dispatch")
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # --- דרוש בדיקות סיכונים ובלש ---
            df_history = get_cloud_history()
            current_companies = df_final['company'].tolist()
            
            # Risk
            risk_threshold = date.today() - timedelta(days=30)
            bad = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            if not bad.empty:
                risk_ack = st.checkbox("🚨 I confirm overdue debts check")
                if not risk_ack:
                    st.markdown(f'<div class="risk-box">⚠️ Debtors detected: {", ".join(bad["company"].unique())}</div>', unsafe_allow_html=True)
                    risk_cleared = False
            
            # Detective
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            missing = [c for c in current_companies if not any(str(c).lower() in fn.lower() for fn in file_names)]
            if missing:
                det_ack = st.checkbox("🕵️‍♂️ I confirm file review")
                if not det_ack:
                    st.markdown(f'<div class="detective-box">🔍 Missing files for: {", ".join(missing)}</div>', unsafe_allow_html=True)
                    detective_cleared = False
        else:
            st.error("Missing 'company' or 'amount' columns in the uploaded files.")
    except Exception as e:
        st.error(f"Error processing files: {e}")

# --- 2. AUTH & DISPATCH ---
sc1, sc2 = st.columns(2)
u_m = sc1.text_input("Gmail Account")
u_p = sc2.text_input("App Password", type="password")

if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (not df_final.empty and uploaded_files and risk_cleared and detective_cleared)):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        sh = st.empty()
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            for _, row in df_final.iterrows():
                comp = str(row['company']).strip()
                target_email = str(row.iloc[-1]).strip() # המייל מהעמודה האחרונה ב-Merge
                total_amt = float(row['amount'])
                
                comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                
                if comp_files:
                    msg = MIMEMultipart()
                    msg['Subject'] = f"Invoice - {comp}"
                    msg['To'] = target_email
                    msg.attach(MIMEText(f"Hello,\nPlease find attached invoices for {comp}. Total: ₪{total_amt:,.2f}", 'plain'))
                    
                    for f in comp_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.send_message(msg)
                    
                    # Supabase Update
                    dv = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                    it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                    supabase.table("billing_history").insert({
                        "date": it, "company": comp, "amount": total_amt, 
                        "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0
                    }).execute()
                    
        server.quit()
        st.balloons()
        st.success("Dispatch Finished!")
        time.sleep(1)
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
