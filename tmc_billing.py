import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection (נאמן לחוזה) ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. UI CSS (Tuesday Style) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .main { background-color: #f4f7f9; }
    div[data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 700 !important; }
    div[data-testid="stMetricLabel"] { font-size: 12px !important; }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e1e8ed; padding: 10px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    h1 { color: #1a202c; font-weight: 800; margin-bottom: 20px; }
    .alert-box { border-right: 6px solid #003366; margin-bottom: 25px; padding: 15px; background: white; border-radius: 10px; border: 1px solid #e1e8ed; }
    .risk-box { border: 2px solid #e53e3e; background-color: #fff5f5; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    .detective-box { border: 2px solid #ed8936; background-color: #fffaf0; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    .log-box { background-color: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e0e4e8; border-right: 4px solid #003366; margin-bottom: 8px; font-size: 13px; direction: rtl; }
    .success-msg { font-size: 80px; font-weight: 900; color: #28a745; text-align: center; margin-top: 10px; display: block; }
    .tuesday-header { font-size: 28px; font-weight: 900; color: #003366; margin-bottom: 10px; padding-left: 5px; }
</style>""", unsafe_allow_html=True)

# --- 3. Helper Functions ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date_sent_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['date_sent_dt'])
            df['date_sent_obj'] = df['date_sent_dt'].dt.date
            df['date_sent_str'] = df['date_sent_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            df['received_amount'] = pd.to_numeric(df.get('received_amount', 0), errors='coerce').fillna(0.0)
            df['due_date_dt'] = pd.to_datetime(df['due_date'], errors='coerce')
            df['due_date_obj'] = df['due_date_dt'].dt.date
            today = date.today()
            def auto_status(row):
                if row['status'] == 'Paid': return 'Paid'
                if pd.notna(row['due_date_obj']) and row['due_date_obj'] < today: return 'Overdue'
                return row['status']
            df['status'] = df.apply(auto_status, axis=1)
            df['due_date_str'] = df['due_date_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
            df['month_sent'] = df['date_sent_dt'].dt.strftime('%b %Y')
            df['balance'] = df['amount'] - df['received_amount']
            def extract_days(note, sent_date):
                match = re.search(r'Paid on (\d{2}/\d{2}/\d{2})', str(note))
                if match and not pd.isna(sent_date):
                    try:
                        p_dt = pd.to_datetime(match.group(1), format='%d/%m/%y')
                        return (p_dt - sent_date).days
                    except: return None
                return None
            df['days_to_pay'] = df.apply(lambda r: extract_days(r['notes'], r['date_sent_dt']), axis=1)
        return df
    except: return pd.DataFrame()

def clean_amount(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        clean_val = re.sub(r'[^\d.]', '', str(val))
        return float(clean_val) if clean_val else 0.0
    except: return 0.0

def extract_total_amount_from_file(uploaded_file):
    try:
        temp_df = pd.read_excel(uploaded_file)
        temp_df.columns = [str(c).lower().strip() for c in temp_df.columns]
        if 'amount' in temp_df.columns:
            amounts = pd.to_numeric(temp_df['amount'].apply(clean_amount), errors='coerce').fillna(0.0)
            return float(amounts.sum())
    except: pass
    return 0.0

def add_log_entry(item_id, entry_text):
    current_time = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%y %H:%M")
    new_entry = f"[{current_time}] {entry_text}"
    res = supabase.table("billing_history").select("notes").eq("id", item_id).execute()
    old_notes = res.data[0]['notes'] if res.data and res.data[0]['notes'] else ""
    updated = f"{old_notes}\n{new_entry}".strip() if old_notes else new_entry
    supabase.table("billing_history").update({"notes": updated}).eq("id", item_id).execute()

# --- 4. Sidebar ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)
page = st.sidebar.radio("Navigation", ["Email Sender 📧", "Analytics Dashboard 📊", "Collections Control 🔍", "Reminders Manager 🚨"])

# --- PAGE 1: EMAIL SENDER (Risk + Detective + Name Validation) ---
if page == "Email Sender 📧":
    st.title("Invoicing Center")
    col_up, col_due = st.columns([2, 1])
    with col_up: up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_due:
        st.markdown('<p style="font-weight:700; color:#4a5568;">SET DUE DATE</p>', unsafe_allow_html=True)
        mc, yc = st.columns(2); months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1); sel_y = yc.selectbox("Year", ["2025", "2026", "2027"], index=1)
    uploaded_files = st.file_uploader("Drop Company Invoices Here", accept_multiple_files=True)
    
    risk_cleared, detective_cleared = True, True
    if up_ex:
        df_history = get_cloud_history()
        try:
            df_ex = pd.read_excel(up_ex); current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            risk_threshold = date.today() - timedelta(days=30)
            bad_debtors = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            if not bad_debtors.empty:
                risk_cleared = st.checkbox("🚨 אני מאשר שבדקתי את חובות העבר (Risk Control)", value=False)
                if not risk_cleared:
                    st.markdown('<div class="risk-box">⚠️ <b>Risk Alert:</b> חובות מעל חודש:</div>', unsafe_allow_html=True)
                    for _, row in bad_debtors.drop_duplicates('company').iterrows(): st.error(f"● {row['company']} - ${row['balance']:,.2f}")
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
            name_issue = "emails" not in up_ex.name.lower()
            if missing or name_issue:
                detective_cleared = st.checkbox("🕵️‍♂️ אני מאשר תקינות קבצים (Detective)", value=False)
                if not detective_cleared:
                    st.markdown('<div class="detective-box">🔍 <b>Detective Alert:</b></div>', unsafe_allow_html=True)
                    if name_issue: st.warning("קובץ המיילים אינו מכיל 'Emails' בשמו.")
                    if missing: st.warning(f"חסרים קבצים עבור: {', '.join(missing)}")
        except: pass
    st.write("---")
    with st.expander("💡 App Password Link"): st.markdown("[Google Settings](https://myaccount.google.com/apppasswords)")
    sc1, sc2 = st.columns(2); u_m = sc1.text_input("Gmail Account"); u_p = sc2.text_input("App Password", type="password")
    if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (up_ex and uploaded_files and risk_cleared and detective_cleared)):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(u_m.strip(), u_p.strip().replace(" ",""))
            with st.spinner("Traveling..."):
                for i, row in df_master.iterrows():
                    comp, emails = str(row.iloc[0]).strip(), [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    amt = sum([extract_total_amount_from_file(f) for f in files])
                    if emails and files:
                        msg = MIMEMultipart(); msg['Subject'] = f"Invoice - {comp}"; msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Dear {comp}, find invoices attached.", 'plain'))
                        for f in files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        server.send_message(msg)
                        it, dv = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M"), f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        supabase.table("billing_history").insert({"date": it, "company": comp, "amount": amt, "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0}).execute()
                server.quit(); st.balloons(); st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True); time.sleep(3); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS DASHBOARD (CEI + TOP DEBTORS) ---
elif page == "Analytics Dashboard 📊":
    st.title("Analytics Dashboard")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        # פילטרים גלובליים
        st.subheader("Global Filters")
        f1, f2, f3 = st.columns(3)
        sel_comps = f1.multiselect("Companies", sorted(df_raw['company'].unique()))
        send_range = f2.date_input("Send Range", value=(df_raw['date_sent_obj'].min(), df_raw['date_sent_obj'].max()))
        due_range = f3.date_input("Due Range", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
        
        df = df_raw.copy()
        if sel_comps: df = df[df['company'].isin(sel_comps)]
        if isinstance(send_range, tuple) and len(send_range) == 2: df = df[(df['date_sent_obj'] >= send
