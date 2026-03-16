import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client

# --- 1. חיבור לענן ---
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

# פונקציה לחילוץ שם החודש בעברית מהתאריך
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

# --- 2. עיצוב הממשק ---
st.set_page_config(page_title="Tuesday | Recovery", layout="wide")

st.markdown("""
    <style>
    .recovery-title { font-size: 32px; font-weight: 800; color: #DC2626; margin-bottom: 10px; text-align: right; }
    .stCheckbox { transform: scale(1.2); }
    .guide-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-right: 5px solid #1E3A8A; margin-bottom: 20px; }
    div[target="descriptor"] { text-align: right; direction: rtl; }
    </style>
""", unsafe_allow_html=True)

# כותרת וכפתור סנכרון
t_col, r_col = st.columns([5, 1])
with t_col:
    st.markdown('<p class="recovery-title">ניהול תזכורות תשלום (Page 5) 🚨</p>', unsafe_allow_html=True)
with r_col:
    if st.button("🔄 סנכרון נתונים"):
        st.cache_data.clear()
        st.rerun()

# --- 3. מדריך APP PASSWORD ---
with st.expander("💡 מדריך להגדרת סיסמת אפליקציה (Gmail App Password)", expanded=False):
    st.markdown("""
    <div style="direction: rtl; text-align: right;">
    כדי לשלוח מיילים מהמערכת, עליך להשתמש בסיסמה ייעודית ולא בסיסמת המייל הרגילה שלך:
    1. היכנס להגדרות <b>Google Account</b>.
    2. בחר בלשונית <b>Security</b> (אבטחה).
    3. וודא שמוגדר <b>2-Step Verification</b> (אימות דו-שלבי).
    4. חפש בשורת החיפוש למעלה <b>"App Passwords"</b>.
    5. תחת "Select App" בחר 'Other' וקרא לזה 'Tuesday App'.
    6. העתק את הקוד בן 16 התווים שקיבלת והדבק אותו בשדה למטה.
    </div>
    """, unsafe_allow_html=True)

# הגדרות שליחה
with st.expander("🛠️ הגדרות שליחה ורשימת תפוצה", expanded=True):
    up_contacts = st.file_uploader("העלה קובץ אקסל אנשי קשר", type=['xlsx'])
    c1, c2 = st.columns(2)
    gmail_user = c1.text_input("כתובת ה-Gmail שלך")
    gmail_pass = c2.text_input("סיסמת אפליקציה (16 תווים)", type="password")

# --- 4. עיבוד הנתונים ---
df_overdue = get_overdue_data()

if df_overdue.empty:
    st.success("אין חובות פתוחים! הכל מעודכן בענן. 🎉")
    st.stop()

if up_contacts:
    try:
        df_emails = pd.read_excel(up_contacts)
        df_emails.columns = [str(c).lower().strip() for c in df_emails.columns]
        email_col = next((c for c in df_emails.columns if 'email' in c or 'mail' in c), None)
        comp_col = df_emails.columns[0]
        df_final = pd.merge(df_overdue, df_emails[[comp_col, email_col]], left_on='company', right_on=comp_col, how='left')

        st.subheader(f"נמצאו {len(df_final)} עסקאות בחריגה")
        
        # תצוגת צ'קלקלה
        selected_indices = []
        h1, h2, h3, h4 = st.columns([0.5, 2, 2, 2])
        h2.write("**חברה**")
        h3.write("**סכום חוב**")
        h4.write("**אימייל**")

        for idx, row in df_final.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([0.5, 2, 2, 2])
                with col1:
                    is_selected = st.checkbox("", key=f"ov_{idx}")
                with col2:
                    st.write(row['company'])
                with col3:
                    st.write(f"₪{row['balance']:,.2f}")
                with col4:
                    email_display = row[email_col] if pd.notna(row[email_col]) else "⚠️ חסר מייל"
                    st.write(f"`{email_display}`")
                if is_selected:
                    selected_indices.append(idx)

        st.divider()

        # --- 5. מנגנון השליחה עם ספינר ---
        if st.button("🚀 שלח תזכורות למסומנים", use_container_width=True, type="primary"):
            if not selected_indices:
                st.warning("נא לסמן לפחות חברה אחת.")
            elif not gmail_user or not gmail_pass:
                st.error("חסרים פרטי גישה למייל.")
            else:
                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(gmail_user.strip(), gmail_pass.strip().replace(" ", ""))

                    # ספינר התקדמות (Progress Bar)
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, idx in enumerate(selected_indices):
                        row = df_final.iloc[idx]
                        target_email = str(row[email_col])
                        if "@" not in target_email: continue

                        month_name = get_hebrew_month(row['due_date'])
                        
                        # בניית המייל עם הטמפלט החדש
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
                        status_text.text(f"שולח מייל ל-{row['company']} ({i+1}/{len(selected_indices)})...")

                    server.quit()
                    st.balloons()
                    st.success("כל המיילים נשלחו והסטטוסים עודכנו בענן!")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"שגיאה בשליחה: {e}")
    except Exception as e:
        st.error(f"שגיאה בקובץ האקסל: {e}")
else:
    st.info("נא להעלות את רשימת אנשי הקשר כדי להתחיל.")
