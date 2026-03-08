import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף
st.set_page_config(page_title="TMC Billing Dashboard", layout="centered")

# --- ניהול בסיס נתונים (Dashboard Data) ---
def init_db():
    conn = sqlite3.connect('billing_dashboard.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, company TEXT, emails_sent INTEGER)''')
    conn.commit()
    conn.close()

def add_to_dashboard(company, count):
    conn = sqlite3.connect('billing_dashboard.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?)", 
              (datetime.now().strftime("%d/%m/%Y"), company, count))
    conn.commit()
    conn.close()

def get_dashboard_data():
    conn = sqlite3.connect('billing_dashboard.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()
    return df

init_db()

# --- עיצוב CSS ---
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .stExpander { margin-top: 20px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("TMC Billing System")

# --- חלק 1: תפעול (Setup & Files) ---
st.subheader("⚙️ Operation Center")
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
st.subheader("📧 Sender Details")
sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
user_mail = sc1.text_input("Gmail Address")
user_pass = sc2.text_input("App Password", type="password")
with sc3:
    with st.expander("🔑 App Password Help"):
        st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. 2-Step Auth ON\n3. Create 'App password'")

user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

def get_files_for_company(company_name, files_list):
    search_name = str(company_name).strip().lower()
    return [f for f in files_list if search_name in f.name.lower()]

# כפתור הפעלה
if st.button("🚀 Start Bulk Sending", use_container_width=True):
    if not up_ex or not uploaded_files or not user_mail:
        st.error("Missing fields or files!")
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
                day_val = str(row.iloc[2]).strip() if len(df.columns) > 2 else "10"
                due_date = f"{day_val} {current_month_year}"
                
                company_files = get_files_for_company(company, uploaded_files)
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'], msg['To'], msg['Subject'] = user_mail, ", ".join(emails), f"{user_subj} - {company}"
                    msg.attach(MIMEText(f"Attached files for {company}. Due: {due_date}", 'plain'))
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    sent_count += 1
                    # שמירה לדשבורד
                    add_to_dashboard(company, len(emails))
                prog.progress((i + 1) / len(df))
            server.quit()
            st.success(f"Sent {sent_count} emails!")
            st.balloons()
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# --- חלק 3: דשבורד (Dashboard) ---
st.write("---")
st.subheader("📊 Sending Dashboard")

dash_df = get_dashboard_data()

if not dash_df.empty:
    # כרטיסיות מידע (Metrics)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Companies", len(dash_df['company'].unique()))
    m2.metric("Total Emails Sent", dash_df['emails_sent'].sum())
    m3.metric("Last Sending Date", dash_df['date'].iloc[0])

    # טבלת פירוט בתוך Expander
    with st.expander("📝 Full Activity Log"):
        st.dataframe(dash_df, use_container_width=True)
    
    if st.button("🗑️ Reset Dashboard Data"):
        conn = sqlite3.connect('billing_dashboard.db')
        conn.cursor().execute("DELETE FROM history")
        conn.commit()
        conn.close()
        st.rerun()
else:
    st.info("Dashboard is empty. Start sending to see data!")
