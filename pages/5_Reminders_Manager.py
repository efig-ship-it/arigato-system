import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. CORE CONNECTION ---
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_overdue_data():
    res = supabase.table("billing_history").select("*").execute()
    full_df = pd.DataFrame(res.data)
    if not full_df.empty:
        full_df['status_check'] = full_df['status'].astype(str).str.strip().str.lower()
        df = full_df[full_df['status_check'] == 'overdue'].copy()
        if not df.empty:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
            df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
            df['balance'] = df['amount'] - df['received_amount']
            return df
    return pd.DataFrame()

def get_hebrew_month(date_str):
    try:
        dt = pd.to_datetime(date_str)
        months = {
            1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
            7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
        }
        return months.get(dt.month, "")
    except:
        return "החודש האחרון"

# --- 2. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Reminders", layout="wide")

st.markdown("""
    <style>
    .recovery-title { font-size: 32px; font-weight: 800; color: #DC2626; margin-bottom: 20px; text-align: right; direction: rtl; }
    .stCheckbox { transform: scale(1.2); }
    .status-msg { padding: 10px; border-radius: 5px; margin-bottom: 15px; direction: rtl; text-align: right; }
    </style>
""", unsafe_allow_html=True)

# כותרת וסנכרון
t_col, r_col = st.columns([5, 1])
with t_col:
    st.markdown('<p class="recovery-title">ניהול תזכורות תשלום 🚨</p>', unsafe_allow_html=True)
with r_col:
    if st.button("🔄 סנכרון נתונים"):
        st.cache_data.clear()
        st.rerun()

# --- 3. הטרנזקציות (מופיעות מיד) ---
df_overdue = get_overdue_data()

if df_overdue.empty:
    st.success("אין חובות פתוחים במערכת! 🎉")
    st.stop()

st.subheader(f"נמצאו {len(df_overdue)} עסקאות בחריגה (Overdue)")

# טבלה להצגה בלבד של החריגות
st.dataframe(
    df_overdue[['company', 'due_date', 'balance']],
    column_config={
        "company": "חברה",
        "due_date": "מועד תשלום",
        "balance": st.column_config.NumberColumn("יתרת חוב", format="₪%.2f")
    },
    use_container_width=True, hide_index=True
)

st.divider()

# --- 4. הגדרות שליחה וחיבור (עם המדריך צמוד) ---
st.markdown("### 🛠️ הגדרות שליחה")
c_mail, c_pass = st.columns(2)

with c_mail:
    gmail_user = st.text_input("כתובת ה-Gmail שלך", placeholder="example@gmail.com")
    up_contacts = st.file_uploader("📁 העלה קובץ אקסל (אנשי קשר)", type=['xlsx'])

with c_pass:
    gmail_pass = st.text_input("סיסמת אפליקציה (16 תווים)", type="password")
    with st.expander("💡 איך משיגים סיסמת אפליקציה?", expanded=False):
        st.markdown("""
        <div style="direction: rtl; text-align: right; font-size: 14px;">
        1. היכנס ל-<b>Google Account</b> -> <b>Security</b>.<br>
        2. וודא ש-<b>2-Step Verification</b> פעיל.<br>
        3. חפש <b>"App Passwords"</b> בשורת החיפוש.<br>
        4. צור סיסמה חדשה (קרא לה Tuesday) והעתק את 16 התווים לכאן.
        </div>
        """, unsafe_allow_html=True)

# --- 5. הצלבת נתונים ושליחה ---
if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]
        
        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.markdown("---")
        st.markdown("### 🚀 בחירת חברות לשליחה")
        
        selected_indices = []
        h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
        h2.write("**חברה**")
        h3.write("**יתרת חוב**")
        h4.write("**אימייל יעד**")

        for idx, row in df_final.iterrows():
            col1, col2, col3, col4 = st.columns([0.5, 2, 2, 2])
            with col1:
                is_selected = st.checkbox("", key=f"send_check_{idx}")
            with col2:
                st.write(row['company'])
            with col3:
                st.write(f"₪{row['balance']:,.2f}")
            with col4:
                email_display = row[email_col] if pd.notna(row[email_col]) else "⚠️ חסר מייל"
                st.write(f"`{email_display}`")
            if is_selected:
                selected_indices.append(idx)

        # כפתור ביצוע
        if st.button("שלח תזכורות למסומנים", use_container_width=True, type="primary"):
            if not selected_indices:
                st.warning("נא לסמן לפחות חברה אחת.")
            elif not gmail_user or not gmail_pass:
                st.error("נא להזין פרטי Gmail וסיסמת אפליקציה.")
            else:
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

                    # ספינר התקדמות
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, idx in enumerate(selected_indices):
                        row = df_final.iloc[idx]
                        target_email = str(row[email_col])
                        if "@" not in target_email: continue

                        month_name = get_hebrew_month(row['due_date'])
                        
                        msg = MIMEMultipart()
                        msg['Subject'] = f"תזכורת תשלום: {row['company']}"
                        msg['To'] = target_email
                        
                        body = f"""שלום,
נכון להיום, התשלום עבור חודש {month_name} טרם הוסדר, וזאת על אף שמועד התשלום חלף.
דוח חשבוניות פתוחות לתשלום נשלח בתחילת החודש.

אנא הסדירו את התשלום באופן מיידי ועדכנו אותנו עם ביצוע ההעברה.
אי־הסדרת התשלום עלולה להוביל לסגירת החשבון ולהפסקת השירות.

במידה והתשלום בוצע בימים האחרונים, אנא שלחו אישור העברה ופירוט חשבוניות רלוונטיות.
בברכה,
צוות Tuesday"""
                        
                        msg.attach(MIMEText(body, 'plain', 'utf-8'))
                        server.send_message(msg)

                        # עדכון הסטטוס בענן
                        supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                        
                        # עדכון ספינר
                        percent = (i + 1) / len(selected_indices)
                        progress_bar.progress(percent)
                        status_text.text(f"שולח ל-{row['company']} ({i+1}/{len(selected_indices)})...")

                    server.quit()
                    st.balloons()
                    st.success("השליחה הסתיימה בהצלחה!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"שגיאה: {e}")
    except Exception as e:
        st.error(f"שגיאה בקובץ האקסל: {e}")
else:
    st.info("💡 המתן להעלאת קובץ אקסל של אנשי קשר כדי להפעיל את אפשרות השליחה.")
