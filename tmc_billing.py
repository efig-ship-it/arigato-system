import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף - נקי וקומפקטי
st.set_page_config(page_title="TMC Billing Dashboard", layout="centered")

# --- ניהול דשבורד (SQLite) ---
def init_db():
    conn = sqlite3.connect('billing_dashboard.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (date TEXT, company TEXT, emails_sent INTEGER)''')
    conn.commit()
    conn.close()

def add_to_dashboard(company, count):
    conn = sqlite3.connect('billing_dashboard.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?)", 
              (datetime.now().strftime("%d/%m/%Y"), company, count))
    conn.commit()
    conn.close()

def get_dashboard_data():
    conn = sqlite3.connect('billing_dashboard.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()
    return df

init_db()

# עיצוב CSS לצמצום רווחים
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 0rem; }
    h1 { margin-top: 0.5rem !important; margin-bottom: 1rem !important; }
    .stVerticalBlock { gap: 0.6rem; }
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    /* יישור ה-Expander לשדות */
    .stExpander { margin-top: 28px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("TMC Billing System")

# פונקציה להשמעת צלילים
def play_sound(sound_type):
    sound_url = "https://www.myinstants.com/media/sounds/clapping.mp3" if sound_type == "success" else "https://www.myinstants.com/media/sounds/sad-trombone.mp3"
    audio_html = f'<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>'
    st.components.v1.html(audio_html, height=0)

# --- חלק 1: הגדרות וקבצים ---
st.subheader("1. Operation Center")
c1, c2 = st.columns([2, 1])

with c1:
    up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
with c2:
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    curr_y = datetime.now().year
    years = [str(y) for y in range(curr_y - 1, curr_y + 3)]
    mc, yc = st.columns(2)
    sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1)
    sel_y = yc.selectbox("Year", years, index=1)
    current_month_year = f"{sel_m} {sel_y}"

uploaded_files = st.file_uploader("Upload Invoices/Reports", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

# --- חלק 2: פרטי שולח (עם הפירוט המלא של ה-APP PASSWORD) ---
st.write("---")
st.subheader("2. Sender Details")
sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])

user_mail = sc1.text_input("Gmail Address", placeholder="your-email@gmail.com")
user_pass = sc2.text_input("App Password", type="password")

with sc3:
    # כאן החזרתי את הפירוט המלא והמפורט שביקשת
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

# --- לוגיקה לשליחה ---
if st.button("🚀 Start Bulk Sending", use_container_width=True):
    missing = []
    if not up_ex: missing.append("Mailing List")
    if not uploaded_files: missing.append("Invoice Files")
    if not user_mail: missing.append("Gmail Address")
    if not user_pass: missing.append("App Password")
    
    if missing:
        st.error(f"⚠️ Missing Information: {', '.join(missing)}")
        play_sound("error")
    else:
        try:
            df = pd.read_excel(up_ex)
            prog = st.progress(0)
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(user_mail.strip(), user_pass.replace(" ", ""))
            
            sent_count = 0
            for i, row in df.iterrows():
                company = str(row.iloc[0]).strip()
                emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                day_val = str(row.iloc[2]).strip() if len(df.columns) > 2 else "10"
                due_date = f"{day_val} {current_month_year}"
                
                # התאמת קבצים לחברה
                company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'], msg['To'], msg['Subject'] = user_mail, ", ".join(emails), f"{user_subj} - {company}"
                    body = f"Hi,\n\nAttached are the invoice and report for {company}.\nPayment is due by {due_date}.\n\nBest Regards,\nTMC Team"
                    msg.attach(MIMEText(body, 'plain'))
                    
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    
                    server.send_message(msg)
                    sent_count += 1
                    add_to_dashboard(company, len(emails))
                
                prog.progress((i + 1) / len(df))
            
            server.quit()
            if sent_count > 0:
                st.success(f"Successfully sent {sent_count} emails!")
                play_sound("success")
                st.balloons()
                time.sleep(1)
                st.rerun()
            else:
                st.error("0 emails sent. Check if filenames match company names.")
                play_sound("error")
                
        except Exception as e:
            st.error(f"❌ Error: {e}")
            play_sound("error")

# --- חלק 3: דשבורד (Dashboard) ---
st.write("---")
dash_df = get_dashboard_data()
if not dash_df.empty:
    st.subheader("📊 Sending Dashboard")
    m1, m2, m3 = st.columns(3)
    m1.metric("Companies", len(dash_df['company'].unique()))
    m2.metric("Total Emails", dash_df['emails_sent'].sum())
    m3.metric("Last Sending", dash_df['date'].iloc[0])

    with st.expander("📝 View Full Activity Log"):
        st.dataframe(dash_df, use_container_width=True)
    
    if st.button("🗑️ Reset Dashboard"):
        conn = sqlite3.connect('billing_dashboard.db')
        conn.cursor().execute("DELETE FROM history")
        conn.commit()
        conn.close()
        st.rerun()
else:
    st.info("No activity recorded yet.")
