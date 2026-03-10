import streamlit as st
import pandas as pd
import smtplib, time, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date
from supabase import create_client, Client

# --- 1. Supabase Connection Check ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    else:
        st.warning("⚠️ Supabase Secrets are missing in Streamlit Settings.")
except Exception as e:
    st.error(f"🚨 Supabase Connection Error: {e}")

# --- Page Config ---
st.set_page_config(page_title="TMC Billing System PRO", layout="centered")

# --- Database Fetch ---
def get_cloud_history():
    if supabase is None: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

# --- Audio ---
def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Navigation ---
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- Page 1: Email Sender ---
if page == "Email Sender":
    st.markdown("""<style>
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; }
    </style>""", unsafe_allow_html=True)

    st.title("TMC Billing System")
    
    # Files Upload
    up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'])
    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

    # Detective Logic
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip().lower() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name.lower() for f in uploaded_files]
            
            orphans = [f.name for f in uploaded_files if not any(c in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c in fname for fname in file_names)]
            
            if orphans or missing:
                st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                st.markdown('<p class="detective-header">Alert!</p>', unsafe_allow_html=True)
                if orphans: st.error(f"Unrecognized files: {', '.join(orphans)}")
                if missing: st.warning(f"Missing files for: {', '.join(missing)}")
                
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
        except Exception as e:
            st.error(f"Error reading files: {e}")

    # Credentials
    st.write("---")
    user_mail = st.text_input("Gmail Address")
    user_pass = st.text_input("App Password", type="password")
    user_subj = st.text_input("Email Subject", value="Invoice Payment Due")

    # --- THE BUTTON ---
    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not user_mail or not user_pass:
            st.error("❌ Missing Gmail address or App Password!")
        elif supabase is None:
            st.error("❌ Database not connected. Check Secrets!")
        elif not up_ex or not uploaded_files:
            st.error("❌ Please upload files first.")
        else:
            try:
                with st.spinner("Processing..."):
                    df_master = pd.read_excel(up_ex).dropna(how='all')
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                    
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        
                        if emails and company_files:
                            # (כאן לוגיקת יצירת המייל - מקוצר לצורך תצוגה)
                            msg = MIMEMultipart()
                            msg['Subject'] = f"{user_subj} - {company}"
                            msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, please see attached invoices.", 'plain'))
                            
                            for f in company_files:
                                part = MIMEApplication(f.getvalue(), Name=f.name)
                                part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                                msg.attach(part)
                            
                            server.send_message(msg)
                            
                            # שמירה ל-Supabase
                            supabase.table("billing_history").insert({
                                "Date": datetime.now().strftime("%d/%m/%Y"),
                                "Company": company,
                                "Amount": 0.0, # כאן אפשר להוסיף את לוגיקת הסכום
                                "Status": "Sent",
                                "Due_Date": datetime.now().strftime("%Y-%m-%d"),
                                "Currency": "$",
                                "Sender": user_mail
                            }).execute()
                    
                    server.quit()
                    sound_success()
                    st.balloons()
                    st.success("✅ Success! Emails sent and saved to cloud.")
            except Exception as e:
                st.error("❌ Sending Failed!")
                st.exception(e) # מציג את השגיאה המדויקת

# (דף הדשבורד והבקרה נשארים אותו דבר...)
