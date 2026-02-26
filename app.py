import streamlit as st
import pandas as pd
from docx import Document
import io, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

st.set_page_config(page_title="Arigato Billing", layout="centered")

st.title("Arigato Billing System")
st.write("---")

st.header("1. Upload Files")
col1, col2 = st.columns(2)

df = None
template_text = ""

with col1:
    up_ex = st.file_uploader("Upload Excel", type=['xlsx'])
with col2:
    up_wd = st.file_uploader("Upload Word Template", type=['docx'])

if up_ex:
    try:
        excel_data = up_ex.read()
        df = pd.read_excel(io.BytesIO(excel_data), engine='openpyxl')
        df.columns = [str(col).strip().upper() for col in df.columns]
        c_col = next((c for c in df.columns if c in ['COMPANY', 'חברה', 'NAME']), None)
        e_col = next((c for c in df.columns if c in ['EMAIL', 'מייל', 'MAIL']), None)
        if c_col and e_col:
            st.success("Excel Loaded")
            st.session_state['cols'] = (c_col, e_col)
        else:
            st.error("Column mapping failed")
    except Exception as e:
        st.error(f"Excel Error: {e}")

if up_wd:
    try:
        word_data = up_wd.read()
        doc = Document(io.BytesIO(word_data))
        template_text = "\n".join([p.text for p in doc.paragraphs])
        if template_text:
            st.success("Template Loaded")
    except Exception as e:
        st.error(f"Word Error: {e}")

st.write("---")
st.header("2. Sender Details")

user_mail = st.text_input("Your Gmail Address:")
user_pass = st.text_input("App Password:", type="password")
user_subj = st.text_input("Email Subject:")

st.write("---")
if st.button("Start Sending"):
    if df is not None and template_text and user_mail and user_pass and user_subj:
        prog = st.progress(0)
        status = st.empty()
        
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            c_col, e_col = st.session_state['cols']
            sent_count = 0
            
            for i, row in df.iterrows():
                if pd.isna(row[c_col]) or pd.isna(row[e_col]):
                    continue
                
                msg = MIMEMultipart()
                msg['From'] = user_mail.strip()
                msg['To'] = str(row[e_col]).strip()
                msg['Subject'] = user_subj.strip()
                
                body = template_text.replace("{COMPANY}", str(row[c_col]))
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                server.send_message(msg)
                sent_count += 1
                prog.progress((i + 1) / len(df))
                status.text(f"Sending to: {row[c_col]}")
                time.sleep(0.4)
                
            server.quit()
            st.success(f"Finished! Sent {sent_count} emails.")
            st.balloons()
        except Exception as e:
            st.error(f"Process Error: {e}")
    else:
        st.warning("Missing data")
