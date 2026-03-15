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

# --- 3. LOADING DATA ---
st.subheader("1. Load Files")
c1, c2 = st.columns(2)
with c1:
    up_emails = st.file_uploader("Upload Mailing List (Emails)", type=['xlsx'], key="emails")
with c2:
    up_data = st.file_uploader("Upload Billing Data (Amounts)", type=['xlsx'], key="data")

uploaded_files = st.file_uploader("Drop PDF Invoices", accept_multiple_files=True)

months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
sel_m = st.selectbox("For Month", months, index=datetime.now().month - 1)
sel_y = st.selectbox("Year", ["2025", "2026"], index=1)

df_final = pd.DataFrame()

if up_emails and up_data:
    # קריאת הקבצים
    df_emails = pd.read_excel(up_emails).dropna(how='all')
    df_amounts = pd.read_excel(up_data).dropna(how='all')
    
    # נירמול עמודות
    df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
    df_amounts.columns = [str(c).lower().strip() for c in df_amounts.columns]
    
    # חיפוש עמודת המייל באקסל האימיילים
    email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
    
    if 'company' not in df_emails.columns or 'company' not in df_amounts.columns or 'amount' not in df_amounts.columns or not email_col:
        st.error("❌ וודא שבשני האקסלים יש עמודת 'company' ובאקסל הנתונים יש עמודת 'amount'.")
    else:
        # סכימת הסכומים לפי חברה
        df_summed = df_amounts.groupby('company')['amount'].sum().reset_index()
        
        # חיבור עם רשימת המיילים (Merge)
        df_final = pd.merge(df_summed, df_emails[['company', email_col]], on='company', how='inner')
        
        st.write("### 📊 Preview: Summary to Send")
        st.dataframe(df_final, use_container_width=True, hide_index=True)

        # --- הבלש וניהול סיכונים ---
        file_names = [f.name for f in uploaded_files] if uploaded_files else []
        missing = [c for c in df_final['company'] if not any(str(c).lower() in fn.lower() for fn in file_names)]
        if missing:
            st.markdown(f'<div class="detective-box">🕵️‍♂️ Missing PDF for: {", ".join(missing)}</div>', unsafe_allow_html=True)
            
        df_hist = get_cloud_history()
        risk_threshold = date.today() - timedelta(days=30)
        bad_debts = df_hist[(df_hist['company'].isin(df_final['company'])) & (df_hist['status'] != 'Paid') & (df_hist['due_date_obj'] < risk_threshold)]
        if not bad_debts.empty:
            st.markdown(f'<div class="risk-box">🚨 Overdue debts detected for {len(bad_debts.company.unique())} companies.</div>', unsafe_allow_html=True)

# --- 4. AUTH & DISPATCH ---
st.subheader("2. Dispatch")
u_m = st.text_input("Gmail Account")
u_p = st.text_input("App Password", type="password")

if st.button("🚀 Start Dispatch", use_container_width=True) and not df_final.empty:
    if u_m and u_p:
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(u_m.strip(), u_p.strip().replace(" ",""))
            
            sh = st.empty()
            with sh.container():
                st.markdown('<div class="suitcase-container"><div class="big-suitcase">💼</div></div>', unsafe_allow_html=True)
                
                for _, row in df_final.iterrows():
                    comp = str(row['company']).strip()
                    target_email = str(row[email_col]).strip()
                    total_sum = float(row['amount'])
                    
                    comp_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    
                    if comp_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp}"
                        msg['To'] = target_email
                        msg.attach(MIMEText(f"Hello,\nTotal amount for this period: ₪{total_sum:,.2f}.\nAttached invoices.", 'plain'))
                        
                        for f in comp_files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        # שמירה ל-Supabase
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
            st.success("Dispatch Completed!")
            time.sleep(1); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
