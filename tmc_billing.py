import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="TMC Billing System Pro", layout="centered")

# --- Dark Professional Theme CSS ---
st.markdown("""
<style>
    /* Global Background */
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    
    /* Metrics Styling */
    [data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    [data-testid="stMetricValue"] { 
        color: #58A6FF !important; 
        font-size: 20px !important; 
        word-break: break-all !important;
    }
    [data-testid="stMetricLabel"] { color: #8B949E !important; font-size: 14px !important; }

    /* Buttons */
    .stButton>button {
        background-color: #238636;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }
    
    /* Headers */
    h1, h2, h3 { color: #58A6FF !important; border-bottom: 1px solid #30363D; padding-bottom: 10px; }
    
    /* Detective Styling */
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; opacity: 0.8; }
    .detective-header { font-size: 80px; font-weight: 900; color: #F85149; text-align: center; text-transform: uppercase; }
    
    /* Due Date Box */
    .due-date-container { background: #161B22; padding: 10px; border-radius: 10px; border: 1px solid #30363D; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Database Management ---
def init_db():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS history 
                   (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER, Amount REAL, Sender TEXT, Currency TEXT)''')
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# --- Sidebar ---
st.sidebar.title("💎 TMC PRO PANEL")
page = st.sidebar.radio("Navigation", ["📧 Email Dispatcher", "📊 Analytics Matrix"])

if page == "📧 Email Dispatcher":
    st.title("📧 Professional Billing Dispatcher")
    
    st.subheader("1. Documentation & Files")
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p style="margin:0; font-size:12px; color:#8B949E;">BILLING PERIOD</p>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1, label_visibility="collapsed")
        current_period = f"{sel_m} {sel_y}"
        st.markdown('</div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader("Invoices (Auto-Calculating Amount)", accept_multiple_files=True)

    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            comp_col = df_ex.columns[0]
            excel_comps = [str(c).strip() for c in df_ex[comp_col].dropna().unique()]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in f.name.lower() for f in uploaded_files)]
            
            if orphans or missing:
                confirm = st.toggle("⚠️ I acknowledge and confirm data mismatches", value=False)
                allow_sending = confirm
                if not confirm:
                    if 'sound_triggered' not in st.session_state:
                        sound_detective(); st.session_state.sound_triggered = True
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    st.markdown('<p class="detective-header">ALERT</p>', unsafe_allow_html=True)
        except: pass

    st.write("---")
    st.subheader("2. Security Credentials")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Sender Gmail")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 Setup Info"):
            st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. 2-Step Verification ON.\n3. Create 'App passwords'.")

    if st.button("🚀 EXECUTE BULK SENDING", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                for i, row in df_master.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    
                    total_amount = 0.0
                    detected_currency = "$"
                    
                    for f in company_files:
                        if f.name.endswith('.xlsx'):
                            df_temp = pd.read_excel(io.BytesIO(f.getvalue()))
                            amt_col = next((c for c in df_temp.columns if 'amount' in str(c).lower()), None)
                            if amt_col:
                                sample = str(df_temp[amt_col].iloc[0])
                                if '₪' in sample: detected_currency = '₪'
                                elif '€' in sample: detected_currency = '€'
                                df_temp[amt_col] = pd.to_numeric(df_temp[amt_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
                                total_amount += df_temp[amt_col].sum()

                    if emails and company_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {company} - {current_period}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Billing files for {company}.\nTotal: {detected_currency}{total_amount:,.2f}", 'plain'))
                        for f in company_files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        
                        conn = sqlite3.connect('billing_history.db')
                        conn.execute("INSERT INTO history VALUES (?,?,?,?,?,?,?)", 
                                     (datetime.now().strftime("%d/%m/%Y"), company, len(emails), len(company_files), total_amount, user_mail, detected_currency))
                        conn.commit(); conn.close()
                
                server.quit(); sound_success(); st.balloons(); st.success("Batch Completed."); time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

elif page == "📊 Analytics Matrix":
    st.title("📊 Financial Intelligence")
    df = get_history_df()
    if not df.empty:
        df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        c1, c2 = st.columns(2)
        sel_comp = c1.multiselect("Filter Entity", options=sorted(df['Company'].unique()))
        sel_date = c2.date_input("Time Horizon", value=[df['Date_obj'].min(), df['Date_obj'].max()])

        f_df = df.copy()
        if sel_comp: f_df = f_df[f_df['Company'].isin(sel_comp)]
        if len(sel_date) == 2:
            f_df = f_df[(f_df['Date_obj'].dt.date >= sel_date[0]) & (f_df['Date_obj'].dt.date <= sel_date[1])]

        st.divider()
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Last Activity", df['Date'].iloc[0])
        m_col2.metric("Last Sender", df['Sender'].iloc[0])
        
        curr = f_df['Currency'].iloc[0] if not f_df.empty else "$"
        m_col3.metric("Total Billed", f"{curr}{f_df['Amount'].sum():,.2f}")

        st.divider()
        p1, p2 = st.columns(2)
        with p1:
            st.write("**Entity Summary**")
            res1 = f_df.groupby(['Company', 'Currency']).agg({'Amount':'sum'}).reset_index()
            res1['Amount'] = res1.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(res1.drop(columns=['Currency']), use_container_width=True, hide_index=True)
        with p2:
            st.write("**Timeline Summary**")
            res2 = f_df.groupby(['Date', 'Currency']).agg({'Amount':'sum'}).reset_index()
            res2['Amount'] = res2.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(res2.drop(columns=['Currency']), use_container_width=True, hide_index=True)

        with st.expander("📂 Transaction Log"):
            log_df = f_df.copy()
            log_df['Amount'] = log_df.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(log_df.drop(columns=['Date_obj', 'Currency']), use_container_width=True, hide_index=True)
