import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף
st.set_page_config(page_title="TMC Billing Dashboard", layout="centered")

# --- ניהול דשבורד (SQLite) ---
def init_db():
    conn = sqlite3.connect('billing_dashboard.db')
    c = conn.cursor()
    # הוספת עמודה לכמות קבצים
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, company TEXT, emails_sent INTEGER, files_count INTEGER)''')
    conn.commit()
    conn.close()

def add_to_dashboard(company, email_count, files_count):
    conn = sqlite3.connect('billing_dashboard.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d"), company, email_count, files_count))
    conn.commit()
    conn.close()

def get_dashboard_data():
    conn = sqlite3.connect('billing_dashboard.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()
    # המרה לפורמט תאריך של פנדס לצורך פילטור
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
    return df

init_db()

# עיצוב CSS
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .filter-box { background-color: #f9f9f9; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

st.title("TMC Billing System")

# --- חלק 1 + 2: תפעול ופרטי שולח (נשאר כפי שהיה) ---
st.subheader("1. Operation Center")
c1, c2 = st.columns([2, 1])
with c1:
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with c2:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    curr_y = datetime.now().year
    years = [str(y) for y in range(curr_y - 1, curr_y + 3)]
    mc, yc = st.columns(2)
    sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = yc.selectbox("Year", years, index=1)
    current_month_year = f"{sel_m} {sel_y}"

uploaded_files = st.file_uploader("Upload Invoices/Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

st.write("---")
st.subheader("2. Sender Details")
sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
user_mail = sc1.text_input("Gmail Address", placeholder="your-email@gmail.com")
user_pass = sc2.text_input("App Password", type="password")
with sc3:
    with st.expander("🔑 How to create an App Password?"):
        st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. 2-Step Auth ON\n3. Search 'App passwords'\n4. Create & Copy code.")

user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

# --- לוגיקה לשליחה ---
if st.button("🚀 Start Bulk Sending", use_container_width=True):
    if not up_ex or not uploaded_files or not user_mail:
        st.error("Missing information!")
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
                    msg.attach(MIMEText(f"Attached files for {company}.", 'plain'))
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    sent_count += 1
                    # שמירה לדשבורד כולל כמות קבצים
                    add_to_dashboard(company, len(emails), len(company_files))
                
                prog.progress((i + 1) / len(df))
            server.quit()
            st.success(f"Done! {sent_count} emails delivered.")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# --- חלק 3: דשבורד עם סננים (Dashboard with Filters) ---
st.write("---")
st.subheader("📊 Sending Dashboard")

dash_df = get_dashboard_data()

if not dash_df.empty:
    # תיבת סננים
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3)
    
    with f1:
        search_company = st.text_input("🔍 Filter by Company", "")
    with f2:
        date_range = st.date_input("📅 Filter by Date Range", [])
    with f3:
        min_files = st.number_input("📎 Min Files Count", min_value=0, value=0)
    st.markdown('</div>', unsafe_allow_html=True)

    # החלת הפילטרים על המידע
    filtered_df = dash_df.copy()
    
    if search_company:
        filtered_df = filtered_df[filtered_df['company'].str.contains(search_company, case=False, na=False)]
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[(filtered_df['date'] >= start_date) & (filtered_df['date'] <= end_date)]
    
    if min_files > 0:
        filtered_df = filtered_df[filtered_df['files_count'] >= min_files]

    # כרטיסיות מידע מעודכנות לפי הפילטר
    m1, m2, m3 = st.columns(3)
    m1.metric("Companies (Filtered)", len(filtered_df['company'].unique()))
    m2.metric("Total Emails", filtered_df['emails_sent'].sum())
    m3.metric("Total Files Sent", filtered_df['files_count'].sum())

    # הצגת הטבלה המסוננת
    st.dataframe(filtered_df, use_container_width=True, column_config={
        "date": "Date",
        "company": "Company Name",
        "emails_sent": "Recipients",
        "files_count": "Files Attached"
    })
    
    if st.button("🗑️ Reset All Data"):
        conn = sqlite3.connect('billing_dashboard.db')
        conn.cursor().execute("DELETE FROM history")
        conn.commit()
        conn.close()
        st.rerun()
else:
    st.info("No activity recorded yet.")
