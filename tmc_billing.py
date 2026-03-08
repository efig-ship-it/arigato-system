import streamlit as st
import pandas as pd
import smtplib, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# הגדרות דף - TMC Billing System
st.set_page_config(page_title="TMC Billing System", layout="centered")

st.title("TMC Billing System")
st.write("---")

# פונקציה להשמעת צלילים (הצלחה/כישלון)
def play_sound(sound_type):
    if sound_type == "success":
        # הצליל שבחרת: מחיאות כפיים
        sound_url = "https://www.myinstants.com/media/sounds/clapping.mp3"
    else:
        # צליל טרומבון עצוב (קצר)
        sound_url = "https://www.myinstants.com/media/sounds/sad-trombone.mp3"
        
    audio_html = f"""
        <audio autoplay>
            <source src="{sound_url}" type="audio/mp3">
        </audio>
    """
    st.components.v1.html(audio_html, height=0)

# חלק 1: העלאת קבצים
st.header("1. Upload Files")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**1. Upload Mailing List (Excel)**")
    up_ex = st.file_uploader("Upload Excel List", type=['xlsx'], label_visibility="collapsed")
    
with col2:
    st.markdown("**2. Current Month & Year**")
    current_month_year = st.text_input("Month/Year", value="March 2026", label_visibility="collapsed")

st.markdown("**3. Upload all Invoices & Reports (PDF/Excel)**")
uploaded_files = st.file_uploader("Drag and drop all files here", 
                                 type=['pdf', 'xlsx', 'xls'], 
                                 accept_multiple_files=True,
                                 label_visibility="collapsed")

st.write("---")

# חלק 2: פרטי שולח
st.header("2. Sender Details")
user_mail = st.text_input("Your Gmail Address:", placeholder="example@gmail.com")
user_pass = st.text_input("App Password:", type="password")

user_subj = st.text_input("Email Subject:", value=f"Invoice Payment Due - {current_month_year}")

st.write("---")

# פונקציה לחיפוש קבצים לפי שם חברה
def get_files_for_company(company_name, files_list):
    matched_files = []
    search_name = str(company_name).strip().lower()
    for uploaded_file in files_list:
        if search_name in uploaded_file.name.lower():
            matched_files.append(uploaded_file)
    return matched_files

# כפתור הפעלה
if st.button("Start Bulk Sending", use_container_width=True):
    # בדיקה אם הועלו קבצים נספחים
    if not uploaded_files:
        st.error("😭 NO FILES UPLOADED! 😭")
        play_sound("error")
        st.write("💔 Please drag and drop your invoice files first.")
    
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
                
                # שימוש ב-df.columns למניעת שגיאת ה-Series הקודמת
                day_val = str(row.iloc[2]).strip() if len(df.columns) > 2 else "10"
                due_date = f"{day_val} {current_month_year}"
                
                company_files = get_files_for_company(company, uploaded_files)
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'] = user_mail
                    msg['To'] = ", ".join(emails)
                    msg['Subject'] = f"{user_subj} - {company}"
                    
                    body = f"Hi,\n\nAttached are the invoice and report for {company}.\nPayment is due by {due_date}.\n\nBest Regards,\nTMC Team"
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.send_message(msg)
                    sent_count += 1
                    status.text(f"✅ Sent to: {company}")
                
                prog.progress((i + 1) / total_rows)
                time.sleep(0.1)

            server.quit()

            if sent_count > 0:
                st.success(f"Successfully sent {sent_count} emails!")
                play_sound("success") # השמעת מחיאות כפיים! 👏
                st.balloons()
            else:
                st.error("😭 0 EMAILS SENT! 😭")
                play_sound("error")
                st.write("💔 No matching files found. Check your file names.")

        except Exception as e:
            st.error(f"😭 TECHNICAL ERROR: {e}")
            play_sound("error")
    else:
        st.warning("Please fill in all details and upload the mailing list.")
