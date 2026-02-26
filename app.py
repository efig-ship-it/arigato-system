import streamlit as st
import pandas as pd
from docx import Document
import io, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Basic Page Config
st.set_page_config(page_title="Arigato Billing System", layout="centered")

# App Header
st.title("Arigato Billing System")
st.markdown("---")

# Constant Settings
MY_APP_PASSWORD = "nwfk odkt qzzc whhv"

# Step 1: File Upload
st.subheader("Step 1: Upload Files")
col1, col2 = st.columns(2)

with col1:
    up_ex = st.file_uploader("Upload Excel (.xlsx)", type=['xlsx'])
with col2:
    up_wd = st.file_uploader("Upload Template (.docx)", type=['docx'])

# Data placeholders
df = None
template_text = ""

# Process Excel
if up_ex:
    try:
        excel_bytes = up_ex.read()
        df = pd.read_excel(io.BytesIO(excel_bytes), engine='openpyxl')
        df.columns = [str(col).strip().upper() for col in df.columns]
        
        # Look for Company and Email columns
        c_col = next((c for c in df.columns if c in ['COMPANY', 'NAME', 'חברה', 'שם חברה']), None)
        e_col = next((c for c in df.columns if c in ['EMAIL', 'MAIL', 'מייל', 'אימייל']), None)
        
        if c_col and e_col:
            st.success(f"Excel loaded! Found {len(df)} rows.")
            st.session_state['c_col'] = c_col
            st.session_state['e_col'] = e_col
        else:
            st.error("Could not find Company or Email columns in Excel.")
    except Exception as e:
        st.error(f"Error reading Excel: {str(e)}")

# Process Word
if up_wd:
    try:
        word_bytes = up_wd.read()
        doc = Document(io.BytesIO(word_bytes))
        template_text = "\n".join([p.text for p in doc.paragraphs])
        if template_text.strip():
            st.success("Word template loaded!")
    except Exception as e:
        st.error(f"Error reading Word: {str(e)}")

# Step 2: Email Details
st.markdown("---")
st.subheader("Step 2: Sending Details")
mail_in = st.text_input("Your Gmail Address:")
subj_in = st.text_input("Email Subject:")

# Step 3: Execution
if st.button("Start Sending Emails"):
    if df is not None and template_text and mail_in and subj_in:
        prog = st.progress(0)
        status = st.empty()
        
        c_col = st.session_state.get('c_col')
        e_col = st.session_state.get('e_col')

        try:
            # Login to SMTP
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(mail_in.strip(), MY_APP_PASSWORD.replace(" ", ""))

            count = 0
            for i, row in df.iterrows():
                if pd.isna(row[c_col]) or pd.isna(row[e_col]):
                    continue
                
                # Build Message
                msg = MIMEMultipart()
                msg['From'] = mail_in.strip()
                msg['To'] = str(row[e_col]).strip()
                msg['Subject'] = subj_in.strip()
                
                # Replace tag
                body = template_text.replace("{COMPANY}", str(row[c_col]))
                msg.attach(MIMEText(body, 'plain', 'utf-8'))

                server.send_message(msg)
                count += 1
                
                # Update Progress
                prog.progress((i + 1) / len(df))
                status.text(f"Sent to: {row[c_col]}")
                time.sleep(0.3)

            server.quit()
            st.success(f"Done! {count} emails sent successfully.")
            st.balloons()
        except Exception as e:
            st.error(f"Error during sending: {str(e)}")
    else:
        st.warning("Please upload files and fill all fields.")
