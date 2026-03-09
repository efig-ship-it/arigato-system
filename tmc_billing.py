import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- פונקציות עזר (צליל) ---
def play_success_sound():
    # הקוד המובנה שכבר היה לנו
    sound_html = """
    <audio autoplay>
    <source src="https://www.soundjay.com/misc/sounds/bell-ringing-05.mp3" type="audio/mpeg">
    </audio>
    """
    st.markdown(sound_html, unsafe_allow_html=True)

# --- ניהול בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- תפריט ניווט בצד ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

# --- עמוד 1: Email Sender ---
if page == "Email Sender":
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 0rem; }
        h1 { margin-top: 0rem !important; margin-bottom: 1rem !important; font-size: 2rem; }
        .stVerticalBlock { gap: 0.4rem; }
        hr { margin: 0.5em 0px; }
        .stMetric { background-color: #f8f9fb; padding: 5px; border-radius: 8px; border: 1px solid #eee; }
        </style>
        """, unsafe_allow_html=True)

    st.title("TMC Billing System")

    # חלק 1: הגדרות וקבצים
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = st.selectbox("Mo", months, index=datetime.now().month - 1)
        years = [str(y) for y in range(datetime.now().year - 1, datetime.now().year + 3)]
        sel_y = st.selectbox("Yr", years, index=1)
        current_month_year = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload all Invoices & Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

    # חלק 2: פרטי שולח
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2 = st.columns(2)
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

    # בדיקת כפילויות לזיהוי מהיר
    if up_ex:
        conn = sqlite3.connect('billing_history.db')
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            already_sent_today = pd.read_sql_query(f"SELECT Company FROM history WHERE Date='{today_str}'", conn)['Company'].tolist()
            excel_companies = pd.read_excel(up_ex).iloc[:, 0].dropna().unique().tolist()
            duplicates = [c for c in excel_companies if str(c).strip() in already_sent_today]
            if duplicates:
                st.warning(f"⚠️ שים לב: כבר שלחת היום מיילים ל: {', '.join(duplicates)}")
        except: pass
        finally: conn.close()

    # לוגיקה לשליחה
    if st.button("🚀 Start Bulk Sending", use_container_width=True):
        if up_ex and uploaded_files and user_mail:
            try:
                df = pd.read_excel(up_ex)
                prog = st.progress(0)
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(user_mail.strip(), user_pass.replace(" ", ""))
                
                sent_count = 0
                for i, row in df.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    
                    if files and emails:
                        msg = MIMEMultipart()
                        msg['From'], msg['To'], msg['Subject'] = user_mail, ", ".join(emails), f"{user_subj} - {company}"
                        msg.attach(MIMEText(f"Hi,\n\nAttached are files for {company}.\nDue: {current_month_year}", 'plain'))
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        
                        # רישום בהיסטוריה
                        conn = sqlite3.connect('billing_history.db')
                        conn.cursor().execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
                                           (datetime.now().strftime("%Y-%m-%d"), company, len(emails), len(files)))
                        conn.commit()
                        conn.close()
                        sent_count += 1
                    prog.progress((i + 1) / len(df))
                
                server.quit()
                
                # הפעלת אפקטים (בלונים + סאונד מובנה)
                st.balloons()
                play_success_sound()
                st.success(f"השליחה הסתיימה! {sent_count} מיילים נשלחו.")
                time.sleep(2)
                st.rerun() # מרענן את הדף כדי לעדכן טבלאות ודשבורד
                
            except Exception as e:
                st.error(f"שגיאה בשליחה: {e}")
        else:
            st.error("חסרים פרטים, קבצים או רשימת תפוצה!")

    # חלק 3: טבלת היסטוריה מתוקנת
    st.write("---")
    conn = sqlite3.connect('billing_history.db')
    history_df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()

    if not history_df.empty:
        # תיקון התאריך למניעת קריסה (כאן הייתה השגיאה שלך)
        history_df['Date'] = pd.to_datetime(history_df['Date'], errors='coerce')
        history_df = history_df.dropna(subset=['Date'])
        history_df['Date'] = history_df['Date'].dt.date

        st.subheader("Recent History")
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        
        # כפתור גיבוי ידני
        csv = history_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 הורד גיבוי היסטוריה (CSV)", data=csv, file_name=f"billing_backup_{date.today()}.csv", mime="text/csv")

# --- עמוד 2: Analytics Dashboard ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics & Reports")
    
    conn = sqlite3.connect('billing_history.db')
    df_raw = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()

    if not df_raw.empty:
        df_raw['Date'] = pd.to_datetime(df_raw['Date'], errors='coerce')
        df_raw = df_raw.dropna(subset=['Date'])
        
        # סיכום לפי חברה (פיבוט)
        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({
            'Recipients': 'sum',
            'Files': 'sum',
            'Date': 'max'
        }).rename(columns={'Recipients': 'Total Emails', 'Files': 'Total Files', 'Date': 'Last Sent'}).reset_index()
        pivot['Last Sent'] = pivot['Last Sent'].dt.strftime("%d-%m-%Y")
        st.dataframe(pivot, use_container_width=True, hide_index=True)
        
        # תרשים פעילות
        st.subheader("📈 Monthly Activity")
        df_raw['Month'] = df_raw['Date'].dt.strftime('%Y-%m')
        monthly_counts = df_raw.groupby('Month').size()
        st.bar_chart(monthly_counts)
    else:
        st.info("אין נתונים היסטוריים להצגה בדשבורד.")
