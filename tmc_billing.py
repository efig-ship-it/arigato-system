import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

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
                   (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER, Amount REAL, Sender TEXT, Currency TEXT,
                    Status TEXT DEFAULT 'Sent', Due_Date TEXT, Notes TEXT DEFAULT '')''')
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT rowid, * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# --- Sidebar ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- Page 1: Email Sender (Untouched) ---
if page == "Email Sender":
    st.markdown("""<style>
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
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], key="up_ex")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1)
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1)
        current_period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

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
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
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
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. 2-Step Verification ON.\n3. Create 'App passwords' (16 chars).")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                day_col = next((c for c in df_master.columns if 'day' in str(c).lower()), None)
                month_idx = months.index(sel_m) + 1
                for i, row in df_master.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    target_day = int(row[day_col]) if day_col and not pd.isna(row[day_col]) else 15
                    due_date_val = date(int(sel_y), month_idx, target_day).strftime("%Y-%m-%d")
                    total_amount = 0.0
                    detected_currency = "$"
                    for f in company_files:
                        if f.name.endswith('.xlsx'):
                            df_temp = pd.read_excel(io.BytesIO(f.getvalue()))
                            amt_col = next((c for c in df_temp.columns if 'amount' in str(c).lower()), None)
                            if amt_col:
                                sample_val = str(df_temp[amt_col].iloc[0])
                                if '₪' in sample_val: detected_currency = '₪'
                                elif '€' in sample_val: detected_currency = '€'
                                df_temp[amt_col] = pd.to_numeric(df_temp[amt_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
                                total_amount += df_temp[amt_col].sum()
                    if emails and company_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {company} - {current_period}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Hello,\nTotal Amount: {detected_currency}{total_amount:,.2f}", 'plain'))
                        for f in company_files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        conn = sqlite3.connect('billing_history.db')
                        conn.execute("INSERT INTO history (Date, Company, Recipients, Files, Amount, Sender, Currency, Status, Due_Date) VALUES (?,?,?,?,?,?,?,?,?)", 
                                     (datetime.now().strftime("%d/%m/%Y"), company, len(emails), len(company_files), total_amount, user_mail, detected_currency, 'Sent', due_date_val))
                        conn.commit(); conn.close()
                server.quit(); sound_success(); st.balloons(); st.success("Success!"); time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- Page 2: Analytics Dashboard (Untouched Layout, Fixed Metrics) ---
elif page == "Analytics Dashboard":
    st.markdown("<style>[data-testid='stMetricValue'] { font-size: 20px !important; }</style>", unsafe_allow_html=True)
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
        curr = f_df['Currency'].iloc[0] if not f_df.empty else "$"
        m_col3.metric("Total Amount Filtered", f"{curr}{f_df['Amount'].sum():,.2f}")

        st.divider()
        p1, p2 = st.columns(2)
        with p1:
            st.write("**Pivot by Company**")
            res1 = f_df.groupby(['Company', 'Currency']).agg({'Amount':'sum', 'Recipients':'sum'}).reset_index()
            res1['Amount'] = res1.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(res1.drop(columns=['Currency']), use_container_width=True, hide_index=True)
        with p2:
            st.write("**Pivot by Date**")
            res2 = f_df.groupby(['Date', 'Currency']).agg({'Amount':'sum', 'Company':'count'}).reset_index()
            res2['Amount'] = res2.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(res2.drop(columns=['Currency']), use_container_width=True, hide_index=True)
        with st.expander("📂 Full Filtered Log", expanded=True):
            log_df = f_df.copy()
            log_df['Amount'] = log_df.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(log_df[['Date', 'Company', 'Recipients', 'Files', 'Amount', 'Sender']], use_container_width=True, hide_index=True)
    else: st.info("No data recorded.")

# --- Page 3: Collections Control (COLOR CODED & EDITABLE) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections & Payment Control")
    df = get_history_df()
    
    if not df.empty:
        # פונקציה לצביעת השורות לפי סטטוס (ירוק ל-Paid, אדום ל-Sent)
        def color_status(val):
            if val == 'Paid': return 'background-color: #d4edda; color: #155724; font-weight: bold;'
            if val == 'Sent': return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
            return ''

        st.write("Edit **Status** or **Notes** (Click twice to edit notes) then click **Save All Changes**.")
        
        # תצוגה עם עריכה וצבעים
        # השתמשתי בסטייל על הסטטוס בלבד בתוך ה-Editor
        edited_df = st.data_editor(
            df[['rowid', 'Company', 'Due_Date', 'Amount', 'Currency', 'Status', 'Notes']],
            column_config={
                "rowid": None,
                "Status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"], width="medium"),
                "Notes": st.column_config.TextColumn("Notes / Ref", width="large", required=False),
                "Amount": st.column_config.NumberColumn(format="%.2f")
            },
            disabled=["Company", "Due_Date", "Amount", "Currency"],
            hide_index=True,
            use_container_width=True,
            key="col_editor_v2"
        )

        # הצגת טבלה "צבועה" למטה כבקרה (בונוס ויזואלי)
        st.write("**Live Status View:**")
        st.dataframe(edited_df.style.applymap(color_status, subset=['Status']), use_container_width=True, hide_index=True)

        if st.button("💾 Save All Changes", use_container_width=True):
            conn = sqlite3.connect('billing_history.db')
            for _, row in edited_df.iterrows():
                conn.execute("UPDATE history SET Status = ?, Notes = ? WHERE rowid = ?", (row['Status'], str(row['Notes']), row['rowid']))
            conn.commit(); conn.close()
            st.success("All changes saved!"); time.sleep(1); st.rerun()
    else:
        st.info("No records.")
