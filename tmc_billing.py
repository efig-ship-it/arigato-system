import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection (🛡️ סעיף 1) ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. CSS & Design (🎨 סעיף 7) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .success-msg { font-size: 100px; font-weight: 900; color: #28a745; text-align: center; margin-top: 20px; }
    .suitcase-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 30px 0; }
    .rtl-guide { text-align: right; direction: rtl; }
</style>""", unsafe_allow_html=True)

# --- 3. Helper Functions ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date_obj'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce').dt.date
            df = df.dropna(subset=['date_obj'])
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            # הכנת Due Date לגרף
            df['due_date_dt'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
        return df
    except: return pd.DataFrame()

def clean_amount(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
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

# --- 4. Navigation ---
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- PAGE 1: EMAIL SENDER ---
if page == "Email Sender":
    st.title("TMC Billing System")
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    with c1: up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1)
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1)
    
    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name for f in uploaded_files]
            missing = [c for c in excel_comps if not any(c.lower() in fn.lower() for fn in file_names)]
            orphans = [fn for fn in file_names if not any(c.lower() in fn.lower() for c in excel_comps)]
            if missing or orphans:
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if missing: st.warning(f"Missing Files: {', '.join(missing)}")
                    if orphans: st.error(f"Unrecognized Files: {', '.join(orphans)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2 = st.columns(2); user_mail = sc1.text_input("Gmail Address"); user_pass = sc2.text_input("App Password", type="password")

    with st.expander("🔑 מדריך ליצירת סיסמת אפליקציה"):
        st.markdown("""<div class="rtl-guide">גוגל דורשת סיסמה בת 16 תווים: 1. כנס לחשבון גוגל > Security. 2. הפעל אימות דו-שלבי. 3. צור App password ל-Mail.</div>""", unsafe_allow_html=True)

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not up_ex or not user_mail: st.error("Missing credentials.")
        else:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                with st.spinner(""):
                    st.markdown("""<div class="suitcase-container"><svg width="50" height="50" viewBox="0 0 24 24" fill="#8B4513" xmlns="http://www.w3.org/2000/svg">
                        <path d="M17,6H16V5c0-1.1-0.9-2-2-2h-4C8.9,3,8,3.9,8,5v1H7C5.9,6,5,6.9,5,8v11c0,1.1,0.9,2,2,2h10c1.1,0,2-0.9,2-2V8 C19,6.9,18.1,6,17,6z M10,5h4v1h-4V5z M17,19H7V8h10V19z"/></svg>
                        <p style='color: #8B4513;'>Invoices are traveling...</p></div>""", unsafe_allow_html=True)
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        total_amt = sum([extract_total_amount_from_file(f) for f in company_files if f.name.endswith('.xlsx')])
                        if emails and company_files:
                            msg = MIMEMultipart(); msg['Subject'] = f"Invoice - {company}"; msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, invoices attached.", 'plain'))
                            for f in company_files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                            server.send_message(msg)
                            it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                            due_val = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                            supabase.table("billing_history").insert({"date": it, "company": company, "amount": total_amt, "status": "Sent", "currency": "$", "due_date": due_val, "sender": user_mail}).execute()
                server.quit(); st.balloons(); st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True); st.audio("https://www.myinstants.com/media/sounds/victory-sound-effect.mp3", format="audio/mp3", autoplay=True); time.sleep(3); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS (📊 Dashboard עם תצוגת Due Date) ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        last_send = df['date'].iloc[0]
        st.info(f"🕒 **Last Invoices Sent On:** {last_send}")
        
        m1, m2, m3 = st.columns(3)
        tb = df['amount'].sum(); tp = df[df['status'] == 'Paid']['amount'].sum()
        m1.metric("Total Billed", f"${tb:,.2f}"); m2.metric("Total Received", f"${tp:,.2f}"); m3.metric("Outstanding", f"${tb-tp:,.2f}")
        
        st.divider()
        st.write("### 📅 Amount by Due Date (Time Projection)")
        # גרף סכומים לפי תאריך יעד
        chart_data = df.groupby('due_date').agg({'amount':'sum'}).reset_index()
        st.bar_chart(data=chart_data, x='due_date', y='amount')
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1: st.write("**Billed by Company**"); st.dataframe(df.groupby('company').agg({'amount':'sum'}).reset_index().style.format({"amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
        with c2: st.write("**Billed by Sending Date**"); st.dataframe(df.groupby('date_obj').agg({'amount':'sum'}).reset_index().style.format({"amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
    else: st.info("No data.")

# --- PAGE 3: CONTROL (🔍 Collections Control 🔍 - עם אפשרות קיפול) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        def highlight_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white;'
            if val == 'Overdue': return 'background-color: #d32f2f; color: white;'
            return ''

        display_cols = ['id', 'company', 'date', 'due_date', 'amount', 'status', 'notes']
        edit_mode = st.toggle("✏️ Edit Mode", value=False)
        
        # טבלה בתוך Expander לקיפול לפי דרישתך
        with st.expander("📋 Click to expand/collapse Billing Records", expanded=True):
            if not edit_mode:
                st.dataframe(df[display_cols].style.map(highlight_status, subset=['status']).format({"amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
            else:
                edited_df = st.data_editor(df[display_cols], column_config={"id": None, "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute", "Overdue"]), "amount": st.column_config.NumberColumn("amount", format="%,.2f")}, disabled=['company', 'date', 'due_date'], hide_index=True, use_container_width=True)
                if st.button("💾 Save Changes"):
                    for _, row in edited_df.iterrows():
                        supabase.table("billing_history").update({"status": row['status'], "notes": str(row.get('notes', '') or ''), "amount": float(row['amount'])}).eq("id", row['id']).execute()
                    st.success("Updated!"); time.sleep(0.5); st.rerun()
    else: st.info("No records.")
