import streamlit as st
import pandas as pd
import smtplib, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# הגדרות דף - רקע לבן ונקי
st.set_page_config(page_title="TMC Hotel Billing", layout="centered")

# עיצוב CSS נקי עם נגיעות של מלון יוקרה
st.markdown("""
    <style>
    /* רקע לבן ונקי */
    .stApp {
        background-color: #ffffff;
    }
    
    /* כותרת בכחול מלכותי */
    h1 {
        color: #1A365D;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        border-bottom: 2px solid #D4AF37; /* קו זהב מתחת לכותרת */
        padding-bottom: 10px;
    }
    
    /* עיצוב תיבות הקלט */
    .stTextInput>div>div>input, .stFileUploader section {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }

    /* כפתור ה-Dispatch בעיצוב "דלת זהב" */
    .stButton>button {
        background-color: #D4AF37; /* זהב */
        color: white;
        border-radius: 10px;
        height: 3em;
        width: 100%;
        font-size: 20px;
        border: 2px solid #B8860B;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #1A365D; /* הופך לכחול במעבר עכבר */
        color: #D4AF37;
        border: 2px solid #D4AF37;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏨 TMC Hotel Billing System")
st.write("Welcome to the TMC Concierge Billing Terminal.")

# פונקציה להשמעת צלילים
def play_sound(sound_type):
    if sound_type == "success":
        sound_url = "https://www.myinstants.com/media/sounds/clapping.mp3"
    else:
        sound_url = "https://www.myinstants.com/media/sounds/sad-trombone.mp3"
    audio_html = f'<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>'
    st.components.v1.html(audio_html, height=0)

# חלק 1: ניהול חדרים וקבצים
st.header("🔑 Room & File Management")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**📁 Guest Mailing List**")
    up_ex = st.file_uploader("Upload Excel", type=['xlsx'], label_visibility="collapsed")
    
with col2:
    st.markdown("**📅 Check-out Month**")
    current_month_year = st.text_input("Month", value="March 2026", label_visibility="collapsed")

st.markdown("**📄 Room Service & Tax Invoices (PDF/Excel)**")
uploaded_files = st.file_uploader("Drop all files for all rooms here", 
                                 type=['pdf', 'xlsx', 'xls'], 
                                 accept_multiple_files=True,
                                 label_visibility="collapsed")

st.write("---")

# חלק 2: עמדת הקונסיירז'
st.header("🛎️ Concierge Station")
user_mail = st.text_input("Hotel Sender Email:", placeholder="billing@arbitrip.com")
user_pass = st.text_input("Station Access Key (App Password):", type="password")
user_subj = st.text_input("Email Subject:", value=f"Final Invoice & Stay Summary - {current_month_year}")

st.write("---")

def get_files_for_company(company_name, files_list):
    matched_files = []
    search_name = str(company_name).strip().lower()
    for uploaded_file in files_list:
        if search_name in uploaded_file.name.lower():
            matched_files.append(uploaded_file)
    return matched_files

# כפתור הפעלה - ה"דלת" לשליחה
if st.button("🚪 Open Door & Dispatch All", use_container_width=True):
    if not uploaded_files:
        st.error("😭 The luggage cart is empty! Please upload files.")
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
                    
                    body = f"Dear {company},\n\nWe hope you enjoyed your stay. Attached are your room reports and invoices.\nPayment is due by {due_date}.\n\nWarm Regards,\nTMC Hotel Team"
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.send_message(msg)
                    sent_count += 1
                    status.text(f"✈️ Room {company}: Delivered")
                
                prog.progress((i + 1) / total_rows)
                time.sleep(0.1)

            server.quit()

            if sent_count > 0:
                st.success(f"🛎️ Reception Task Complete! {sent_count} emails sent.")
                play_sound("success")
                st.balloons()
            else:
                st.error("😭 No matches found. Check-in names don't match file names.")
                play_sound("error")

        except Exception as e:
            st.error(f"😭 Elevator Stuck (Technical Error): {e}")
            play_sound("error")
    else:
        st.warning("Please fill in the guest list and station details.")
