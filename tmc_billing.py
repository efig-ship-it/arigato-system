import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף - TMC Billing System
st.set_page_config(page_title="TMC Billing System", layout="centered")

# --- ניהול בסיס נתונים להיסטוריה ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit()
    conn.close()

def add_to_history(company, recipients, files):
    conn = sqlite3.connect('billing_history.db')
    c = conn.cursor()
    c.execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
              (datetime.now().strftime("%d/%m/%Y"), company, recipients, files))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect('billing_history.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close()
    return df

init_db()

# עיצוב CSS לצמצום רווחים ומראה נקי
st.markdown("""
    <style>
    .block-container { padding-top: 3rem; padding-bottom: 0rem; }
    h1 { margin-top: 1rem !important; margin-bottom: 1rem !important; }
    .stVerticalBlock { gap: 0.6rem; }
    hr { margin: 0.6em 0px; }
    .stExpander { margin-top: 28px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("TMC Billing System")

def play_sound(sound_type):
    sound_url = "https://www.myinstants.com/media/sounds/clapping.mp3" if sound_type == "success" else "https://www.myinstants.com/media/sounds/sad-trombone.mp3"
    audio_html = f'<audio autoplay><source src="{sound_url}" type="audio/mp3"></audio>'
    st.components.v1.html(audio_html, height=0)

# --- חלק 1: הגדרות וקבצים ---
st.subheader("1. Setup & Files")
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

uploaded_files = st.file_uploader("Upload all Invoices & Reports (PDF/Excel)", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True)

# --- חלק 2: פרטי שולח ---
st.write("---")
st.subheader("2. Sender Details")
sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
user_mail = sc1.text_input("Gmail Address", placeholder="example@gmail.com")
user_pass = sc2.text_input("App Password", type="password")

with sc3:
    with st.expander("🔑 How to create an App Password?"):
        st.markdown("""
        1. [Google Security](https://myaccount.google.com/security).
        2. 2-Step Verification: **ON**.
        3. Search **'App passwords'**.
        4. Copy the **16-character code**.
        """)

user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_month_year}")

# --- לוגיקה לשליחה ---
if st.button("🚀 Start Bulk Sending", use_container_width=True):
    if not uploaded_files or not up_ex or not user_mail or not user_pass:
        st.error("Missing information!")
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
                
                company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                
                if company_files and emails:
                    msg = MIMEMultipart()
                    msg['From'], msg['To'], msg['Subject'] = user_mail, ", ".join(emails), f"{user_subj} - {company}"
                    msg.attach(MIMEText(f"Attached files for {company}.", 'plain'))
                    for f in company_files:
                        part = MIMEApplication(f.getvalue(), Name=f.name)
                        part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                        msg.attach(part)
                    server.send_message(msg)
                    sent_count += 1
                    add_to_history(company, len(emails), len(company_files))
                
                prog.progress((i + 1) / len(df))
            
            server.quit()
            st.success(f"Successfully sent {sent_count} emails!")
            play_sound("success")
            st.balloons()
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
            play_sound("error")

# --- חלק 3: היסטוריה עם סינון וחיפוש מובנה ---
st.write("---")
history_df = get_history()

if not history_df.empty:
    with st.expander("📊 Permanent Sending History (Searchable Table)"):
        st.info("💡 Tip: Click any header to sort. Use the search bar at the top right of the table to filter.")
        
        # שימוש ב-st.data_editor המאפשר פונקציות מתקדמות של טבלה
        st.data_editor(
            history_df,
            use_container_width=True,
            hide_index=True,
            disabled=True, # מונע עריכה ידנית, רק לצפייה וסינון
            column_config={
                "Date": st.column_config.TextColumn("Date"),
                "Company": st.column_config.TextColumn("Company"),
                "Recipients": st.column_config.NumberColumn("Recipients"),
                "Files": st.column_config.NumberColumn("Files Sent")
            }
        )
        
        if st.button("🗑️ Clear All History"):
            conn = sqlite3.connect('billing_history.db')
            conn.cursor().execute("DELETE FROM history")
            conn.commit()
            conn.close()
            st.rerun()
else:
    st.info("No sending history found yet.")
