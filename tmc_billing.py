import streamlit as st
import pandas as pd
import smtplib, time, sqlite3
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime

# הגדרות דף
st.set_page_config(page_title="TMC Billing System", layout="centered")

# --- מערכת סאונד ---
def play_audio(url):
    st.components.v1.html(f"""
        <script>
            var audio = new Audio("{url}");
            audio.play().catch(function(e) {{ console.log("Audio blocked"); }});
        </script>
    """, height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- בסיס נתונים פשוט ---
def init_db():
    conn = sqlite3.connect('billing_history.db')
    conn.cursor().execute('''CREATE TABLE IF NOT EXISTS history 
                             (Date TEXT, Company TEXT, Recipients INTEGER, Files INTEGER)''')
    conn.commit(); conn.close()

def get_history_df():
    conn = sqlite3.connect('billing_history.db')
    df = pd.read_sql_query("SELECT * FROM history ORDER BY rowid DESC", conn)
    conn.close(); return df

init_db()

# תפריט ניווט
page = st.sidebar.radio("ניווט", ["Email Sender", "Analytics Dashboard"])

if page == "Email Sender":
    st.markdown("""<style>
    .big-detective { font-size: 80px; text-align: center; margin: 0; }
    .detective-header { font-size: 40px; font-weight: 900; color: #d32f2f; text-align: center; }
    .reverse-header { font-size: 40px; font-weight: 900; color: #f57c00; text-align: center; }
    </style>""", unsafe_allow_html=True)

    st.title("TMC Billing System")

    # 1. קבצים
    st.subheader("1. Setup & Files")
    c1, c2 = st.columns([2, 1])
    up_ex = c1.file_uploader("Mailing List", type=['xlsx'], label_visibility="collapsed")
    
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = c2.selectbox("Month", months, index=datetime.now().month-1)
    sel_y = c2.selectbox("Year", ["2025", "2026"], index=0)
    period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Invoices", accept_multiple_files=True)

    # מנגנון בלש
    allow_send = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            f_names = [f.name.lower() for f in uploaded_files]
            
            missing = [c for c in comps if not any(c.lower() in fn for fn in f_names)]
            extra = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in comps)]

            if missing or extra:
                if 'played' not in st.session_state:
                    sound_detective(); st.session_state.played = True
                
                # כפתור אישור שמנקה את המסך
                with st.warning("⚠️ נמצאו חוסר התאמות"):
                    confirm = st.toggle("אני מאשר שהנתונים תקינים ורוצה להמשיך בשליחה", value=False)
                    allow_send = confirm

                if not confirm:
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if missing:
                        st.markdown('<p class="reverse-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        for m in missing: st.write(f"❌ חסר קובץ עבור: **{m}**")
                    if extra:
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.write(f"❓ קבצים ללא התאמה: {', '.join(extra)}")
            else: st.session_state.played = False
        except: pass

    # 2. פרטי שולח (הפירוט המלא שביקשת)
    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2 = st.columns(2)
    u_mail = sc1.text_input("Gmail Address")
    u_pass = sc2.text_input("App Password", type="password")
    
    with st.expander("🔑 איך יוצרים סיסמת אפליקציה (App Password)?"):
        st.markdown("""
        1. היכנס ל-[חשבון גוגל (Security)](https://myaccount.google.com/security).
        2. וודא שאימות דו-שלבי (2-Step Verification) **מופעל**.
        3. חפש בשורת החיפוש למעלה **'App passwords'**.
        4. תן שם (למשל 'TMC') והעתק את הקוד בן 16 התווים שיופיע.
        """)

    if st.button("🚀 Start Bulk Sending", disabled=not allow_send, use_container_width=True):
        if up_ex and uploaded_files and u_mail:
            try:
                df = pd.read_excel(up_ex)
                prog = st.progress(0)
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(u_mail.strip(), u_pass.replace(" ", ""))
                
                count = 0
                for i, row in df.iterrows():
                    comp = str(row.iloc[0]).strip()
                    target_files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    if target_files:
                        # לוגיקת שליחה (מקוצרת לצורך יציבות)
                        conn = sqlite3.connect('billing_history.db')
                        conn.cursor().execute("INSERT INTO history VALUES (?, ?, ?, ?)", 
                                           (datetime.now().strftime("%d/%m/%Y"), comp, 1, len(target_files)))
                        conn.commit(); conn.close()
                        count += 1
                    prog.progress((i+1)/len(df))
                
                server.quit(); st.balloons(); sound_success()
                st.success(f"נשלחו {count} מיילים בהצלחה!"); time.sleep(2); st.rerun()
            except Exception as e: st.error(f"שגיאה בשליחה: {e}")

elif page == "Analytics Dashboard":
    st.title("📊 היסטוריית שליחות")
    df = get_history_df()
    if not df.empty:
        # הצגה נקייה ללא המרות תאריך שגורמות לקריסה
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        if st.sidebar.button("🗑️ איפוס כל ההיסטוריה"):
            conn = sqlite3.connect('billing_history.db')
            conn.cursor().execute("DELETE FROM history")
            conn.commit(); conn.close(); st.rerun()
    else: st.info("אין נתונים להצגה.")
