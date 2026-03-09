import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- פונקציית סאונד מחיאות כפיים ---
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

    # התראת בלש 🕵️‍♂️
    if up_ex and uploaded_files:
        try:
            df_excel = pd.read_excel(up_ex)
            excel_companies = [str(c).strip().lower() for c in df_excel.iloc[:, 0].dropna().unique()]
            orphaned = [f.name for f in uploaded_files if not any(comp in f.name.lower() for comp in excel_companies)]
            if orphaned:
                st.error(f"🕵️‍♂️ **עצור!** מצאתי קבצים שלא משויכים לאף חברה באקסל: `{', '.join(orphaned)}`")
        except: pass

    # חלק 2: פרטי שולח
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. Go to [Google Security](https://myaccount.google.com/security)\n2. 2-Step Auth: **ON**\n3. Search **'App passwords'**\n4. Copy the **16-char code**.")

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True):
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
                        msg.attach(MIMEText(f"Attached are files for {company}.\nDue: {current_month_year}", 'plain'))
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

    # חלק 3: היסטוריה - תצוגה מתוקנת למניעת שגיאה
    st.write("---")
    conn = sqlite3.connect('billing_history.db')
    history_df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()

    if not history_df.empty:
        # פתרון השגיאה: המרה בטוחה של תאריכים
        history_df['Date_obj'] = pd.to_datetime(history_df['Date'], errors='coerce')
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Companies", len(history_df['Company'].unique()))
        m2.metric("Total Emails", int(history_df['Recipients'].sum()))
        # הצגת תאריך אחרון בפורמט DD/MM/YYYY
        last_date = history_df['Date_obj'].max()
        m3.metric("Last Sent", last_date.strftime("%d/%m/%Y") if pd.notnull(last_date) else "N/A")

        with st.expander("📊 View History & Filters", expanded=True):
            f1, f2 = st.columns([1.5, 1])
            sel_comp = f1.multiselect("Filter Company", options=sorted(history_df['Company'].unique().tolist()))
            sel_date_range = f2.date_input("Date Range", value=[])

            filtered_df = history_df.copy()
            if sel_comp: filtered_df = filtered_df[filtered_df['Company'].isin(sel_comp)]
            if len(sel_date_range) == 2:
                filtered_df = filtered_df[(filtered_df['Date_obj'].dt.date >= sel_date_range[0]) & 
                                          (filtered_df['Date_obj'].dt.date <= sel_date_range[1])]
            
            # הצגת הטבלה בפורמט DD-MM-YYYY
            display_df = filtered_df.drop(columns=['Date_obj']).copy()
            display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime("%d-%m-%Y")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            if st.button("🗑️ Reset History"):
                conn = sqlite3.connect('billing_history.db'); conn.cursor().execute("DELETE FROM history"); conn.commit(); conn.close()
                st.rerun()

# --- עמוד 2: Analytics Dashboard ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    conn = sqlite3.connect('billing_history.db')
    df_raw = pd.read_sql_query("SELECT * FROM history", conn); conn.close()
    
    if not df_raw.empty:
        df_raw['Date_obj'] = pd.to_datetime(df_raw['Date'], errors='coerce')
        
        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({'Recipients': 'sum', 'Files': 'sum', 'Date_obj': 'max'}).reset_index()
        pivot['Last Activity'] = pivot['Date_obj'].dt.strftime("%d-%m-%Y")
        st.dataframe(pivot[['Company', 'Recipients', 'Files', 'Last Activity']], use_container_width=True, hide_index=True)
    else: st.info("No data yet.")
