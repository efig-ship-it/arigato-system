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
    try:
        # ניקוי הכתובות מרווחים או גרשיים מיותרים שעלולים לגרום לשגיאת DNS
        u = st.secrets["SUPABASE_URL"].strip().strip('"').strip("'")
        k = st.secrets["SUPABASE_KEY"].strip().strip('"').strip("'")
        return create_client(u, k)
    except Exception as e:
        st.error(f"Failed to initialize Supabase connection: {e}")
        st.stop()

supabase = init_connection()

def get_cloud_history():
    try:
        res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            # המרה בטוחה לתאריך לצורך השוואת Risk
            df['due_date_obj'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
            return df
    except Exception as e:
        st.error(f"Cloud Connection Error: {e}")
    return pd.DataFrame()

# --- 2. UI STYLE ---
st.set_page_config(page_title="Tuesday | Dispatch", layout="wide")
st.markdown("""
    <style>
    .risk-box { background-color: #FEE2E2; border: 1px solid #EF4444; padding: 15px; border-radius: 10px; color: #991B1B; margin: 10px 0; direction: rtl; text-align: right; }
    .detective-box { background-color: #FEF3C7; border: 1px solid #F59E0B; padding: 15px; border-radius: 10px; color: #92400E; margin: 10px 0; direction: rtl; text-align: right; }
    .suitcase-anim { font-size: 100px; text-align: center; animation: move 1.5s infinite ease-in-out; }
    @keyframes move { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.1) translateY(-20px); } }
    </style>
""", unsafe_allow_html=True)

st.title("Invoicing Dispatch 📧")

# --- 3. UPLOADS ---
col_up, col_due = st.columns([2, 1])
with col_up:
    up_mailing = st.file_uploader("1. Upload Mailing List (Excel)", type=['xlsx'])
with col_due:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Billing Month", months, index=datetime.now().month - 1)
    sel_y = st.selectbox("Year", ["2025", "2026"], index=0 if datetime.now().year == 2025 else 1)

uploaded_files = st.file_uploader("2. Drop Company Files (PDF Invoices & Company Excels)", accept_multiple_files=True)

risk_cleared, detective_cleared = True, True
mailing_data = pd.DataFrame()

if up_mailing:
    try:
        mailing_data = pd.read_excel(up_mailing).dropna(how='all')
        mailing_data.columns = [str(c).lower().strip() for c in mailing_data.columns]
        
        # זיהוי עמודות גמיש
        comp_col = next((c for c in mailing_data.columns if 'comp' in c or 'חברה' in c or 'customer' in c), mailing_data.columns[0])
        email_col = next((c for c in mailing_data.columns if 'mail' in c or 'מייל' in c), None)
        day_col = next((c for c in mailing_data.columns if 'day' in c or 'יום' in c or 'due' in c), None)

        if not email_col:
            st.error("❌ Could not find an 'Email' column in the Excel file.")
        else:
            with st.expander("🔍 Preview Mailing List", expanded=False):
                st.write(f"Detected Company Column: **{comp_col}**")
                st.write(f"Detected Email Column: **{email_col}**")
                st.dataframe(mailing_data.head())

            df_history = get_cloud_history()
            current_companies = mailing_data[comp_col].astype(str).str.strip().tolist()
            
            # 🕵️‍♂️ הבלש (Detective)
            if uploaded_files:
                file_names = [f.name.lower() for f in uploaded_files]
                missing = [c for c in current_companies if not any(c.lower() in fn for fn in file_names)]
                if missing:
                    st.markdown(f'<div class="detective-box">🕵️‍♂️ <b>Detective:</b> Missing files for: {", ".join(missing)}</div>', unsafe_allow_html=True)
                    det_ack = st.checkbox("Proceed despite missing files")
                    if not det_ack: detective_cleared = False
            
            # 🚨 סיכונים (Risk)
            risk_threshold = (date.today() - timedelta(days=30))
            if not df_history.empty:
                bad_rows = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
                if not bad_rows.empty:
                    st.markdown(f'<div class="risk-box">🚨 <b>Risk:</b> Overdue debts found for debtors.</div>', unsafe_allow_html=True)
                    risk_ack = st.checkbox("Confirm dispatch for these companies")
                    if not risk_ack: risk_cleared = False
            
    except Exception as e:
        st.error(f"Error loading mailing list: {e}")

# --- 4. AUTH & DISPATCH ---
st.divider()
sc1, sc2 = st.columns(2)
u_m = sc1.text_input("Sender Gmail Account")
u_p = sc2.text_input("Gmail App Password", type="password")

if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (up_mailing and uploaded_files and risk_cleared and detective_cleared)):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(u_m.strip(), u_p.strip().replace(" ",""))
        
        sh = st.empty()
        with sh.container():
            st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
            
            for _, row in mailing_data.iterrows():
                comp = str(row[comp_col]).strip()
                email = str(row[email_col]).strip()
                due_day = int(row[day_col]) if day_col and pd.notna(row[day_col]) else 15
                
                # 1. חישוב סכום מאקסלים של החברה
                comp_excels = [f for f in uploaded_files if comp.lower() in f.name.lower() and f.name.endswith('.xlsx')]
                total_sum = 0.0
                if comp_excels:
                    for ex in comp_excels:
                        ex.seek(0)
                        df_temp = pd.read_excel(ex)
                        df_temp.columns = [str(c).lower().strip() for c in df_temp.columns]
                        amt_col = next((c for c in df_temp.columns if 'amount' in c or 'סכום' in c), None)
                        if amt_col:
                            total_sum += pd.to_numeric(df_temp[amt_col], errors='coerce').sum()

                # 2. איסוף קבצים ושלחה
                pdf_files = [f for f in uploaded_files if comp.lower() in f.name.lower() and f.name.endswith('.pdf')]
                
                if email and (pdf_files or comp_excels):
                    with st.spinner(f"Sending to {comp}..."):
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {comp} - {sel_m} {sel_y}"
                        msg['To'] = email
                        msg.attach(MIMEText(f"Hello {comp},\nAttached invoices for {sel_m} {sel_y}.\nTotal: ₪{total_sum:,.2f}", 'plain'))
                        
                        for f in (pdf_files + comp_excels):
                            f.seek(0)
                            part = MIMEApplication(f.read(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        # 3. שמירה לענן
                        m_idx = months.index(sel_m) + 1
                        dv_str = f"{sel_y}-{m_idx:02d}-{due_day:02d}"
                        it_str = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        supabase.table("billing_history").insert({
                            "date": it_str, "company": comp, "amount": total_sum, 
                            "status": "Sent", "due_date": dv_str, "sender": u_m, "received_amount": 0
                        }).execute()

        server.quit()
        st.balloons()
        st.success("Dispatch Finished!")
        time.sleep(2)
        st.rerun()
    except Exception as e:
        st.error(f"Dispatch Error: {e}")
