import streamlit as st
import pandas as pd
import smtplib, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# הגדרות דף ועיצוב מלונות מותאם אישית
st.set_page_config(page_title="TMC Hotel Billing", layout="centered")

# הזרקת CSS לעיצוב בסגנון עולם הנסיעות
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0.8)), 
                    url('https://images.unsplash.com/photo-1455587734955-081b22074882?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80');
        background-size: cover;
    }
    h1 {
        color: #1A365D; /* כחול כהה של מלונות יוקרה */
        font-family: 'serif';
        text-shadow: 1px 1px 2px #ccc;
    }
    .stButton>button {
        background-color: #D4AF37; /* צבע זהב */
        color: white;
        border-radius: 20px;
        border: none;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #B8860B;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏨 TMC Hotel Billing System")
st.subheader("Travel & Invoice Management Console")
st.write("---")

# פונקציה להשמעת צלילים
def play_sound(sound_type):
    if sound_type == "success":
        sound_url = "https://www.myinstants.com/media/sounds/clapping.mp3"
    else:
        sound_url = "https://www.myinstants.com/media/sounds/sad-trombone.mp3"
    audio_html = f'<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>'
    st.components.v1.html(audio_html, height=0)

# חלק 1: העלאת קבצים
st.header("🛂 1. Check-in Information")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**📁 Mailing List (Excel)**")
    up_ex = st.file_uploader("Upload Excel", type=['xlsx'], label_visibility="collapsed")
    
with col2:
    st.markdown("**📅 Billing Month**")
    current_month_year = st.text_input("Month", value="March 2026", label_visibility="collapsed")

st.markdown("**📄 Upload Invoices & Reports (PDF/Excel)**")
uploaded_files = st.file_uploader("Drop Room Reports & Invoices Here", 
                                 type=['pdf', 'xlsx', 'xls'], 
                                 accept_multiple_files=True,
                                 label_visibility="collapsed")

st.write("---")

# חלק 2: פרטי שולח
st.header("📧 2. Concierge Details")
user_mail = st.text_input("Your Business Gmail:", placeholder="concierge@arbitrip.com")
user_pass = st.text_input("App Password:", type="password")
user_subj = st.text_input("Subject Line:", value=f"Your Stay Report & Invoice - {current_month_year}")

st.write("---")

def get_files_for_company(company_name, files_list):
    matched_files = []
    search_name = str(company_name).strip().lower()
    for uploaded_file in files_list:
        if search_name in uploaded_file.name.lower():
            matched_files.append(uploaded_file)
    return matched_files

# כפתור הפעלה בעיצוב זהב
if st.button("🚀 Dispatch Invoices (Take Off)", use_container_width=True):
    if not uploaded_files:
        st.error("😭 No baggage (files) uploaded! 😭")
        play_sound("error")
    elif up_ex and user_mail and user_pass:
        try:
            df = pd.read_excel(up_ex)
            prog = st.progress(0)
            status = st.empty()
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            sent_count = 0
            total_rows = len(df)

            for i, row in df.iterrows():
                company = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                day_val = str(row.iloc[2]).strip() if len(df.columns) > 2 else "10"
                due_date = f"{day_val} {current_month_year}"
                
                company_files = get_files_for_company(company, uploaded_files)
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'] = user_mail
                    msg['To'] = ", ".join(emails)
                    msg['Subject'] = f"{user_subj} - {company}"
                    
                    body = f"Dear Client,\n\nPlease find attached the detailed stay report and invoice for {company}.\nPayment is due by {due_date}.\n\nSafe Travels,\nTMC Billing Team"
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.send_message(msg)
                    sent_count += 1
                    status.text(f"✈️ Flying to: {company}")
                
                prog.progress((i + 1) / total_rows)
                time.sleep(0.1)

            server.quit()

            if sent_count > 0:
                st.success(f"Bon Voyage! {sent_count} emails delivered.")
                play_sound("success")
                st.balloons()
            else:
                st.error("😭 Flight cancelled! 0 matches found. 😭")
                play_sound("error")

        except Exception as e:
            st.error(f"😭 Turbulence (Technical Error): {e}")
            play_sound("error")
    else:
        st.warning("Please fill in the guest list and concierge details.")
