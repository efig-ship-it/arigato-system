import streamlit as st
import pandas as pd
from docx import Document
import io, smtplib, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- הגדרות דף ---
st.set_page_config(page_title="מערכת גבייה - אריגאטו", layout="centered")

# --- עיצוב CSS מותאם אישית (RTL וצבעים) ---
st.markdown("""
    <style>
    /* הגדרת כיוון כתיבה מימין לשמאל לכל האתר */
    .main { direction: rtl; text-align: right; }
    div.stButton > button {
        width: 100%;
        background-color: #d4af37;
        color: white;
        font-weight: bold;
        height: 3.5em;
        border-radius: 12px;
        border: none;
        font-size: 18px;
    }
    div.stButton > button:hover { background-color: #b8962d; color: white; }
    
    .app-header {
        background-color: #003366;
        color: #ffffff;
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        border-bottom: 5px solid #d4af37;
        margin-bottom: 30px;
    }
    
    /* עיצוב תוויות הטקסט והעלאת הקבצים */
    label { font-weight: bold !important; color: #003366 !important; font-size: 18px !important; }
    
    .info-box {
        background-color: #f0f4f8;
        padding: 15px;
        border-radius: 8px;
        border-right: 5px solid #003366;
        margin: 10px 0;
        text-align: right;
    }
    
    /* תיקון ליישור טקסט בעברית בתוך תיבות הקלט */
    input { text-align: right; direction: rtl; }
    </style>
    
    <div class="app-header">
        <h1 style='margin:0; color: white;'>מערכת גבייה - מחלקת כספים אריגאטו</h1>
    </div>
""", unsafe_allow_all_with_html=True)

# --- הגדרות קבועות ---
MY_APP_PASSWORD = "nwfk odkt qzzc whhv"

# --- שלב 1: העלאת קבצים ---
st.subheader("?? שלב 1: העלאת קבצים")
col1, col2 = st.columns(2)

with col1:
    up_ex = st.file_uploader("טען אקסל גבייה", type=['xlsx'])
with col2:
    up_wd = st.file_uploader("טען טמפלט וורד", type=['docx'])

# משתני עזר לנתונים
df = None
template_text = ""

if up_ex:
    try:
        df = pd.read_excel(up_ex)
        df.columns = [str(col).strip().upper() for col in df.columns]
        c_col = next((c for c in df.columns if c in ['COMPANY', 'חברה', 'שם חברה']), None)
        e_col = next((c for c in df.columns if c in ['EMAIL', 'מייל', 'אימייל']), None)
        
        if c_col and e_col:
            st.markdown(f"<div class='info-box'>? האקסל נקלט! נמצאו <b>{len(df)}</b> חברות לשליחה.</div>", unsafe_allow_all_with_html=True)
            # שמירת שמות העמודות שמצאנו
            st.session_state['c_col'] = c_col
            st.session_state['e_col'] = e_col
        else:
            st.error("? שגיאה: לא נמצאו עמודות 'חברה' ו'מייל' באקסל! וודא שהכותרות תקינות.")
    except Exception as e:
        st.error(f"שגיאה בקריאת האקסל: {e}")

if up_wd:
    try:
        doc = Document(up_wd)
        template_text = '\n'.join([para.text for para in doc.paragraphs])
        st.markdown("<div class='info-box' style='border-right-color: #d4af37;'>? טמפלט הוורד נטען בהצלחה.</div>", unsafe_allow_all_with_html=True)
    except Exception as e:
        st.error(f"שגיאה בקריאת קובץ הוורד: {e}")

# --- שלב 2: פרטי שליחה ---
st.markdown("---")
st.subheader("?? שלב 2: פרטי שליחה")
mail_in = st.text_input("כתובת המייל שלך (Gmail):", placeholder="example@gmail.com")
subj_in = st.text_input("נושא המייל ללקוח:", placeholder="הכנס נושא כאן...")

# --- שלב 3: ביצוע ---
st.markdown("<br>", unsafe_allow_all_with_html=True)
if st.button("?? התחל שליחת מיילים"):
    if df is not None and template_text and mail_in and subj_in:
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()
        logs = []
        
        c_col = st.session_state.get('c_col')
        e_col = st.session_state.get('e_col')

        try:
            # התחברות לשרת המייל
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(mail_in.strip(), MY_APP_PASSWORD.replace(" ", ""))

            sent_count = 0
            for i, row in df.iterrows():
                # דילוג על שורות ריקות
                if pd.isna(row[c_col]) or pd.isna(row[e_col]):
                    continue

                company_name = str(row[c_col]).strip()
                target_email = str(row[e_col]).strip()

                msg = MIMEMultipart()
                msg['From'] = mail_in.strip()
                msg['To'] = target_email
                msg['Subject'] = subj_in.strip()
                
                # החלפת תגית החברה בטקסט
                body = template_text.replace("{COMPANY}", company_name)
                msg.attach(MIMEText(body, 'plain', 'utf-8'))

                server.send_message(msg)
                sent_count += 1
                
                # עדכון ממשק התקדמות
                percent = (i + 1) / len(df)
                progress_bar.progress(percent)
                status_text.text(f"שולח אל: {company_name} ({target_email})")
                
                logs.append(f"? נשלח בהצלחה אל: {company_name}")
                log_area.code("\n".join(logs[-10:])) # מציג את 10 האחרונים בלוג
                
                time.sleep(0.5) # השהייה קלה למניעת חסימת ספאם

            server.quit()
            st.success(f"? הסתיים בהצלחה! נשלחו {sent_count} מיילים.")
            st.balloons() # חגיגה קטנה בסיום
        except Exception as e:
            st.error(f"? שגיאה בתהליך השליחה: {e}")
    else:
        st.warning("?? חסרים נתונים: וודא שהעלית קבצים ומילאת את כל השדות.")