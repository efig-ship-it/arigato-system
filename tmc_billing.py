import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- מערכת סאונד דרמטית ---
def play_audio(url):
    st.components.v1.html(f"""
        <script>
            var audio = new Audio("{url}");
            audio.play();
        </script>
    """, height=0)

def sound_success(): play_audio("https://github.com/robiningelbrecht/strava-activities/raw/master/files/applause.mp3")
def sound_detective(): play_audio("https://www.soundjay.com/buttons/sounds/button-4.mp3")
def sound_dramatic(): play_audio("https://www.myinstants.com/media/sounds/dun_dun_dun.mp3") # טא טא טאאאא

# --- ניהול בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# תפריט ניווט
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

# --- עמוד 1: Email Sender ---
if page == "Email Sender":
    st.markdown("""<style>
    .stMetric { background-color: #f8f9fb; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .due-date-container { display: flex; justify-content: center; width: 100%; margin-bottom: 2px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; }
    .big-detective { font-size: 80px; text-align: center; margin-bottom: 0px; }
    .detective-header { font-size: 40px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-top: 0px; }
    .reverse-detective-header { font-size: 40px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-top: 0px; }
    </style>""", unsafe_allow_html=True)

    st.title("TMC Billing System")

    # 1. Setup & Files
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", [str(y) for y in range(2025, 2030)], index=1, label_visibility="collapsed")
        current_month_year = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload all Invoices & Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

    # --- מנגנון הבלשים המשופר ---
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name.lower() for f in uploaded_files]
            
            # בלש 1: קבצים ללא חברה
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            
            # בלש 2 (הפוך): חברות ללא קבצים
            missing_files = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]

            if orphans:
                st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                st.error(f"Files with no matching company in Excel: {', '.join(orphans)}")
                sound_detective()

            if missing_files:
                st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                for comp in missing_files:
                    st.warning(f"⚠️ {comp} appears in the mailing list, but no file was found for it!")
                sound_dramatic() # טא טא טאאאא

            if orphans or missing_files:
                with st.info("🚨 **Safety Verification Required**"):
                    allow_sending = st.toggle("I confirm that data is correct and I want to proceed with sending", value=False)
        except Exception:
            sound_dramatic(); st.error("Critical error in file validation!")

    # 2. Sender Details (נשמר במלואו)
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("""
            1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
            2. Make sure **2-Step Verification** is turned **ON**.
            3. Search for **'App passwords'**.
            4. Create a name and copy the **16-character code**.
            """)

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

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
                        msg['Subject'] = f"{user_subj} - {company}"
                        msg.attach(MIMEText(f"Files for {company}.\nDue: {current_month_year}", 'plain'))
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
                server.quit(); st.balloons(); sound_success()
                st.success(f"Done! {sent_count} emails sent."); time.sleep(2); st.rerun()
            except Exception as e: sound_dramatic(); st.error(f"Error: {e}")

# --- עמוד 2: Analytics Dashboard ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    df_raw = get_history_df()
    if not df_raw.empty:
        # תיקון ValueError - המרה בטוחה
        df_raw['Date'] = pd.to_datetime(df_raw['Date'], errors='coerce')
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Companies", len(df_raw['Company'].unique()))
        m2.metric("Total Emails Sent", int(df_raw['Recipients'].sum()))
        m3.metric("Last Activity", df_raw['Date'].max().strftime("%Y-%m-%d") if pd.notnull(df_raw['Date'].max()) else "N/A")

        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({'Recipients': 'sum', 'Files': 'sum', 'Date': 'max'}).reset_index()
        st.dataframe(pivot, use_container_width=True, hide_index=True)

        with st.expander("📂 Detailed Activity Log & Filters", expanded=True):
            st.dataframe(df_raw, use_container_width=True, hide_index=True)
    else: st.info("No data yet.")
