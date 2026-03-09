import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- מערכת סאונד ---
def play_audio(url):
    st.components.v1.html(f"""
        <script>
            var audio = new Audio("{url}");
            audio.play();
        </script>
    """, height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

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

if page == "Email Sender":
    st.markdown("""<style>
    .stMetric { background-color: #f8f9fb; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .due-date-container { display: flex; justify-content: center; width: 100%; margin-bottom: 2px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; }
    .big-detective { font-size: 90px; text-align: center; margin-bottom: 0px; }
    .detective-header { font-size: 45px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; }
    .reverse-detective-header { font-size: 45px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; }
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

    uploaded_files = st.file_uploader("Upload Invoices & Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

    # --- מנגנון הבלשים עם העלמת הודעה לאחר אישור ---
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name.lower() for f in uploaded_files]
            
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing_files = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]

            if orphans or missing_files:
                # יצירת מפתח ב-Session State כדי לעקוב אם השמענו כבר את הצליל
                if 'sound_played' not in st.session_state:
                    sound_detective()
                    st.session_state.sound_played = True
                
                # תיבת האישור מופיעה תמיד כשיש תקלה
                with st.info("🚨 **Data Validation Required**"):
                    confirm_toggle = st.toggle("I confirm that data is correct and I want to proceed", value=False)
                    allow_sending = confirm_toggle

                # ההודעות מוצגות רק אם המשתמש *לא* אישר עדיין
                if not confirm_toggle:
                    if orphans:
                        st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.error(f"Unrecognized files: {', '.join(orphans)}")
                    if missing_files:
                        if not orphans: st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                        st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        for comp in missing_files:
                            st.warning(f"⚠️ {comp} appears in the mailing list, but no file was found for it!")
            else:
                st.session_state.sound_played = False # איפוס למקרה שהכל תקין
        except: pass

    # 2. Sender Details (החזרתי את הפירוט המלא)
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
            except Exception as e: st.error(f"Error: {e}")

# --- עמוד 2: Analytics Dashboard (החזרתי פיבוטים ופילטרים) ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    df_raw = get_history_df()
    if not df_raw.empty:
        df_raw['Date_obj'] = pd.to_datetime(df_raw['Date'], errors='coerce')
        m1, m2, m3 = st.columns(3)
        m1.metric("Companies", len(df_raw['Company'].unique()))
        m2.metric("Total Emails", int(df_raw['Recipients'].sum()))
        m3.metric("Last Activity", df_raw['Date_obj'].max().strftime("%Y-%m-%d") if pd.notnull(df_raw['Date_obj'].max()) else "N/A")

        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({'Recipients': 'sum', 'Files': 'sum', 'Date_obj': 'max'}).reset_index()
        pivot['Last Activity'] = pivot['Last Activity'].dt.strftime("%Y-%m-%d")
        st.dataframe(pivot[['Company', 'Recipients', 'Files', 'Last Activity']], use_container_width=True, hide_index=True)

        with st.expander("📂 Detailed Activity Log & Filters", expanded=True):
            f1, f2 = st.columns([1.5, 1])
            sel_comp = f1.multiselect("Filter by Company", options=sorted(df_raw['Company'].unique().tolist()))
            sel_date_range = f2.date_input("Filter by Date Range", value=[])
            filtered_df = df_raw.copy()
            if sel_comp: filtered_df = filtered_df[filtered_df['Company'].isin(sel_comp)]
            if len(sel_date_range) == 2:
                filtered_df = filtered_df[(filtered_df['Date_obj'].dt.date >= sel_date_range[0]) & (filtered_df['Date_obj'].dt.date <= sel_date_range[1])]
            st.dataframe(filtered_df.drop(columns=['Date_obj']), use_container_width=True, hide_index=True)
