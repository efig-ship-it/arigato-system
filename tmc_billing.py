import streamlit as st
import pandas as pd
import smtplib, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף - נקי ומהודק
st.set_page_config(page_title="TMC Billing System", layout="centered")

st.markdown("""
    <style>
    .block-container { padding-top: 3rem; padding-bottom: 0rem; }
    h1 { margin-top: 1rem !important; margin-bottom: 1rem !important; }
    .stVerticalBlock { gap: 0.6rem; }
    hr { margin: 0.6em 0px; }
    /* יישור תיבת העזרה לגובה השדות */
    .stExpander { margin-top: 28px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("TMC Billing System")

def play_sound(sound_type):
    sound_url = "https://www.myinstants.com/media/sounds/clapping.mp3" if sound_type == "success" else "https://www.myinstants.com/media/sounds/sad-trombone.mp3"
    audio_html = f'<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>'
    st.components.v1.html(audio_html, height=0)

# --- חלק 1: הגדרות וקבצים ---
st.subheader("1. Setup & Files")
c1, c2 = st.columns([2, 1])

with c1:
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    
with c2:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    curr_y = datetime.now().year
    years = [str(y) for y in range(curr_y - 1, curr_y + 3)]
    mc, yc = st.columns(2)
    sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = yc.selectbox("Year", years, index=1)
    current_month_year = f"{sel_m} {sel_y}"

uploaded_files = st.file_uploader("Upload all Invoices & Reports (PDF/Excel)", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

# --- חלק 2: פרטי שולח (הסבר מפורט עם קישור ליד הסיסמה) ---
st.write("---")
st.subheader("2. Sender Details")

# חלוקה ל-3 עמודות: מייל, סיסמה, והסבר מפורט
sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])

user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
user_pass = sc2.text_input("App Password", type="password")

with sc3:
    with st.expander("🔑 How to create an App Password?"):
        st.markdown("""
        To send emails via Gmail, you need a unique **App Password**.
        *Standard login passwords will not work.*

        1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
        2. Make sure **2-Step Verification** is turned **ON**.
        3. Search for **'App passwords'** in the top search bar.
        4. Select a name (e.g., "TMC Billing") and click **Create**.
        5. Copy the **16-character code** and paste it here.
        """)

user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

# --- לוגיקה ---
def get_files_for_company(company_name, files_list):
    search_name = str(company_name).strip().lower()
    return [f for f in files_list if search_name in f.name.lower()]

if st.button("🚀 Start Bulk Sending", use_container_width=True):
    if not uploaded_files or not up_ex or not user_mail or not user_pass:
        st.warning("Please fill all fields and upload files.")
    else:
        try:
            df = pd.read_excel(up_ex)
            prog = st.progress(0)
            status = st.empty()
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            sent_count = 0
            for i, row in df.iterrows():
                company = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                day_val = str(row.iloc[2]).strip() if len(df.columns) > 2 else "10"
                due_date = f"{day_val} {current_month_year}"
                
                company_files = get_files_for_company(company, uploaded_files)
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'], msg['To'], msg['Subject'] = user_mail, ", ".join(emails), f"{user_subj} - {company}"
                    body = f"Hi,\n\nAttached are the invoice and report for {company}.\nPayment is due by {due_date}.\n\nBest Regards,\nTMC Team"
                    msg.attach(MIMEText(body, 'plain'))
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    sent_count += 1
                prog.progress((i + 1) / len(df))
            
            server.quit()
            if sent_count > 0:
                st.success(f"Successfully sent {sent_count} emails!")
                play_sound("success")
                st.balloons()
            else:
                st.error("0 emails were sent. No matches found.")
                play_sound("error")
        except Exception as e:
            st.error(f"Error: {e}")
            play_sound("error")
