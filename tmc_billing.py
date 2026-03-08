import streamlit as st
import pandas as pd
import smtplib, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# הגדרות דף
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
# העלאה מרובה של קבצים
uploaded_files = st.file_uploader("Drag and drop all files here", 
                                 type=['pdf', 'xlsx', 'xls'], 
                                 accept_multiple_files=True,
                                 label_visibility="collapsed")

if uploaded_files:
    st.info(f"📂 {len(uploaded_files)} files uploaded. Matching logic is ready.")

st.write("---")

# חלק 2: פרטי שולח והסבר סיסמה
st.header("2. Sender Details")

user_mail = st.text_input("Your Gmail Address:", placeholder="example@gmail.com")
user_pass = st.text_input("App Password:", type="password")

with st.expander("🔑 How to create an App Password for TMC?"):
    st.markdown("""
    To send emails via Gmail, you need a unique **App Password**. 
    *Standard login passwords will not work.*
    
    1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
    2. Make sure **2-Step Verification** is turned **ON**.
    3. Search for **'App passwords'** in the top search bar.
    4. Select a name (e.g., "TMC Billing") and click **Create**.
    5. Copy the **16-character code** and paste it above.
    """)

user_subj = st.text_input("Email Subject:", value=f"Invoice Payment Due - {current_month_year}")

st.write("---")

# לוגיקת התאמת קבצים
def get_files_for_company(company_name, files_list):
    """מחפש קבצים שהשם שלהם מכיל את שם החברה"""
    matched_files = []
    search_name = str(company_name).strip().lower()
    
    for uploaded_file in files_list:
        if search_name in uploaded_file.name.lower():
            matched_files.append(uploaded_file)
            
    return matched_files

# כפתור הפעלה
if st.button("Start Bulk Sending", use_container_width=True):
    if up_ex and uploaded_files and user_mail and user_pass:
        try:
            # קריאת האקסל הראשי
            df = pd.read_excel(up_ex)
            prog = st.progress(0)
            status = st.empty()
            
            # התחברות לשרת
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            sent_count = 0
            total_rows = len(df)

            for i, row in df.iterrows():
                # חילוץ נתונים מהשורות
                company = str(row.iloc[0]).strip()
                emails_raw = str(row.iloc[1]).split(',')
                emails = [e.strip() for e in emails_raw if '@' in e]
                
                # תיקון השגיאה: בדיקת כמות העמודות מתבצעת מול ה-df
                if len(df.columns) > 2:
                    day_val = str(row.iloc[2]).strip()
                else:
                    day_val = "10"
                
                due_date = f"{day_val} {current_month_year}"
                
                # חיפוש קבצים מתוך הרשימה שהועלתה
                company_files = get_files_for_company(company, uploaded_files)
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'] = user_mail
                    msg['To'] = ", ".join(emails)
                    msg['Subject'] = f"{user_subj} - {company}"
                    
                    body = f"Hi,\n\nAttached are the invoice and report for {company}.\nPayment is due by {due_date}.\n\nBest Regards,\nTMC Team"
                    msg.attach(MIMEText(body, 'plain', 'utf-8'))
                    
                    # צירוף הקבצים שנמצאו
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.sendmail(user_mail, emails, msg.as_string())
                    sent_count += 1
                    status.text(f"✅ Sent to: {company}")
                else:
                    if not emails:
                        st.warning(f"⚠️ No valid email found for {company}. Skipping...")
                    else:
                        st.warning(f"⚠️ No files found for {company}. Skipping...")

                prog.progress((i + 1) / total_rows)
                time.sleep(0.1)

            server.quit()
            st.success(f"Successfully sent {sent_count} emails!")
            st.balloons()

        except Exception as e:
            st.error(f"Error during process: {e}")
    else:
        st.warning("Please make sure to upload the Excel list, the invoice files, and fill in your details.")
