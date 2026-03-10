import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection (🛡️ בסיס נתונים - Lowercase) ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. CSS & Design (🎨 עיצוב מקורי ושפה) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .success-msg { font-size: 100px; font-weight: 900; color: #28a745; text-align: center; margin-top: 20px; }
</style>""", unsafe_allow_html=True)

# --- 3. Helper Functions (🛡️ ניקוי סכומים) ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date_obj'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce').dt.date
            df = df.dropna(subset=['date_obj'])
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        return df
    except: return pd.DataFrame()

def clean_amount(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    try:
        clean_val = re.sub(r'[^\d.]', '', str(val))
        return float(clean_val) if clean_val else 0.0
    except: return 0.0

# --- 4. Navigation ---
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- PAGE 1: EMAIL SENDER (📧 שליחת מיילים) ---
if page == "Email Sender":
    st.title("TMC Billing System")
    st.subheader("1. Setup & Files")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'], label_visibility="collapsed")
    with c2:
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1)
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1)
        current_period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

    # 🕵️‍♂️ הבלש (The Detective)
    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name for f in uploaded_files]
            missing = [c for c in excel_comps if not any(c.lower() in fn.lower() for fn in file_names)]
            orphans = [fn for fn in file_names if not any(c.lower() in fn.lower() for c in excel_comps)]
            if missing or orphans:
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if missing: st.warning(f"Missing Files: {', '.join(missing)}")
                    if orphans: st.error(f"Unrecognized Files: {', '.join(orphans)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        # 📧 מדריך App Password מפורט לפי החוזה
        with st.expander("🔑 מדריך ליצירת App Password (חובה לשליחה)"):
            st.markdown("""
            **בלי השלבים האלו גוגל תחסום את השליחה (שגיאה 535):**
            
            1. **כנסו לקישור הבא:** [Google App Passwords](https://myaccount.google.com/apppasswords)
            2. **אימות:** גוגל תבקש מכם להיכנס לחשבון (סיסמה רגילה).
            3. **יצירה:** תחת 'App name' רשמו: **TMC Billing**.
            4. **קבלת הקוד:** לחצו על **Create**.
            5. **העתקה:** יופיע חלון עם קוד בן **16 אותיות** (בתוך מלבן צהוב).
            6. **הדבקה:** העתיקו את הקוד (ללא הרווחים) והדביקו אותו כאן בתיבת ה-Password.
            
            *הערה: אם הקישור לא עובד, ודאו ש'אימות דו-שלבי' מופעל בחשבון שלכם.*
            """)

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not up_ex or not user_mail or not user_pass:
            st.error("Missing details. Did you generate an App Password?")
        else:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                cols = [str(c).lower().strip() for c in df_master.columns]
                # איתור עמודת סכום חכם
                amount_col_idx = cols.index('amount') if 'amount' in cols else 2
                
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                with st.spinner("🚀 Sending emails and syncing to cloud..."):
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        
                        raw_val = row.iloc[amount_col_idx]
                        final_amount = clean_amount(raw_val)
                        
                        if emails and company_files:
                            msg = MIMEMultipart()
                            msg['Subject'] = f"{user_subj} - {company}"; msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, invoices attached.", 'plain'))
                            for f in company_files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                            server.send_message(msg)
                            
                            # 🕒 שעה מעודכנת לישראל (UTC+2)
                            is_time = datetime.now() + timedelta(hours=2)
                            supabase.table("billing_history").insert({
                                "date": is_time.strftime("%d/%m/%Y %H:%M"), "company": company, 
                                "amount": final_amount, "status": "Sent", "currency": "$", 
                                "sender": user_mail, "due_date": f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                            }).execute()
                
                server.quit()
                # 🎉 סיום חגיגי
                st.balloons()
                st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True)
                st.audio("https://www.myinstants.com/media/sounds/victory-sound-effect.mp3", format="audio/mp3", autoplay=True)
                time.sleep(3); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS (📊 דשבורד משלים) ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        st.info(f"🕒 **Last Email Sent on:** {df['date'].iloc[0]}")
        f_df = df.copy()
        
        m1, m2, m3 = st.columns(3)
        total_billed = f_df['amount'].sum()
        total_paid = f_df[f_df['status'] == 'Paid']['amount'].sum()
        m1.metric("Total Billed (Sent)", f"${total_billed:,.2f}")
        m2.metric("Total Received (Paid)", f"${total_paid:,.2f}")
        m3.metric("Outstanding", f"${total_billed - total_paid:,.2f}")
        
        st.divider()
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.write("**Billed by Company**")
            p1 = f_df.groupby(['company', 'currency']).agg({'amount':'sum'}).reset_index()
            st.dataframe(p1, use_container_width=True, hide_index=True)
        with c_p2:
            st.write("**Billed by Date**")
            p2 = f_df.groupby(['date_obj', 'currency']).agg({'amount':'sum'}).reset_index()
            st.dataframe(p2, use_container_width=True, hide_index=True)
    else: st.info("No data in cloud.")

# --- PAGE 3: CONTROL (🔍 לוח בקרה) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        st.success("💡 **Changes here update the Dashboard instantly.**")
        display_cols = ['id', 'company', 'date', 'amount', 'status', 'notes']
        
        def color_paid(val):
            return 'background-color: #d4edda; color: #155724; font-weight: bold;' if val == 'Paid' else ''

        edited_df = st.data_editor(df[display_cols].style.map(color_paid, subset=['status']), 
                                   column_config={
                                       "id": None, 
                                       "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"]),
                                       "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
                                   },
                                   disabled=['company', 'date'], hide_index=True, use_container_width=True)
        
        if st.button("💾 Save Changes to Cloud", use_container_width=True):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({
                    "status": row['status'], "notes": str(row.get('notes', '')), "amount": float(row['amount'])
                }).eq("id", row['id']).execute()
            st.success("Cloud Updated!"); time.sleep(0.5); st.rerun()
    else: st.info("No records found.")
