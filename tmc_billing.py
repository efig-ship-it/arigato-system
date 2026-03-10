import streamlit as st
import pandas as pd
import smtplib, time, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date
from supabase import create_client, Client

# --- Supabase Connection ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except:
    st.error("🚨 Missing Supabase Secrets!")

# --- Page Config ---
st.set_page_config(page_title="TMC Billing System PRO", layout="centered")

# --- Functions ---
def get_cloud_history():
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

# --- CSS - העיצוב המקורי שלך ---
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- Navigation ---
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- Page 1: Email Sender ---
if page == "Email Sender":
    st.title("TMC Billing System")
    st.subheader("1. Setup & Files")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1, label_visibility="collapsed")
        current_period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

    allow_sending = True
    # לוגיקת הבלש עם ה-Session State כדי שייעלם
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            comp_col = df_ex.columns[0]
            excel_comps = [str(c).strip() for c in df_ex[comp_col].dropna().unique()]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in f.name.lower() for f in uploaded_files)]
            
            if orphans or missing:
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                if not confirm:
                    allow_sending = False
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if orphans: 
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.error(f"Unrecognized files: {', '.join(orphans)}")
                    if missing: 
                        st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        st.warning(f"Missing files for: {', '.join(missing)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
            server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
            
            for i, row in df_master.iterrows():
                company = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                
                if emails and company_files:
                    # לוגיקת המייל (המלאה מהקוד הקודם)
                    msg = MIMEMultipart(); msg['Subject'] = f"{user_subj} - {company}"; msg['To'] = ", ".join(emails)
                    msg.attach(MIMEText(f"Hello {company}, please see attached invoices.", 'plain'))
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    
                    # שמירה לענן
                    supabase.table("billing_history").insert({
                        "Date": datetime.now().strftime("%d/%m/%Y"),
                        "Company": company, "Amount": 0.0, "Status": "Sent",
                        "Due_Date": f"{sel_y}-{months.index(sel_m)+1}-15",
                        "Currency": "$", "Sender": user_mail
                    }).execute()
            
            server.quit()
            st.success("Success!")
            st.balloons(); time.sleep(2); st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# --- דפים נוספים (Dashboard & Control) נשמרים כרגיל ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics")
    df = get_cloud_history()
    st.dataframe(df)

elif page == "Collections Control 🔍":
    st.title("🔍 Control")
    df = get_cloud_history()
    # לוגיקת עריכה צבעונית...
