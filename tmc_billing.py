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

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Database ---
def init_db():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS history (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)')
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
    .stMetric { background-color: #f8f9fb; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 90px; text-align: center; margin-bottom: 0px; margin-top: 20px; }
    .detective-header { font-size: 45px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; }
    .reverse-detective-header { font-size: 45px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; }
    </style>""", unsafe_allow_html=True)

    st.title("TMC Billing System")

    # 1. Setup
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

    # Detective Logic
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name.lower() for f in uploaded_files]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]
            if orphans or missing:
                if 'sound_played' not in st.session_state:
                    sound_detective(); st.session_state.sound_played = True
                with st.info("🚨 **Action Required: Data Validation**"):
                    confirm = st.toggle("I confirm that data is correct", value=False)
                    allow_sending = confirm
                if not confirm:
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if orphans: st.error(f"Detective Alert! Unrecognized files: {', '.join(orphans)}")
                    if missing: st.warning(f"Reverse Detective! Missing files for: {', '.join(missing)}")
        except: pass

    # 2. Sender Details
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. [Google Security](https://myaccount.google.com/security)\n2. Enable 2-Step Verification.\n3. Search 'App passwords' and create one.")

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df = pd.read_excel(up_ex).dropna(how='all')
                prog = st.progress(0)
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                sent_count = 0
                for i, row in df.iterrows():
                    company = str(row.iloc[0]).strip()
                    raw_emails = str(row.iloc[1]).split(',')
                    emails = [e.strip() for e in raw_emails if '@' in e and '.' in e]
                    files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    
                    if emails and files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"{user_subj} - {company}"
                        msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Attached files for {company}.\nPeriod: {current_period}", 'plain'))
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        
                        server.send_message(msg)
                        
                        conn = sqlite3.connect('billing_history.db', check_same_thread=False)
                        conn.execute("INSERT INTO history VALUES (?, ?, ?, ?)", (datetime.now().strftime("%d/%m/%Y"), company, len(emails), len(files)))
                        conn.commit(); conn.close()
                        sent_count += 1
                    
                    prog.progress((i + 1) / len(df))
                
                server.quit(); st.balloons(); sound_success()
                st.success(f"Done! {sent_count} emails sent.")
                time.sleep(2); st.rerun()
            except Exception as e:
                st.error(f"❌ Critical Error: {str(e)}")
                with st.expander("Show Details"): st.code(traceback.format_exc())

# --- Page 2: Analytics ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    df_raw = get_history_df()
    if not df_raw.empty:
        # המרה בטוחה של התאריכים לצורך הפילטר
        df_raw['Date_obj'] = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce')
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Companies", len(df_raw['Company'].unique()))
        m2.metric("Total Emails", int(df_raw['Recipients'].sum()))
        m3.metric("Last Activity", df_raw['Date'].iloc[0])
        
        st.write("---")
        
        # 1. Pivot Summary (תמיד מציג הכל או לפי הפילטר)
        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({'Recipients': 'sum', 'Files': 'sum'}).reset_index()
        st.dataframe(pivot, use_container_width=True, hide_index=True)
        
        st.write("---")
        
        # 2. Activity Log עם פילטרים (כולל לוח שנה)
        with st.expander("📂 Detailed Activity Log & Filters", expanded=True):
            f1, f2 = st.columns([1.5, 1])
            sel_comp = f1.multiselect("Filter by Company", options=sorted(df_raw['Company'].unique().tolist()))
            
            # פילטר לוח שנה
            sel_range = f2.date_input("Filter by Date Range (Calendar)", value=[])
            
            filtered_df = df_raw.copy()
            
            # החלת פילטר חברה
            if sel_comp:
                filtered_df = filtered_df[filtered_df['Company'].isin(sel_comp)]
            
            # החלת פילטר לוח שנה (רק אם נבחרו שני תאריכים)
            if len(sel_range) == 2:
                filtered_df = filtered_df[(filtered_df['Date_obj'].dt.date >= sel_range[0]) & 
                                          (filtered_df['Date_obj'].dt.date <= sel_range[1])]
            
            # הצגת הטבלה ללא עמודת העזר של התאריכים
            st.dataframe(filtered_df.drop(columns=['Date_obj']), use_container_width=True, hide_index=True)
            
        if st.sidebar.button("🗑️ Reset All History"):
             conn = sqlite3.connect('billing_history.db', check_same_thread=False); conn.execute("DELETE FROM history"); conn.commit(); conn.close(); st.rerun()

    else:
        st.info("No data yet.")
