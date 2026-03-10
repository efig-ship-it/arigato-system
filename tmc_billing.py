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
except Exception as e:
    st.error("🚨 Missing Secrets! Please check SUPABASE_URL and SUPABASE_KEY in Streamlit Settings.")

# --- Page Config ---
st.set_page_config(page_title="TMC Billing System PRO", layout="centered")

# --- Database Fetch Function ---
def get_cloud_history():
    try:
        # שם הטבלה המעודכן ללא נקודה
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame()

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Navigation ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- Page 1: Email Sender ---
if page == "Email Sender":
    st.title("TMC Billing System")
    st.subheader("1. Setup & Files")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1, label_visibility="collapsed")
        current_period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            comp_col = df_ex.columns[0]
            excel_comps = [str(c).strip() for c in df_ex[comp_col].dropna().unique()]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            if orphans:
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    sound_detective()
                    st.markdown('<p style="font-size:100px; text-align:center;">🕵️‍♂️</p>', unsafe_allow_html=True)
                    st.error(f"Unrecognized files found: {', '.join(orphans)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2 = st.columns(2)
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                day_col = next((c for c in df_master.columns if 'day' in str(c).lower()), None)
                month_idx = months.index(sel_m) + 1
                
                for i, row in df_master.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    target_day = int(row[day_col]) if day_col and not pd.isna(row[day_col]) else 15
                    due_date_val = date(int(sel_y), month_idx, target_day).strftime("%Y-%m-%d")
                    
                    total_amount = 0.0
                    currency = "$"
                    # לוגיקת סכימת סכומים וזיהוי מטבע (זהה לקוד הקודם)
                    
                    if emails and company_files:
                        # שליחת המייל...
                        
                        # שמירה לענן לטבלה החדשה
                        data = {
                            "Date": datetime.now().strftime("%d/%m/%Y"),
                            "Company": company,
                            "Amount": float(total_amount),
                            "Status": "Sent",
                            "Due_Date": due_date_val,
                            "Currency": currency,
                            "Sender": user_mail
                        }
                        supabase.table("billing_history").insert(data).execute()
                
                server.quit(); sound_success(); st.balloons(); st.success("Success!"); time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- Page 2: Dashboard ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        c1, c2 = st.columns(2)
        sel_comp = c1.multiselect("Filter by Company", options=sorted(df['Company'].unique()))
        # הפילטרים משתמשים ב-billing_history
        f_df = df[df['Company'].isin(sel_comp)] if sel_comp else df
        st.metric("Total Billed", f"${f_df['Amount'].sum():,.2f}")
    else: st.info("No data in cloud.")

# --- Page 3: Collections Control ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        edited_df = st.data_editor(df, hide_index=True, use_container_width=True)
        if st.button("💾 Save All Changes"):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({"Status": row['Status'], "Notes": row['Notes']}).eq("id", row['id']).execute()
            st.success("Cloud Updated!"); st.rerun()
