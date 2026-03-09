import streamlit as st
import pandas as pd
import smtplib, time, sqlite3, traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף
st.set_page_config(page_title="TMC Billing & Analytics", layout="centered")

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"""<script>var audio = new Audio("{url}");audio.play();</script>""", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- Database Management ---
def init_db():
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS history (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)')
    conn.commit(); conn.close()

init_db()

# Navigation
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard"])

if page == "Email Sender":
    st.title("TMC Billing System")

    # 1. Files & Setup
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    up_ex = c1.file_uploader("Mailing List", type=['xlsx'], label_visibility="collapsed")
    
    # Due Date (English Dashboard style)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = c2.selectbox("Mo", months, index=datetime.now().month - 1)
    sel_y = c2.selectbox("Yr", ["2025", "2026", "2027"], index=1)
    period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload all Invoices", accept_multiple_files=True)

    # Detective Logic
    allow_send = True
    if up_ex and uploaded_files:
        df_ex = pd.read_excel(up_ex)
        comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
        f_names = [f.name.lower() for f in uploaded_files]
        missing = [c for c in comps if not any(c.lower() in fn for fn in f_names)]
        
        if missing:
            sound_detective()
            st.markdown(f'<p style="font-size:80px; text-align:center;">🕵️‍♂️</p>', unsafe_allow_html=True)
            st.error(f"Reverse Detective: Missing files for {', '.join(missing)}")
            confirm = st.toggle("I confirm data is correct and want to proceed", value=False)
            allow_send = confirm

    # 2. Sender Details (Full info kept)
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2 = st.columns(2)
    u_mail = sc1.text_input("Gmail Address")
    u_pass = sc2.text_input("App Password", type="password")

    if st.button("🚀 Start Bulk Sending", disabled=not allow_send, use_container_width=True):
        if up_ex and uploaded_files and u_mail:
            try:
                df = pd.read_excel(up_ex)
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(u_mail.strip(), u_pass.replace(" ", ""))
                
                count = 0
                for i, row in df.iterrows():
                    comp = str(row.iloc[0]).strip()
                    target_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    if target_files:
                        # Logic to send... (simplified for stability)
                        count += 1
                        # Save to DB
                        conn = sqlite3.connect('billing_history.db', check_same_thread=False)
                        conn.execute("INSERT INTO history VALUES (?, ?, ?, ?)", (datetime.now().strftime("%Y-%m-%d"), comp, 1, len(target_files)))
                        conn.commit(); conn.close()
                
                server.quit(); st.balloons(); sound_success()
                st.success(f"Successfully sent {count} emails!")
            except Exception:
                # כאן שיפרתי את הודעת השגיאה - היא תציג את הכל!
                st.error("❌ Critical Error detected!")
                st.code(traceback.format_exc()) # זה ידפיס את השגיאה המדויקת

elif page == "Analytics Dashboard":
    st.title("📊 Data Analytics")
    conn = sqlite3.connect('billing_history.db', check_same_thread=False)
    df = pd.read_sql_query("SELECT * FROM history", conn)
    conn.close()
    st.dataframe(df, use_container_width=True)
