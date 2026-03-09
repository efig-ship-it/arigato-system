import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="TMC Billing Tracker", layout="wide")

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Database Management ---
def init_db():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS history 
                   (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER, Amount REAL)''')
    cursor = conn.execute("PRAGMA table_info(history)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'Amount' not in columns:
        conn.execute("ALTER TABLE history ADD COLUMN Amount REAL DEFAULT 0")
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# --- Sidebar ---
st.sidebar.title("TMC Billing Control")
page = st.sidebar.radio("Navigation", ["📧 Send Invoices", "📊 Client Billing Matrix"])

# --- Page 1: Email Sender ---
if page == "📧 Send Invoices":
    st.markdown("""<style>
    .big-detective { font-size: 400px; text-align: center; margin-top: -50px; }
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; }
    </style>""", unsafe_allow_html=True)

    st.title("📧 Bulk Billing Dispatcher")
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_b:
        mo_col, yr_col = st.columns(2)
        sel_m = mo_col.selectbox("Month", ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], index=datetime.now().month-1)
        sel_y = yr_col.selectbox("Year", [2025, 2026, 2027], index=1)
        period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Invoices/Reports", accept_multiple_files=True)

    allow_sending = True
    if up_ex and uploaded_files:
        df_ex = pd.read_excel(up_ex)
        excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        file_names = [f.name.lower() for f in uploaded_files]
        orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
        missing = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]

        if orphans or missing:
            confirm = st.toggle("🚨 I confirm data is correct (Hides Detective)", value=False)
            allow_sending = confirm
            if not confirm:
                if 'snd' not in st.session_state:
                    sound_detective(); st.session_state.snd = True
                st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                st.markdown('<p class="detective-header">DATA MISMATCH!</p>', unsafe_allow_html=True)
        else:
            if 'snd' in st.session_state: del st.session_state.snd

    st.divider()
    c1, c2, c3 = st.columns([1,1,1.5])
    u_mail = c1.text_input("Gmail Address")
    u_pass = c2.text_input("App Password", type="password")
    with c3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("""
            1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
            2. Make sure **2-Step Verification** is turned **ON**.
            3. Search for **'App passwords'** in the top search bar.
            4. Select a name (e.g., "TMC Billing") and click **Create**.
            5. Copy the **16-character code** and paste it here.
            """)

    if st.button("🚀 START SENDING", use_container_width=True, disabled=not allow_sending):
        try:
            df = pd.read_excel(up_ex).dropna(how='all')
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
            server.login(u_mail.strip(), u_pass.strip().replace(" ", ""))
            
            for i, row in df.iterrows():
                comp = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                amt_str = str(row.get('Amount', 0))
                amt = float(re.sub(r'[^\d.]', '', amt_str)) if any(c.isdigit() for c in amt_str) else 0.0
                
                if emails and files:
                    msg = MIMEMultipart()
                    msg['Subject'] = f"Invoice - {comp} - {period}"
                    msg['To'] = ", ".join(emails)
                    msg.attach(MIMEText(f"Hello,\nAttached is the billing for {comp}.\nAmount: ${amt:,.2f}", 'plain'))
                    for f in files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    
                    conn = sqlite3.connect('billing_history.db')
                    conn.execute("INSERT INTO history VALUES (?,?,?,?,?)", 
                                 (datetime.now().strftime("%d/%m/%Y"), comp, len(emails), len(files), amt))
                    conn.commit(); conn.close()
            
            server.quit(); sound_success(); st.balloons(); st.success("Success!"); time.sleep(2); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- Page 2: Dashboard ---
elif page == "📊 Client Billing Matrix":
    st.title("📊 Client Billing Matrix")
    df = get_history_df()
    
    if not df.empty:
        # תיקון השגיאה: המרת תאריכים בצורה בטוחה
        df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        
        # ניקוי שורות שלא הצליחו לעבור המרה
        df = df.dropna(subset=['Date_obj'])
        
        if not df.empty:
            df['Month'] = df['Date_obj'].dt.strftime('%b %Y')

            st.subheader("💰 Total Monthly Billing per Client")
            # מטריצה של לקוח מול חודש
            billing_matrix = df.pivot_table(
                index='Company', 
                columns='Month', 
                values='Amount', 
                aggfunc='sum', 
                fill_value=0
            )
            
            st.dataframe(billing_matrix.style.format("${:,.2f}"), use_container_width=True)

            st.divider()
            st.subheader("📂 Detailed History")
            st.dataframe(df.drop(columns=['Date_obj', 'Month']), use_container_width=True, hide_index=True)
        else:
            st.warning("No valid dates found in history.")
        
        if st.sidebar.button("🗑️ Reset History"):
            conn = sqlite3.connect('billing_history.db'); conn.execute("DELETE FROM history"); conn.commit(); conn.close(); st.rerun()
    else:
        st.info("No data yet.")
