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

# --- Page 1: Email Sender (UNTOUCHED) ---
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
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'])
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
            if not any(c.lower() in f.name.lower() for c in excel_comps for f in uploaded_files):
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    if 'sound_triggered' not in st.session_state:
                        sound_detective(); st.session_state.sound_triggered = True
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. 2-Step Verification ON.\n3. Create 'App passwords'.")

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
                        msg.attach(MIMEText(f"Hello,\nTotal: {detected_currency}{total_amount:,.2f}", 'plain'))
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

# --- Page 2: Analytics Dashboard (UNTOUCHED PIVOTS) ---
elif page == "Analytics Dashboard":
    st.markdown("<style>[data-testid='stMetricValue'] { font-size: 20px !important; }</style>", unsafe_allow_html=True)
    st.title("📊 Billing Matrix Dashboard")
    df = get_history_df()
    if not df.empty:
        total_billed = df['Amount'].sum()
        total_collected = df[df['Status'] == 'Paid']['Amount'].sum()
        total_outstanding = total_billed - total_collected
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Billed", f"${total_billed:,.2f}")
        m2.metric("Total Collected", f"${total_collected:,.2f}")
        m3.metric("Outstanding", f"${total_outstanding:,.2f}")
        m4.metric("Last Sender", df['Sender'].iloc[0])
        st.divider()
        p1, p2 = st.columns(2)
        with p1:
            st.write("**Pivot by Company**")
            res1 = df.groupby(['Company', 'Currency']).agg({'Amount':'sum'}).reset_index()
            res1['Amount'] = res1.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(res1.drop(columns=['Currency']), use_container_width=True, hide_index=True)
        with p2:
            st.write("**Pivot by Date**")
            res2 = df.groupby(['Date', 'Currency']).agg({'Amount':'sum'}).reset_index()
            res2['Amount'] = res2.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(res2.drop(columns=['Currency']), use_container_width=True, hide_index=True)
        with st.expander("📂 Full History Log", expanded=True):
            log_df = df.copy()
            log_df['Amount'] = log_df.apply(lambda x: f"{x['Currency']}{x['Amount']:,.2f}", axis=1)
            st.dataframe(log_df[['Date', 'Company', 'Amount', 'Status', 'Sender']], use_container_width=True, hide_index=True)
    else: st.info("No data.")

# --- Page 3: Collections Control (SINGLE TABLE + AUTO COLOR) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections & Payment Control")
    df = get_history_df()
    if not df.empty:
        today = date.today()
        # לוגיקת חריגה אוטומטית לתצוגה
        def apply_overdue_logic(row):
            due = datetime.strptime(row['Due_Date'], "%Y-%m-%d").date() if row['Due_Date'] else None
            if row['Status'] != 'Paid' and due and today > due: return 'Overdue'
            return row['Status']
        
        df['Status'] = df.apply(apply_overdue_logic, axis=1)

        # פונקציית צביעת סטטוס בלבד
        def color_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white; font-weight: bold;'
            if val == 'Overdue': return 'background-color: #dc3545; color: white; font-weight: bold;'
            return ''

        st.write("Edit **Status** or **Notes** (Double-click to type). Colors apply after **Save**.")
        
        # טבלה אחת לעריכה עם צביעה מובנית
        edited_df = st.data_editor(
            df[['rowid', 'Company', 'Due_Date', 'Amount', 'Currency', 'Status', 'Notes']].style.map(color_status, subset=['Status']),
            column_config={
                "rowid": None,
                "Status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute", "Overdue"]),
                "Notes": st.column_config.TextColumn("Notes / Ref", width="large"),
                "Amount": st.column_config.NumberColumn(format="%.2f")
            },
            disabled=["Company", "Due_Date", "Amount", "Currency"],
            hide_index=True, use_container_width=True, key="col_editor_v5"
        )
        
        if st.button("💾 Save All Changes", use_container_width=True):
            conn = sqlite3.connect('billing_history.db')
            for _, row in edited_df.iterrows():
                # שומרים כ-Sent אם זה Overdue כדי שהלוגיקה תמשיך לבדוק אוטומטית
                save_status = 'Sent' if row['Status'] == 'Overdue' else row['Status']
                conn.execute("UPDATE history SET Status = ?, Notes = ? WHERE rowid = ?", (save_status, str(row['Notes']), row['rowid']))
            conn.commit(); conn.close()
            st.success("Changes Saved!"); time.sleep(1); st.rerun()
    else: st.info("No records.")
