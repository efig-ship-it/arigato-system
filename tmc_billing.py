import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback, re, io
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
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# --- Sidebar ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

if page == "Email Sender":
    st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
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

    uploaded_files = st.file_uploader("Upload Company Invoices (XLSX/PDF)", accept_multiple_files=True)

    # --- Detective Logic ---
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            comp_col = df_ex.columns[0]
            excel_comps = [str(c).strip() for c in df_ex[comp_col].dropna().unique()]
            file_names = [f.name.lower() for f in uploaded_files]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]
            
            if orphans or missing:
                confirm = st.toggle("🚨 I confirm data is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    if 'sound_triggered' not in st.session_state:
                        sound_detective(); st.session_state.sound_triggered = True
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if orphans: st.error(f"Unrecognized files: {', '.join(orphans)}")
                    if missing: st.warning(f"Missing files for: {', '.join(missing)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. Enable 2-Step Verification.\n3. Create 'App passwords' and paste here.")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                sent_count = 0
                for i, row in df_master.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    
                    # לוגיקת סכימה פנימית מתוך קבצי האקסל של החברה
                    total_amount = 0.0
                    for f in company_files:
                        if f.name.endswith('.xlsx'):
                            # קריאת הקובץ הספציפי של החברה (כמו Alice.xlsx)
                            df_temp = pd.read_excel(io.BytesIO(f.getvalue()))
                            amt_col = next((c for c in df_temp.columns if 'amount' in str(c).lower()), None)
                            if amt_col:
                                # ניקוי וסכימה של כל השורות בעמודה
                                df_temp[amt_col] = pd.to_numeric(df_temp[amt_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
                                total_amount += df_temp[amt_col].sum()

                    if emails and company_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {company} - {current_period}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Hello {company},\nAttached are your billing files.\nTotal Amount Calculated: ${total_amount:,.2f}", 'plain'))
                        for f in company_files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        
                        conn = sqlite3.connect('billing_history.db')
                        conn.execute("INSERT INTO history VALUES (?,?,?,?,?,?)", 
                                     (datetime.now().strftime("%d/%m/%Y"), company, len(emails), len(company_files), total_amount, user_mail))
                        conn.commit(); conn.close()
                        sent_count += 1
                
                server.quit(); sound_success(); st.balloons(); st.success(f"Success! {sent_count} sent."); time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- Page 2: Analytics Dashboard (Dynamic Pivots) ---
elif page == "Analytics Dashboard":
    st.title("📊 Billing Matrix Dashboard")
    df = get_history_df()
    if not df.empty:
        df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        c1, c2 = st.columns(2)
        sel_comp = c1.multiselect("Select Company", options=sorted(df['Company'].unique()))
        sel_date = c2.date_input("Date Range", value=[df['Date_obj'].min(), df['Date_obj'].max()])

        f_df = df.copy()
        if sel_comp: f_df = f_df[f_df['Company'].isin(sel_comp)]
        if len(sel_date) == 2:
            f_df = f_df[(f_df['Date_obj'].dt.date >= sel_date[0]) & (f_df['Date_obj'].dt.date <= sel_date[1])]

        st.divider()
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Last Sending Date", df['Date'].iloc[0])
        m_col2.metric("Last Sender", df['Sender'].iloc[0])
        m_col3.metric("Total Amount Filtered", f"${f_df['Amount'].sum():,.2f}")

        st.divider()
        p1, p2 = st.columns(2)
        with p1:
            st.write("**Pivot by Company**")
            st.dataframe(f_df.groupby('Company').agg({'Amount':'sum', 'Recipients':'sum'}).reset_index(), use_container_width=True, hide_index=True)
        with p2:
            st.write("**Pivot by Date**")
            st.dataframe(f_df.groupby('Date').agg({'Amount':'sum', 'Company':'count'}).reset_index(), use_container_width=True, hide_index=True)

        with st.expander("📂 Full Filtered Log"):
            st.dataframe(f_df.drop(columns=['Date_obj']), use_container_width=True, hide_index=True)
    else: st.info("No data recorded.")
