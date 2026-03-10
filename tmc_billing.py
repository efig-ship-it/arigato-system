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
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    else:
        st.error("🚨 Secrets missing! Go to App Settings -> Secrets and add URL and KEY.")
except Exception as e:
    st.error(f"🚨 Connection Error: {e}")

# --- Page Config ---
st.set_page_config(page_title="TMC Billing Fix", layout="centered")

# --- Functions ---
def get_cloud_history():
    try:
        res = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame()

# --- Page 1: Email Sender ---
if st.sidebar.radio("Go to:", ["Email Sender", "Dashboard", "Control"]) == "Email Sender":
    st.title("TMC Billing System")
    
    # ... (כאן כל הקוד של העלאת הקבצים והאקסל) ...
    up_ex = st.file_uploader("Mailing List", type=['xlsx'])
    uploaded_files = st.file_uploader("Invoices", accept_multiple_files=True)
    
    # הגדרת הבלש
    allow_sending = True
    if up_ex and uploaded_files:
        # בדיקת קבצים (לוגיקה קודמת)
        # אם יש בעיה: 
        # allow_sending = st.toggle("I confirm all is correct")
        pass

    user_mail = st.text_input("Gmail Address")
    user_pass = st.text_input("App Password", type="password")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not user_mail or not user_pass:
            st.warning("Please enter email and password.")
        else:
            try:
                # ניסיון שליחה
                with st.spinner("Processing..."):
                    # כאן הלוגיקה של השליחה שנתתי קודם...
                    # בוא נבדוק רק את השמירה ל-Supabase:
                    test_data = {"Company": "Test", "Amount": 0, "Status": "Sent", "Date": "01/01/2026"}
                    supabase.table("billing_history").insert(test_data).execute()
                    st.success("Test record saved to cloud!")
                    st.balloons()
            except Exception as e:
                # זה החלק שיגיד לנו למה זה לא עובד:
                st.error("❌ היתה שגיאה בשליחה!")
                st.expander("Show Technical Error").code(traceback.format_exc())
