import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף - TMC Billing & Analytics
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- ניהול בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# תפריט ניווט בצד (Sidebar)
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

    # חלק 2: פרטי שולח
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("""
            1. Go to [**Google Security**](https://myaccount.google.com/security).
            2. 2-Step Verification: **ON**.
            3. Search for **'App passwords'**.
            4. Copy the **16-char code**.
            """)

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

    # בדיקת כפילויות (Duplicate Warning)
    if up_ex:
        conn = sqlite3.connect('billing_history.db')
        today_str = datetime.now().strftime("%Y-%m-%d")
        already_sent = pd.read_sql_query(f"SELECT Company FROM history WHERE Date='{today_str}'", conn)['Company'].tolist()
        conn.close()
        
        if already_sent:
            st.warning(f"⚠️ Note: You already sent emails today to: {', '.join(already_sent)}")

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
                        msg.attach(MIMEText(f"Attached are files for {company}.\nDue: {current_month_year}", 'plain'))
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        
                        conn = sqlite3.connect('billing_history.db')
                        conn.cursor().execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
                                           (datetime.now().strftime("%Y-%m-%d"), company, len(emails), len(files)))
                        conn.commit()
                        conn.close()
                        sent_count += 1
                    prog.progress((i + 1) / len(df))
                server.quit()
                st.success(f"Sent {sent_count} emails!")
                time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.error("Missing fields or files!")

    # חלק 3: היסטוריה מהירה
    st.write("---")
    conn = sqlite3.connect('billing_history.db')
    history_df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()

    if not history_df.empty:
        history_df['Date'] = pd.to_datetime(history_df['Date']).dt.date
        m1, m2, m3 = st.columns(3)
        m1.metric("Companies", len(history_df['Company'].unique()))
        m2.metric("Total Emails", int(history_df['Recipients'].sum()))
        m3.metric("Last Sent", history_df['Date'].iloc[0].strftime("%d-%m-%Y"))

# --- עמוד 2: Analytics Dashboard (הכלים החדשים כאן) ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    
    conn = sqlite3.connect('billing_history.db')
    df_raw = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()

    if not df_raw.empty:
        df_raw['Date'] = pd.to_datetime(df_raw['Date'])
        
        # 1. התראת "שכחנו מישהו" (Missing Companies)
        st.subheader("🚨 Missing This Month")
        # בדיקה מול האקסל האחרון שהועלה (אם קיים בסשן)
        if 'last_excel_list' in st.session_state:
            current_month = datetime.now().month
            sent_this_month = df_raw[df_raw['Date'].dt.month == current_month]['Company'].unique()
            missing = [c for c in st.session_state.last_excel_list if c not in sent_this_month]
            if missing:
                st.error(f"The following companies haven't received an email this month: {', '.join(missing)}")
            else:
                st.success("Great! Everyone in your list received their emails this month.")
        else:
            st.info("Upload a Mailing List in the Sender page to track missing companies.")

        # 2. חיפוש חופשי וציר זמן (Timeline Search)
        st.write("---")
        st.subheader("🔍 Free Search & Timeline")
        search_term = st.text_input("Search by Company Name", placeholder="Type company name...")
        
        if search_term:
            search_results = df_raw[df_raw['Company'].str.contains(search_term, case=False)]
            if not search_results.empty:
                st.write(f"Found {len(search_results)} records for '{search_term}':")
                # הצגת ציר זמן פשוט
                display_search = search_results.copy()
                display_search['Date'] = display_search['Date'].dt.strftime("%d-%m-%Y")
                st.table(display_search[['Date', 'Recipients', 'Files']])
            else:
                st.warning("No records found for this company.")

        # 3. ניתוח פיבוט (Pivot Table)
        st.write("---")
        st.subheader("🏢 Company Pivot Analysis")
        pivot = df_raw.groupby('Company').agg({
            'Recipients': 'sum',
            'Files': 'sum',
            'Date': 'max'
        }).rename(columns={'Recipients': 'Total Emails', 'Files': 'Total Files', 'Date': 'Last Activity'}).reset_index()
        pivot['Last Activity'] = pivot['Last Activity'].dt.strftime("%d-%m-%Y")
        st.dataframe(pivot, use_container_width=True, hide_index=True)

    else:
        st.info("No data recorded yet.")
