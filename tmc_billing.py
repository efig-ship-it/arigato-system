import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- פונקציות סאונד ---
def play_sound(url):
    st.components.v1.html(f"""<script>var audio = new Audio("{url}"); audio.play();</script>""", height=0)

# --- ניהול בסיס נתונים ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

def get_history_from_db():
    conn = sqlite3.connect('billing_history.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()
    return df

init_db()

# תפריט ניווט בצד
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

# --- עמוד 1: Email Sender ---
if page == "Email Sender":
    st.markdown("""<style>
    .stMetric { background-color: #f8f9fb; padding: 5px; border-radius: 8px; border: 1px solid #eee; }
    .due-date-container { display: flex; justify-content: center; width: 100%; margin-bottom: 2px; }
    .due-date-label { font-size: 14px; font-weight: 500; color: #31333F; }
    </style>""", unsafe_allow_html=True)

    st.title("TMC Billing System")

    # 1. Setup & Files
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", [str(y) for y in range(2025, 2030)], index=1, label_visibility="collapsed")
        current_month_year = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload all Invoices & Reports", type=['pdf', 'xlsx'], accept_multiple_files=True)

    # הבלש 🕵️‍♂️
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip().lower() for c in df_ex.iloc[:, 0].dropna().unique()]
            orphans = [f.name for f in uploaded_files if not any(c in f.name.lower() for comp in excel_comps)]
            if orphans:
                st.error(f"🕵️‍♂️ **הבלש מצא קבצים ללא שיוך:** {', '.join(orphans)}")
                allow_sending = st.toggle("אני מאשר שהנתונים תקינים ✅", value=False)
        except: pass

    # 2. Sender Details (הפירוט המלא נשמר)
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("""
            To send emails via Gmail, you need a unique **App Password**.
            *Standard login passwords will not work.*

            1. Go to your [**Google Account Security**](https://myaccount.google.com/security).
            2. Make sure **2-Step Verification** is turned **ON**.
            3. Search for **'App passwords'** in the top search bar.
            4. Select a name (e.g., "TMC Billing") and click **Create**.
            5. Copy the **16-character code** and paste it here.
            """)

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df = pd.read_excel(up_ex)
                prog = st.progress(0)
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.replace(" ", ""))
                sent_count = 0
                for i, row in df.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    if files and emails:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"{user_subj} - {company}"
                        msg.attach(MIMEText(f"Attached are files for {company}.\nDue: {current_month_year}", 'plain'))
                        for f in files:
                            part = MIMEApplication(f.getvalue(), Name=f.name)
                            part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                            msg.attach(part)
                        server.send_message(msg)
                        
                        conn = sqlite3.connect('billing_history.db')
                        conn.cursor().execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
                                           (datetime.now().strftime("%Y-%m-%d"), company, len(emails), len(files)))
                        conn.commit(); conn.close()
                        sent_count += 1
                    prog.progress((i + 1) / len(df))
                server.quit()
                st.balloons(); play_sound("https://github.com/robiningelbrecht/strava-activities/raw/master/files/applause.mp3")
                st.success(f"Success! {sent_count} emails sent."); time.sleep(2); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- עמוד 2: Analytics Dashboard (התוספת החדשה לבקשתך) ---
elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics Dashboard")
    df_raw = get_history_from_db()

    if not df_raw.empty:
        # פתרון ה-ValueError מהתמונה: המרה בטוחה של תאריכים
        df_raw['Date_obj'] = pd.to_datetime(df_raw['Date'], errors='coerce')
        
        # שורת ה-Metrics (החלק העליון מהתמונה שלך)
        m1, m2, m3 = st.columns(3)
        m1.metric("Companies", len(df_raw['Company'].unique()))
        m2.metric("Total Emails", int(df_raw['Recipients'].sum()))
        last_date = df_raw['Date_obj'].max()
        m3.metric("Last Sent", last_date.strftime("%d/%m/%Y") if pd.notnull(last_date) else "N/A")

        st.write("---")

        # טבלה ופילטרים ניתנים לקיפול (Expander)
        with st.expander("📂 View Activity Log & Filters", expanded=True):
            f1, f2 = st.columns([1.5, 1])
            sel_comp = f1.multiselect("Filter by Company", options=sorted(df_raw['Company'].unique().tolist()))
            sel_date_range = f2.date_input("Filter by Date Range (Calendar)", value=[])

            filtered_df = df_raw.copy()
            
            # החלת פילטר חברה
            if sel_comp:
                filtered_df = filtered_df[filtered_df['Company'].isin(sel_comp)]
            
            # החלת פילטר לוח שנה (תאריכים)
            if len(sel_date_range) == 2:
                filtered_df = filtered_df[(filtered_df['Date_obj'].dt.date >= sel_date_range[0]) & 
                                          (filtered_df['Date_obj'].dt.date <= sel_date_range[1])]
            
            # תיקון תצוגת התאריך בטבלה לפורמט DD-MM-YYYY
            display_df = filtered_df.drop(columns=['Date_obj']).copy()
            display_df['Date'] = pd.to_datetime(display_df['Date'], errors='coerce').dt.strftime("%d-%m-%Y")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        # סיכום פיבוט לפי חברה
        st.subheader("🏢 Company Pivot Summary")
        pivot = df_raw.groupby('Company').agg({'Recipients': 'sum', 'Files': 'sum', 'Date_obj': 'max'}).reset_index()
        pivot['Last Activity'] = pivot['Date_obj'].dt.strftime("%d-%m-%Y")
        st.dataframe(pivot[['Company', 'Recipients', 'Files', 'Last Activity']], use_container_width=True, hide_index=True)

    else:
        st.info("No data recorded yet. Send some emails to see analytics!")
