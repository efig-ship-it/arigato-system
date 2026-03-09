import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="TMC Billing & Analytics Pro", layout="wide", initial_sidebar_state="expanded")

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"""
        <script>
            var audio = new Audio("{url}");
            audio.play().catch(e => console.log("Audio blocked"));
        </script>
    """, height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Database Management (Auto-Repairing) ---
def init_db():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    # יצירת טבלה בסיסית
    conn.execute('''CREATE TABLE IF NOT EXISTS history 
                   (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    # בדיקה והוספת עמודת Amount אם חסרה (מונע את ה-KeyError שקיבלת)
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
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1063/1063302.png", width=100)
st.sidebar.title("TMC Control Panel")
page = st.sidebar.radio("Navigation", ["📧 Email Dispatcher", "📊 Business Dashboard"])

# --- Page 1: Email Dispatcher ---
if page == "📧 Email Dispatcher":
    st.markdown("""<style>
    .big-detective { font-size: 400px; text-align: center; margin-top: -50px; }
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; }
    </style>""", unsafe_allow_html=True)

    st.title("📧 Bulk Billing Dispatcher")
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_b:
        st.write("**Due Date Selection**")
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
                st.markdown(f'<p class="detective-header">MISSING DATA!</p>', unsafe_allow_html=True)
                if orphans: st.error(f"Unknown Files: {', '.join(orphans)}")
                if missing: st.warning(f"Missing Files for: {', '.join(missing)}")
        else:
            if 'snd' in st.session_state: del st.session_state.snd

    st.divider()
    
    # Sender Details Section
    c1, c2, c3 = st.columns([1,1,1.5])
    u_mail = c1.text_input("Gmail Address")
    u_pass = c2.text_input("App Password", type="password")
    with c3:
        with st.expander("🔑 Setup Guide (App Password)"):
            st.write("1. Go to [Google Security](https://myaccount.google.com/security)")
            st.write("2. Enable 2-Step Verification.")
            st.write("3. Create 'App Password' and paste here.")

    u_subj = st.text_input("Email Subject", value=f"Invoice Payment - {period}")

    if st.button("🚀 EXECUTE BULK SENDING", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and u_mail:
            try:
                df = pd.read_excel(up_ex).dropna(how='all')
                prog = st.progress(0)
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(u_mail.strip(), u_pass.strip().replace(" ", ""))
                
                sent_count = 0
                for i, row in df.iterrows():
                    comp = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    
                    # ניקוי סכום מתווים לא רצויים
                    amt_raw = str(row.get('Amount', 0))
                    amt = float(re.sub(r'[^\d.]', '', amt_raw)) if amt_raw else 0.0
                    
                    if emails and files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"{u_subj} - {comp}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Attached are the billing files for {comp}.\nTotal Amount: ${amt:,.2f}", 'plain'))
                        
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        conn = sqlite3.connect('billing_history.db')
                        conn.execute("INSERT INTO history VALUES (?,?,?,?,?)", 
                                     (datetime.now().strftime("%d/%m/%Y"), comp, len(emails), len(files), amt))
                        conn.commit(); conn.close()
                        sent_count += 1
                    prog.progress((i + 1) / len(df))
                
                server.quit(); sound_success(); st.balloons()
                st.success(f"Successfully sent {sent_count} emails!"); time.sleep(3); st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

# --- Page 2: Dashboard ---
elif page == "📊 Business Dashboard":
    st.title("📊 Business & Financial Analytics")
    df = get_history_df()
    
    if not df.empty:
        # Metrics Cards
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Revenue", f"${df['Amount'].sum():,.2f}")
        m2.metric("Total Invoices", len(df))
        m3.metric("Total Recipients", int(df['Recipients'].sum()))
        m4.metric("Avg. Invoice", f"${df['Amount'].mean():,.2f}")

        st.divider()
        
        # PIVOT TABLES
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏢 Revenue by Company")
            comp_pivot = df.groupby('Company').agg({'Amount':'sum', 'Files':'sum'}).reset_index()
            st.dataframe(comp_pivot.sort_values('Amount', ascending=False), use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("📅 Revenue by Date")
            date_pivot = df.groupby('Date').agg({'Amount':'sum', 'Company':'count'}).rename(columns={'Company':'Invoices'}).reset_index()
            st.dataframe(date_pivot, use_container_width=True, hide_index=True)

        st.divider()
        
        # LOGS
        with st.expander("🔍 Detailed Transaction Log"):
            st.dataframe(df, use_container_width=True, hide_index=True)

        if st.sidebar.button("🗑️ Clear Database"):
            conn = sqlite3.connect('billing_history.db'); conn.execute("DELETE FROM history"); conn.commit(); conn.close(); st.rerun()
    else:
        st.info("No data available yet. Start by sending invoices!")
