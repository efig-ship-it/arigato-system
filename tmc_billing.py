import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- פונקציית סאונד להתראות בלש ---
def play_detective_alert():
    # צליל התראה קצר כדי למשוך את תשומת הלב לבלש
    audio_url = "https://www.soundjay.com/buttons/sounds/button-4.mp3"
    st.components.v1.html(f"""<audio autoplay><source src="{audio_url}" type="audio/mpeg"></audio>""", height=0)

def play_applause_sound():
    audio_url = "https://github.com/robiningelbrecht/strava-activities/raw/master/files/applause.mp3"
    st.components.v1.html(f"""<audio autoplay><source src="{audio_url}" type="audio/mpeg"></audio>""", height=0)

# --- ניהול בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# תפריט ניווט בצד
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
        .due-date-container { display: flex; justify-content: center; width: 100%; margin-bottom: 2px; }
        .due-date-label { font-size: 14px; font-weight: 500; color: #31333F; }
        </style>
        """, unsafe_allow_html=True)

    st.title("TMC Billing System")

    # חלק 1: הגדרות וקבצים
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        years = [str(y) for y in range(datetime.now().year - 1, datetime.now().year + 3)]
        sel_y = yc.selectbox("Yr", years, index=1, label_visibility="collapsed")
        current_month_year = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload all Invoices & Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

    # --- מנגנון התראות ואישור משתמש ---
    allow_sending = True
    
    if up_ex and uploaded_files:
        try:
            df_excel = pd.read_excel(up_ex)
            excel_companies = [str(c).strip().lower() for c in df_excel.iloc[:, 0].dropna().unique()]
            orphaned = [f.name for f in uploaded_files if not any(comp in f.name.lower() for comp in excel_companies)]
            
            # בדיקת כפילויות
            conn = sqlite3.connect('billing_history.db')
            today_str = datetime.now().strftime("%Y-%m-%d")
            already_sent_today = pd.read_sql_query(f"SELECT Company FROM history WHERE Date='{today_str}'", conn)['Company'].str.lower().tolist()
            conn.close()
            duplicates = [c for c in excel_companies if c in already_sent_today]

            # אם נמצאה בעיה
            if orphaned or duplicates:
                play_detective_alert()
                if orphaned:
                    st.error(f"🕵️‍♂️ **הבלש מצא בעיה:** הקבצים הבאים לא משויכים לאף חברה באקסל: `{', '.join(orphaned)}`")
                if duplicates:
                    st.warning(f"⚠️ **כפילות נמצאה:** כבר שלחת היום ל: `{', '.join(duplicates)}`")
                
                # מחסום האישור
                st.write("---")
                user_confirmation = st.checkbox("סקרתי את ההתראות ואני מאשר שהנתונים תקינים לשליחה ✅")
                allow_sending = user_confirmation
        except: pass

    # חלק 2: פרטי שולח
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("""
            To send emails via Gmail, you need a unique **App Password**.
            *Standard login passwords will not work.*

            1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
            2. Make sure **2-Step Verification** is turned **ON**.
            3. Search for **'App passwords'** in the top search bar.
            4. Select a name (e.g., "TMC Billing") and click **Create**.
            5. Copy the **16-character code** and paste it here.
            """)

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

    # כפתור השליחה - מושבת אם לא אושר
    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df = pd.read_excel(up_ex)
                prog = st.progress(0)
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
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
                        
                        conn = sqlite3.connect('billing_history.db')
                        conn.cursor().execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
                                           (datetime.now().strftime("%Y-%m-%d"), company, len(emails), len(files)))
                        conn.commit(); conn.close()
                        sent_count += 1
                    prog.progress((i + 1) / len(df))
                
                server.quit()
                st.balloons(); play_applause_sound()
                st.success(f"Success! {sent_count} emails sent.")
                time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")
        else:
            st.error("Missing fields or files!")

    # חלק 3: היסטוריה
    st.write("---")
    conn = sqlite3.connect('billing_history.db')
    history_df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()

    if not history_df.empty:
        history_df['Date_obj'] = pd.to_datetime(history_df['Date'], errors='coerce')
        display_df = history_df.drop(columns=['Date_obj']).copy()
        display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime("%d-%m-%Y")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# --- עמוד 2: Analytics Dashboard ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    conn = sqlite3.connect('billing_history.db'); df_raw = pd.read_sql_query("SELECT * FROM history", conn); conn.close()
    if not df_raw.empty:
        df_raw['Date_obj'] = pd.to_datetime(df_raw['Date'], errors='coerce')
        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({'Recipients': 'sum', 'Files': 'sum', 'Date_obj': 'max'}).reset_index()
        pivot['Last Activity'] = pivot['Date_obj'].dt.strftime("%d-%m-%Y")
        st.dataframe(pivot[['Company', 'Recipients', 'Files', 'Last Activity']], use_container_width=True, hide_index=True)
