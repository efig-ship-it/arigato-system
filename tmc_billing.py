import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"""<script>var audio = new Audio("{url}");audio.play();</script>""", height=0)

# --- Database Management (Stable for Cloud) ---
def get_db_connection():
    return sqlite3.connect('billing_history.db', check_same_thread=False)

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS history (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

init_db()

# --- Page Logic ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

if page == "Email Sender":
    st.title("TMC Billing System")
    
    # 1. Setup
    c1, c2 = st.columns([2, 1])
    up_ex = c1.file_uploader("Mailing List (Excel)", type=['xlsx'])
    current_period = c2.text_input("Period (e.g. Mar 2026)", value=datetime.now().strftime("%b %Y"))
    uploaded_files = st.file_uploader("Upload all Invoices", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

    # 2. Sender Details
    st.write("---")
    sc1, sc2 = st.columns(2)
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")

    if st.button("🚀 Start Bulk Sending", use_container_width=True):
        if not up_ex or not uploaded_files or not user_mail or not user_pass:
            st.warning("Please fill all fields and upload files.")
        else:
            try:
                df = pd.read_excel(up_ex)
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(user_mail.strip(), user_pass.replace(" ", ""))
                
                sent_count = 0
                prog = st.progress(0)
                
                for i, row in df.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    
                    if files and emails:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice for {company} - {current_period}"
                        msg.attach(MIMEText(f"Attached files for {company}.", 'plain'))
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        # Logging to DB
                        conn = get_db_connection()
                        conn.execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
                                    (datetime.now().strftime("%d/%m/%Y"), company, len(emails), len(files)))
                        conn.commit()
                        conn.close()
                        sent_count += 1
                    prog.progress((i + 1) / len(df))
                
                server.quit()
                st.success(f"Success! {sent_count} emails sent.")
                st.balloons()
            except smtplib.SMTPAuthenticationError:
                st.error("❌ Authentication Failed: Check your Gmail App Password.")
            except Exception as e:
                # מדפיס את השגיאה המלאה כדי שנבין מה קורה
                st.error(f"Critical Error: {str(e)}")
                st.expander("Show Technical details").code(traceback.format_exc())

elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics")
    conn = get_db_connection()
    df_history = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()
    if not df_history.empty:
        st.dataframe(df_history, use_container_width=True)
    else:
        st.info("No data yet.")
