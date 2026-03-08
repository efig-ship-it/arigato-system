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
# כאן המשתמש מעלה את כל קבצי החשבוניות
uploaded_files = st.file_uploader("Drag and drop all files here", 
                                 type=['pdf', 'xlsx', 'xls'], 
                                 accept_multiple_files=True,
                                 label_visibility="collapsed")

st.write("---")

# חלק 2: פרטי שולח
st.header("2. Sender Details")
user_mail = st.text_input("Your Gmail Address:", placeholder="example@gmail.com")
user_pass = st.text_input("App Password:", type="password")

with st.expander("🔑 How to create an App Password for TMC?"):
    st.markdown("""
    1. Go to Google Account Security.
    2. Turn on 2-Step Verification.
    3. Search for 'App passwords'.
    4. Create a 16-character code and paste it above.
    """)

user_subj = st.text_input("Email Subject:", value=f"Invoice Payment Due - {current_month_year}")

st.write("---")

# פונקציה לשידוך קבצים לחברה
def get_files_for_company(company_name, files_list):
    matched_files = []
    search_name = str(company_name).strip().lower()
    for uploaded_file in files_list:
        if search_name in uploaded_file.name.lower():
            matched_files.append(uploaded_file)
    return matched_files

# כפתור הפעלה
if st.button("Start Bulk Sending", use_container_width=True):
    # בדיקה ראשונית - האם בכלל הועלו קבצים לסל?
    if not uploaded_files:
        st.error("😭 No invoice/report files were uploaded! 😭")
        st.snow()
        st.write("💔 The 'Drag and drop' area is empty. I have nothing to send... 💔")
    
    elif up_ex and user_mail and user_pass:
        try:
            df = pd.read_excel(up_ex)
            prog = st.progress(0)
            status = st.empty()
            
            # ניסיון התחברות
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            sent_count = 0
            total_rows = len(df)

            for i, row in df.iterrows():
                company = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                
                # בדיקת עמודת תאריך (תיקון השגיאה הקודמת)
                day_val = str(row.iloc[2]).strip() if len(df.columns) > 2 else "10"
                due_date = f"{day_val} {current_month_year}"
                
                # שידוך קבצים
                company_files = get_files_for_company(company, uploaded_files)
                
                # שליחה רק אם יש גם מייל וגם לפחות קובץ אחד תואם
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
                else:
                    status.text(f"⚠️ Skipping {company}: Missing files or email.")

                prog.progress((i + 1) / total_rows)
                time.sleep(0.1)

            server.quit()

            # סיכום סופי - בדיקת תוצאה
            if sent_count > 0:
                st.success(f"Successfully sent {sent_count} emails!")
                st.balloons()
            else:
                # אם עברנו על הכל ולא הצלחנו לשלוח כלום
                st.error("😭 0 emails were sent. I couldn't match any files to the companies in your Excel. 😭")
                st.snow()
                st.write("💔 Please check if the file names contain the company names from the Excel list. 💔")

        except Exception as e:
            st.error("---")
            st.error(f"😭 Oh no! A technical error occurred... 😭")
            st.error(f"**Error Details:** {e}")
            st.snow()
            st.write("💔 Check your App Password and Internet connection. 💔")
    else:
        st.warning("Please make sure all fields are filled and the Excel list is uploaded.")
