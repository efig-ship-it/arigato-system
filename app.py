import streamlit as st
import pandas as pd
from docx import Document
import io, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- הגדרות דף ---
st.set_page_config(page_title="מערכת גבייה - אריגאטו", layout="centered")

# --- עיצוב CSS (שימוש ב-Raw String למניעת שגיאות Type) ---
style_css = r"""
<style>
    .main { direction: rtl !important; text-align: right !important; }
    div.stButton > button { width: 100%; background-color: #d4af37; color: white; font-weight: bold; height: 3.5em; border-radius: 12px; }
    .header-box { background-color: #003366; color: white; padding: 20px; border-radius: 15px; text-align: center; border-bottom: 5px solid #d4af37; margin-bottom: 25px; }
    label { font-weight: bold !important; color: #003366 !important; }
    input { text-align: right !important; direction: rtl !important; }
</style>
"""
st.markdown(style_css, unsafe_allow_all_with_html=True)
st.markdown('<div class="header-box"><h1>מערכת גבייה - אריגאטו</h1></div>', unsafe_allow_all_with_html=True)

# --- שלב 1: העלאת קבצים ---
st.subheader("📁 שלב 1: העלאת קבצים")
col1, col2 = st.columns(2)

df = None
template_text = ""

with col1:
    up_ex = st.file_uploader("טען אקסל גבייה", type=['xlsx'])
with col2:
    up_wd = st.file_uploader("טען טמפלט וורד", type=['docx'])

if up_ex:
    try:
        excel_data = up_ex.read()
        df = pd.read_excel(io.BytesIO(excel_data), engine='openpyxl')
        df.columns = [str(col).strip().upper() for col in df.columns]
        c_col = next((c for c in df.columns if c in ['COMPANY', 'חברה', 'שם חברה', 'NAME']), None)
        e_col = next((c for c in df.columns if c in ['EMAIL', 'מייל', 'אימייל', 'MAIL']), None)
        if c_col and e_col:
            st.success("✅ האקסל נטען בהצלחה")
            st.session_state['cols'] = (c_col, e_col)
    except Exception as e:
        st.error(f"Error: {e}")

if up_wd:
    try:
        word_data = up_wd.read()
        doc = Document(io.BytesIO(word_data))
        template_text = "\n".join([p.text for p in doc.paragraphs])
        if template_text: st.success("✅ טמפלט הוורד נטען")
    except Exception as e:
        st.error(f"Error: {e}")

# --- שלב 2: פרטי אימות ושליחה ---
st.markdown("---")
st.subheader("🔐 שלב 2: פרטי חשבון ושליחה")
col_m, col_p = st.columns(2)

with col_m:
    user_mail = st.text_input("כתובת ה-Gmail שלך:")
with col_p:
    user_pass = st.text_input("סיסמת אפליקציה (App Password):", type="password")

user_subj = st.text_input("נושא המייל ללקוח:")

# --- שלב 3: ביצוע ---
if st.button("🚀 התחל שליחת מיילים"):
    if df is not None and template_text and user_mail and user_pass and user_subj:
        prog = st.progress(0)
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            c_col, e_col = st.session_state['cols']
            sent_count = 0
            
            for i, row in df.iterrows():
                if pd.isna(row[c_col]) or pd.isna(row[e_col]): continue
                
                msg = MIMEMultipart()
                msg['From'] = user_mail.strip()
                msg['To'] = str(row[e_col]).strip()
                msg['Subject'] = user_subj.strip()
                
                body = template_text.replace("{COMPANY}", str(row[c_col]))
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                server.send_message(msg)
                sent_count += 1
                prog.progress((i + 1) / len(df))
                time.sleep(0.4)
                
            server.quit()
            st.success(f"✨ הסתיים! נשלחו {sent_count} מיילים.")
            st.balloons()
        except Exception as e:
            st.error(f"❌ שגיאה: {e}")
    else:
        st.warning("⚠️ נא למלא את כל השדות.")
