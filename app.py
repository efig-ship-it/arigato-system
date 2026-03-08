import streamlit as st
import pandas as pd
from docx import Document
import io, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# הגדרות דף
st.set_page_config(page_title="Arigato Billing", layout="centered")

# כותרת ראשית
st.title("Arigato Billing System")
st.write("---")

# חלק 1: העלאת קבצים
st.header("1. Upload Files")
col1, col2 = st.columns(2)

df = None
template_text = ""

with col1:
    st.markdown("**Upload Excel**")
    # שימוש ב-label_visibility="collapsed" כדי להצמד לעיצוב הנקי שלך
    up_ex = st.file_uploader("Upload Excel", type=['xlsx'], label_visibility="collapsed")
    
with col2:
    st.markdown("**Upload Word Template**")
    up_wd = st.file_uploader("Upload Word Template", type=['docx'], label_visibility="collapsed")

# עיבוד קובץ אקסל
if up_ex:
    try:
        excel_data = up_ex.read()
        df = pd.read_excel(io.BytesIO(excel_data), engine='openpyxl')
        df.columns = [str(col).strip().upper() for col in df.columns]
        c_col = next((c for c in df.columns if c in ['COMPANY', 'חברה', 'NAME']), None)
        e_col = next((c for c in df.columns if c in ['EMAIL', 'מייל', 'MAIL']), None)
        if c_col and e_col:
            st.success(f"✅ Excel Loaded: Found columns '{c_col}' and '{e_col}'")
            st.session_state['cols'] = (c_col, e_col)
        else:
            st.error("❌ Column mapping failed. Please ensure 'Company' and 'Email' columns exist.")
    except Exception as e:
        st.error(f"Excel Error: {e}")

# עיבוד קובץ וורד
if up_wd:
    try:
        word_data = up_wd.read()
        doc = Document(io.BytesIO(word_data))
        template_text = "\n".join([p.text for p in doc.paragraphs])
        if template_text:
            st.success("✅ Word Template Loaded")
    except Exception as e:
        st.error(f"Word Error: {e}")

st.write("---")

# חלק 2: פרטי שולח
st.header("2. Sender Details")

user_mail = st.text_input("Your Gmail Address:", placeholder="example@gmail.com")
user_pass = st.text_input("App Password:", type="password", help="The 16-character code from Google")

# רכיב מתקפל עם הסבר על App Password
with st.expander("🔑 How to create an App Password? (Click here)"):
    st.markdown("""
    To send emails via Gmail, you need a unique **App Password**. 
    *Standard login passwords will not work.*
    
    1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
    2. Make sure **2-Step Verification** is turned **ON**.
    3. Scroll down or search for **'App passwords'**.
    4. Select an app name (e.g., "Arigato System") and click **Create**.
    5. Copy the **16-character code** generated and paste it in the field above.
    
    *Note: Do not include spaces when pasting the password.*
    """)

user_subj = st.text_input("Email Subject:", placeholder="Enter email subject here...")

st.write("---")

# כפתור שליחה
if st.button("Start Sending", use_container_width=True):
    if df is not None and template_text and user_mail and user_pass and user_subj:
        prog = st.progress(0)
        status = st.empty()
        
        try:
            # התחברות לשרת
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            # ניקוי רווחים מהסיסמה למקרה שהמשתמש העתיק עם רווחים
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            c_col, e_col = st.session_state['cols']
            sent_count = 0
            total_rows = len(df)
            
            for i, row in df.iterrows():
                if pd.isna(row[c_col]) or pd.isna(row[e_col]):
                    continue
                
                msg = MIMEMultipart()
                msg['From'] = user_mail.strip()
                msg['To'] = str(row[e_col]).strip()
                msg['Subject'] = user_subj.strip()
                
                # החלפת תגיות בטקסט (תומך ב-{COMPANY})
                body = template_text.replace("{COMPANY}", str(row[c_col]))
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                server.send_message(msg)
                sent_count += 1
                
                # עדכון התקדמות
                prog.progress((i + 1) / total_rows)
                status.text(f"Sending to: {row[c_col]} ({sent_count}/{total_rows})")
                time.sleep(0.4) # השהייה קלה למניעת חסימת ספאם
                
            server.quit()
            st.success(f"Done! {sent_count} emails were sent successfully.")
            st.balloons()
            
        except smtplib.SMTPAuthenticationError:
            st.error("Authentication Failed: Please check your Gmail address or App Password.")
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please fill in all details and upload files before starting.")
