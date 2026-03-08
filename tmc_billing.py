import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing System", layout="centered")

# --- ניהול בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

def add_to_history(company, recipients, files):
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    # שמירה בפורמט ISO (YYYY-MM-DD) כדי שהפילטור יהיה קל יותר
    c.execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d"), company, recipients, files))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect('billing_history.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date']).dt.date
    return df

init_db()

# עיצוב CSS
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

# --- חלק 1: הגדרות וקבצים ---
st.subheader("1. Setup & Files")
c1, c2 = st.columns([2, 1])
with c1:
    up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
with c2:
    mc, yc = st.columns(2)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
    years = [str(y) for y in range(datetime.now().year - 1, datetime.now().year + 3)]
    sel_y = yc.selectbox("Yr", years, index=1, label_visibility="collapsed")
    current_month_year = f"{sel_m} {sel_y}"

uploaded_files = st.file_uploader("Upload Invoices & Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

# --- חלק 2: פרטי שולח ---
st.write("---")
st.subheader("2. Sender Details")
sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
user_pass = sc2.text_input("App Password", type="password")
with sc3:
    with st.expander("🔑 App Password Help"):
        st.markdown("""
        1. [Google Security](https://myaccount.google.com/security)
        2. 2-Step Auth: **ON**
        3. Search **'App passwords'**
        4. Create & Copy the **16-char code**
        """)

user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

# --- לוגיקה לשליחה ---
if st.button("🚀 Start Bulk Sending", use_container_width=True):
    if not up_ex or not uploaded_files or not user_mail:
        st.error("Please fill all fields and upload files.")
    else:
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
                company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'], msg['To'], msg['Subject'] = user_mail, ", ".join(emails), f"{user_subj} - {company}"
                    body = f"Attached are files for {company}.\nDue: {current_month_year}"
                    msg.attach(MIMEText(body, 'plain'))
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    sent_count += 1
                    add_to_history(company, len(emails), len(company_files))
                prog.progress((i + 1) / len(df))
            server.quit()
            st.success(f"Sent {sent_count} emails!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# --- חלק 3: דשבורד והיסטוריה עם לוח שנה ---
st.write("---")
history_df = get_history()

if not history_df.empty:
    m1, m2, m3 = st.columns(3)
    m1.metric("Companies", len(history_df['Company'].unique()))
    m2.metric("Total Emails", int(history_df['Recipients'].sum()))
    m3.metric("Last Sent", history_df['Date'].iloc[0].strftime("%d/%m/%Y"))

    with st.expander("📊 View History & Filters", expanded=True):
        f1, f2 = st.columns([1, 1.2])
        
        # סנן חברה (Multiselect)
        sel_comp = f1.multiselect("Filter Company", options=sorted(history_df['Company'].unique()))
        
        # סנן תאריך (Calendar - Date Input)
        sel_date_range = f2.date_input("Filter by Date Range", value=[], help="Select start and end date")

        filtered_df = history_df.copy()
        
        # החלת פילטר חברה
        if sel_comp:
            filtered_df = filtered_df[filtered_df['Company'].isin(sel_comp)]
            
        # החלת פילטר תאריך (Calendar)
        if len(sel_date_range) == 2:
            start_date, end_date = sel_date_range
            filtered_df = filtered_df[(filtered_df['Date'] >= start_date) & (filtered_df['Date'] <= end_date)]
        elif len(sel_date_range) == 1:
            filtered_df = filtered_df[filtered_df['Date'] == sel_date_range[0]]

        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        if st.button("🗑️ Reset History"):
            conn = sqlite3.connect('billing_history.db'); conn.cursor().execute("DELETE FROM history"); conn.commit(); conn.close()
            st.rerun()
else:
    st.info("No activity recorded yet.")
