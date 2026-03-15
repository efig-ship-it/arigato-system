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

# --- 2. UI STYLE ---
st.set_page_config(page_title="Tuesday | Dispatch", layout="wide")
st.markdown("""
    <style>
    .risk-box { background-color: #FEE2E2; border: 1px solid #EF4444; padding: 15px; border-radius: 10px; color: #991B1B; margin: 10px 0; }
    .detective-box { background-color: #FEF3C7; border: 1px solid #F59E0B; padding: 15px; border-radius: 10px; color: #92400E; margin: 10px 0; }
    .suitcase-anim { font-size: 100px; text-align: center; animation: move 1.5s infinite ease-in-out; }
    @keyframes move { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1) translateY(-20px); } }
    </style>
""", unsafe_allow_html=True)

st.title("Invoicing Dispatch 📧")

# --- 3. UPLOADS ---
col_up1, col_up2 = st.columns(2)
with col_up1: 
    up_emails = st.file_uploader("1. Upload Mailing List (Emails)", type=['xlsx'])
with col_up2: 
    up_data = st.file_uploader("2. Upload Billing Data (Amounts)", type=['xlsx'])

uploaded_files = st.file_uploader("Drop PDF Invoices Here", accept_multiple_files=True)

months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
sel_m = st.selectbox("Month", months, index=datetime.now().month - 1)
sel_y = st.selectbox("Year", ["2025", "2026"], index=1)

df_final = pd.DataFrame()
risk_cleared, detective_cleared = True, True

if up_emails and up_data:
    try:
        df_e = pd.read_excel(up_emails).dropna(how='all')
        df_d = pd.read_excel(up_data).dropna(how='all')
        
        # נירמול עמודות
        df_e.columns = [str(c).lower().strip() for c in df_e.columns]
        df_d.columns = [str(c).lower().strip() for c in df_d.columns]
        
        # חיפוש עמודות (amount באקסל השני, email בראשון)
        amt_col = next((c for c in df_d.columns if 'amount' in c or 'סכום' in c), None)
        email_col = next((c for c in df_e.columns if 'email' in c or 'mail' in c), df_e.columns[1])

        if not amt_col:
            st.error(f"❌ לא נמצאה עמודת סכום באקסל הנתונים. עמודות: {list(df_d.columns)}")
        elif 'company' not in df_e.columns or 'company' not in df_d.columns:
            st.error("❌ חסרה עמודת 'company' באחד הקבצים.")
        else:
            # סכימת סכומים מהאקסל השני
            df_d[amt_col] = pd.to_numeric(df_d[amt_col], errors='coerce').fillna(0.0)
            df_summed = df_d.groupby('company')[amt_col].sum().reset_index()
            
            # חיבור עם המיילים מהאקסל הראשון
            df_final = pd.merge(df_summed, df_e[['company', email_col]], on='company', how='inner')
            
            st.write("### 📊 Preview: Summary to Dispatch")
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            # --- הבלש (Detective) ---
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            current_companies = df_final['company'].tolist()
            missing = [c for c in current_companies if not any(str(c).lower() in fn.lower() for fn in file_names)]
            
            if missing:
                st.markdown(f'<div class="detective-box">🕵️‍♂️ <b>Detective:</b> Missing files for: {", ".join(missing)}</div>', unsafe_allow_html=True)
                det_ack = st.checkbox("I acknowledge the missing files and wish to proceed", value=False)
                if not det_ack: detective_cleared = False
            
            # --- ניהול סיכונים (Risk) ---
            df_history = get_cloud_history()
            risk_threshold = date.today() - timedelta(days=30)
            bad = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            
            if not bad.empty:
                st.markdown(f'<div class="risk-box">🚨 <b>Risk:</b> Overdue debts detected for: {", ".join(bad["company"].unique())}</div>', unsafe_allow_html=True)
                risk_ack = st.checkbox("I confirm I have checked these overdue debts", value=False)
                if not risk_ack: risk_cleared = False

    except Exception as e:
        st.error(f"Error processing files: {e}")

# --- 4. AUTH & DISPATCH ---
sc1, sc2 = st.columns(2)
u_m = sc1.text_input("Gmail Account")
u_p = sc2.text_input("App Password", type="password")

if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (not df_final.empty and uploaded_files and risk_cleared and detective_cleared)):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(u_m.strip(), u_p.strip().replace(" ",""))
        sh = st.empty()
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            for _, row in df_final.iterrows():
                comp = str(row['company']).strip()
                target_email = str(row[email_col]).strip()
                total_sum = float(row[amt_col])
                
                comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                
                if comp_files:
                    with st.spinner(f"Sending to {comp}..."):
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = target_email
                        msg.attach(MIMEText(f"Hello,\nPlease find attached invoices for {comp}.\nTotal Amount: ₪{total_sum:,.2f}", 'plain'))
                        
                        for f in comp_files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        # עדכון Supabase
                        dv = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        supabase.table("billing_history").insert({
                            "date": it, "company": comp, "amount": total_sum, 
                            "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0
                        }).execute()
                    
        server.quit(); sh.empty(); st.balloons(); st.success("Dispatch Finished!"); time.sleep(1); st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
