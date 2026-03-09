import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="TMC Billing System", layout="centered")

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Database Management ---
def init_db():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS history 
                   (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER, Amount REAL, Sender TEXT)''')
    cursor = conn.execute("PRAGMA table_info(history)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'Amount' not in columns:
        conn.execute("ALTER TABLE history ADD COLUMN Amount REAL DEFAULT 0")
    if 'Sender' not in columns:
        conn.execute("ALTER TABLE history ADD COLUMN Sender TEXT DEFAULT 'Unknown'")
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# --- Sidebar ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

# --- Page 1: Email Sender (ללא שינוי עיצובי!) ---
if page == "Email Sender":
    st.markdown("""<style>
    .stMetric { background-color: #f8f9fb; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    </style>""", unsafe_allow_html=True)

    st.title("TMC Billing System")

    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1, label_visibility="collapsed")
        current_period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload all Invoices & Reports", accept_multiple_files=True)

    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name.lower() for f in uploaded_files]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]
            
            if orphans or missing:
                confirm = st.toggle("🚨 I confirm all is correct and I am ready to send", value=False)
                allow_sending = confirm
                if not confirm:
                    if 'sound_triggered' not in st.session_state:
                        sound_detective(); st.session_state.sound_triggered = True
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if orphans: 
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.error(f"Unrecognized files: {', '.join(orphans)}")
                    if missing: 
                        st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        st.warning(f"Missing files for: {', '.join(missing)}")
                else:
                    if 'sound_triggered' in st.session_state: del st.session_state.sound_triggered
            else:
                if 'sound_triggered' in st.session_state: del st.session_state.sound_triggered
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("""
            To send emails via Gmail, you need a unique **App Password**.
            1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
            2. Make sure **2-Step Verification** is turned **ON**.
            3. Search for **'App passwords'** in the top search bar.
            4. Select a name (e.g., "TMC Billing") and click **Create**.
            5. Copy the **16-character code** and paste it here.
            """)

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df = pd.read_excel(up_ex).dropna(how='all')
                
                # מציאת עמודת הסכום בצורה חסינה (לא משנה אם אותיות קטנות או גדולות)
                amt_col = next((c for c in df.columns if str(c).lower() == 'amount'), None)
                
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                sent_count = 0
                for i, row in df.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    
                    # שליפת סכום
                    amt = 0.0
                    if amt_col:
                        amt_raw = str(row[amt_col])
                        amt = float(re.sub(r'[^\d.]', '', amt_raw)) if any(c.isdigit() for c in amt_raw) else 0.0
                    
                    if emails and files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"{user_subj} - {company}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Attached files for {company}.\nPeriod: {current_period}\nAmount: ${amt:,.2f}", 'plain'))
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        
                        conn = sqlite3.connect('billing_history.db')
                        conn.execute("INSERT INTO history VALUES (?,?,?,?,?,?)", 
                                     (datetime.now().strftime("%d/%m/%Y"), company, len(emails), len(files), amt, user_mail))
                        conn.commit(); conn.close()
                        sent_count += 1
                
                server.quit(); sound_success(); st.balloons(); st.success("Success!"); time.sleep(4); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- Page 2: Analytics Dashboard (פיבוטים דינמיים) ---
elif page == "Analytics Dashboard":
    st.title("📊 Billing Matrix Dashboard")
    df = get_history_df()
    
    if not df.empty:
        st.subheader("🔍 Filter & Analyze")
        df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Date_obj'])
        
        c1, c2 = st.columns(2)
        sel_comp = c1.multiselect("Select Company", options=sorted(df['Company'].unique()))
        sel_date = c2.date_input("Date Range", value=[df['Date_obj'].min(), df['Date_obj'].max()])

        f_df = df.copy()
        if sel_comp:
            f_df = f_df[f_df['Company'].isin(sel_comp)]
        if len(sel_date) == 2:
            f_df = f_df[(f_df['Date_obj'].dt.date >= sel_date[0]) & (f_df['Date_obj'].dt.date <= sel_date[1])]

        st.divider()

        # מדדים עליונים
        last_date = df['Date'].iloc[0] if not df.empty else "N/A"
        last_sender = df['Sender'].iloc[0] if 'Sender' in df.columns else "N/A"
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Last Sending Date", last_date)
        m_col2.metric("Last Sender Email", last_sender)
        m_col3.metric("Total Amount (Filtered)", f"${f_df['Amount'].sum():,.2f}")

        st.divider()

        # פיבוטים דינמיים
        st.subheader("📈 Summary Pivots")
        p_col1, p_col2 = st.columns(2)
        
        with p_col1:
            st.write("**Total by Company**")
            company_pivot = f_df.groupby('Company').agg({'Amount': 'sum', 'Recipients': 'sum'}).reset_index()
            company_pivot.columns = ['Company', 'Total Amount ($)', 'Total Emails']
            st.dataframe(company_pivot.style.format({"Total Amount ($)": "{:,.2f}"}), use_container_width=True, hide_index=True)

        with p_col2:
            st.write("**Total by Date**")
            date_pivot = f_df.groupby('Date').agg({'Amount': 'sum', 'Company': 'count'}).reset_index()
            date_pivot.columns = ['Date', 'Daily Total ($)', 'Total Clients']
            st.dataframe(date_pivot.style.format({"Daily Total ($)": "{:,.2f}"}), use_container_width=True, hide_index=True)

        st.divider()

        with st.expander("📂 Full Filtered Log (Detailed History)"):
            st.dataframe(f_df.drop(columns=['Date_obj']), use_container_width=True, hide_index=True)

        if st.sidebar.button("🗑️ Reset Database"):
            conn = sqlite3.connect('billing_history.db'); conn.execute("DELETE FROM history"); conn.commit(); conn.close(); st.rerun()
    else:
        st.info("No data available yet.")
