import streamlit as st
import pandas as pd
import os, smtplib, time, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# הגדרות דף - מראה נקי ומקצועי
st.set_page_config(page_title="TMC Billing System", layout="centered")

# כותרת המערכת
st.title("TMC Billing System")
st.write("---")

# חלק 1: העלאת קבצים והגדרות חודש
st.header("1. Upload & Configuration")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Upload Excel Database**")
    # העלאת קובץ האקסל ישירות לממשק (במקום נתיב קבוע)
    up_ex = st.file_uploader("Upload Excel", type=['xlsx'], label_visibility="collapsed")
    
with col2:
    current_month_year = st.text_input("Current Month & Year", value="March 2024")

# הגדרת נתיב התיקייה בדרייב (לחיפוש החשבוניות)
base_path = st.text_input("Google Drive Invoices Path:", 
                         value=f"/content/drive/MyDrive/Invoices_Folders/{current_month_year}/")

st.write("---")

# חלק 2: פרטי שולח והסבר סיסמה
st.header("2. Sender Details")

user_mail = st.text_input("Your Gmail Address:", value="galo@arbitrip.com")
user_pass = st.text_input("App Password:", type="password")

# רכיב מתקפל עם ההסבר לבקשתך
with st.expander("🔑 How to create an App Password for TMC?"):
    st.markdown("""
    To send emails via Gmail, you need a unique **App Password**. 
    *Standard login passwords will not work.*
    
    1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
    2. Make sure **2-Step Verification** is turned **ON**.
    3. Scroll down or search for **'App passwords'**.
    4. Select an app name (e.g., "TMC Billing") and click **Create**.
    5. Copy the **16-character code** (without spaces) and paste it in the field above.
    """)

email_subject = st.text_input("Email Subject:", value=f"Invoice Payment Due - {current_month_year}")

st.write("---")

# פונקציות עזר
def find_files_for_company(company_name, folder_root):
    folder_path = os.path.join(folder_root, company_name)
    pdf_file, excel_file = None, None
    if not os.path.exists(folder_path):
        return None, None, folder_path
    
    for filename in os.listdir(folder_path):
        lower_name = filename.lower()
        full_path = os.path.join(folder_path, filename)
        if lower_name.endswith('.pdf') and not pdf_file:
            pdf_file = full_path
        elif (lower_name.endswith('.xlsx') or lower_name.endswith('.xls')) and not excel_file:
            excel_file = full_path
    return pdf_file, excel_file, folder_path

# כפתור הפעלה
if st.button("Start Bulk Sending", use_container_width=True):
    if up_ex and user_mail and user_pass:
        try:
            # קריאת האקסל שהועלה
            df = pd.read_excel(up_ex)
            prog = st.progress(0)
            status = st.empty()
            
            # התחברות לשרת
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            sent_count = 0
            for i, row in df.iterrows():
                company = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                day_val = str(row.iloc[2]).strip() if len(row.columns) > 2 else "10"
                full_due_date = f"{day_val} {current_month_year}"
                
                # חיפוש קבצים בנתיב הדרייב שהוזן
                pdf_p, excel_p, f_path = find_files_for_company(company, base_path)
                
                if pdf_p and excel_p:
                    msg = MIMEMultipart()
                    msg['From'] = user_mail
                    msg['To'] = ", ".join(emails)
                    msg['Subject'] = f"{email_subject} - {company}"
                    
                    body = f"Hi,\n\nAttached is the report and invoice for {company}.\nPayment is due by {full_due_date}.\n\nBest Regards,\nTMC Team"
                    msg.attach(MIMEText(body, 'plain'))
                    
                    for p in [pdf_p, excel_p]:
                        with open(p, "rb") as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(p))
                            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(p)}"'
                            msg.attach(part)
                    
                    server.sendmail(user_mail, emails, msg.as_string())
                    sent_count += 1
                    status.text(f"✅ Sent to: {company}")
                else:
                    st.error(f"❌ Missing files for {company} in {f_path}")
                
                prog.progress((i + 1) / len(df))
                time.sleep(0.1)
                
            server.quit()
            st.success(f"Finished! Total {sent_count} emails sent.")
            st.balloons()
            
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("Please upload Excel and fill in all details.")
