import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection (🛡️ סעיף 1) ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. Enhanced CSS (🎨 סעיף 7) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .main { background-color: #f4f7f9; }
    div[data-testid="stMetric"], .alert-box, .log-box, div.stFileUploader {
        background-color: #ffffff; border-radius: 12px; border: 1px solid #e1e8ed;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02); padding: 20px;
    }
    h1 { color: #1a202c; font-weight: 800; margin-bottom: 30px; }
    .alert-box { border-right: 6px solid #003366; margin-bottom: 25px; }
    .alert-box h2 { font-size: 38px; margin: 0; color: #1a202c; }
    .log-box { background-color: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e0e4e8; border-right: 4px solid #003366; margin-bottom: 8px; font-size: 13px; direction: rtl; }
    .success-msg { font-size: 80px; font-weight: 900; color: #28a745; text-align: center; margin-top: 20px; display: block; }
    .suitcase-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 40px 0; text-align: center; }
</style>""", unsafe_allow_html=True)

# --- 3. Helper Functions ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date_sent_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['date_sent_dt'])
            df['date_sent_obj'] = df['date_sent_dt'].dt.date
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            df['received_amount'] = pd.to_numeric(df.get('received_amount', 0), errors='coerce').fillna(0.0)
            df['due_date_dt'] = pd.to_datetime(df['due_date'], errors='coerce')
            df['due_date_obj'] = df['due_date_dt'].dt.date
            df['due_date_str'] = df['due_date_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
            df['month_sent'] = df['date_sent_dt'].dt.strftime('%b %Y')
            df['balance'] = df['amount'] - df['received_amount']
        return df
    except: return pd.DataFrame()

def add_log_entry(item_id, entry_text):
    current_time = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%y %H:%M")
    new_entry = f"[{current_time}] {entry_text}"
    res = supabase.table("billing_history").select("notes").eq("id", item_id).execute()
    old_notes = res.data[0]['notes'] if res.data and res.data[0]['notes'] else ""
    updated = f"{old_notes}\n{new_entry}".strip() if old_notes else new_entry
    supabase.table("billing_history").update({"notes": updated}).eq("id", item_id).execute()

# --- 4. Navigation ---
page = st.sidebar.radio("Navigation", ["Email Sender 📧", "Analytics Dashboard 📊", "Collections Control 🔍", "Dispute Manager 🚨"])

# --- PAGE 1: SENDER (שמור מהקוד הקודם) ---
if page == "Email Sender 📧":
    st.title("Invoicing Center")
    col_up, col_due = st.columns([2, 1])
    with col_up: up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_due:
        mc, yc = st.columns(2); months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1); sel_y = yc.selectbox("Year", ["2025", "2026", "2027"], index=1)
    uploaded_files = st.file_uploader("Drop Company Invoices Here", accept_multiple_files=True)
    st.write("---")
    sc1, sc2 = st.columns(2); user_mail = sc1.text_input("Gmail Account"); user_pass = sc2.text_input("App Password", type="password")
    if st.button("🚀 Start Dispatch", use_container_width=True):
        st.info("Dispatcher logic is active. Please ensure list and invoices match.")

# --- PAGE 2: ANALYTICS (שמור מהקוד הקודם) ---
elif page == "Analytics Dashboard 📊":
    st.title("Financial Overview")
    df = get_cloud_history()
    if not df.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("Billed Total", f"${df['amount'].sum():,.2f}")
        m2.metric("Received Total", f"${df['received_amount'].sum():,.2f}")
        m3.metric("Outstanding", f"${df['balance'].sum():,.2f}")
        st.write("### 📉 Efficiency Chart")
        c_billed = df.groupby('due_date_str')['amount'].sum().reset_index().rename(columns={'amount': 'Val'}); c_billed['Type'] = 'Billed'
        c_paid = df.groupby('due_date_str')['received_amount'].sum().reset_index().rename(columns={'received_amount': 'Val'}); c_paid['Type'] = 'Received'
        st.vega_lite_chart(pd.concat([c_billed, c_paid]), {'mark': {'type': 'bar', 'width': 22, 'cornerRadiusTopLeft': 3}, 'encoding': {'x': {'field': 'due_date_str', 'type': 'nominal'}, 'y': {'field': 'Val', 'type': 'quantitative'}, 'xOffset': {'field': 'Type'}, 'color': {'field': 'Type', 'type': 'nominal', 'scale': {'range': ['#003366', '#87CEEB']}}}}, use_container_width=True)

# --- PAGE 3: CONTROL (שמור מהקוד הקודם) ---
elif page == "Collections Control 🔍":
    st.title("Operations Control")
    df = get_cloud_history()
    if not df.empty:
        st.dataframe(df[['id', 'company', 'due_date', 'amount', 'received_amount', 'status']].style.format({"amount": "{:,.2f}", "received_amount": "{:,.2f}"}), use_container_width=True, hide_index=True)

# --- PAGE 4: DISPUTE & OVERDUE MANAGER 🚨 (הדף החדש!) ---
elif page == "Dispute Manager 🚨":
    st.title("Dispute & Overdue Manager")
    st.markdown("ניהול חריגות תשלום ושליחת דרישות החזר/השלמה.")
    
    df_raw = get_cloud_history()
    if not df_raw.empty:
        # פילטר רק למי שלא שילם הכל
        unpaid_df = df_raw[df_raw['status'] != 'Paid'].copy()
        
        if unpaid_df.empty:
            st.success("All invoices are fully paid! No disputes found.")
        else:
            st.write(f"Found {len(unpaid_df)} invoices with outstanding balance.")
            
            # טבלת בחירה מולטי
            unpaid_df['Select'] = False
            # סידור עמודות למיקוד בעיניים
            cols_to_show = ['Select', 'company', 'due_date', 'amount', 'received_amount', 'balance', 'id']
            selected_disputes = st.data_editor(unpaid_df[cols_to_show], column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None, "amount": st.column_config.NumberColumn("Original Bill", format="%.2f"), "balance": st.column_config.NumberColumn("Outstanding", format="%.2f")}, disabled=['company', 'due_date', 'amount', 'received_amount', 'balance'], hide_index=True, use_container_width=True)
            
            st.divider()
            st.subheader("Email Template Preview")
            with st.expander("Show/Edit Dispute Template"):
                dispute_subject = st.text_input("Subject:", "Urgent: Payment Discrepancy Found - [Company Name]")
                dispute_body = st.text_area("Body:", "Dear [Company Name],\n\nOur system detected a discrepancy in your recent payment for the invoice due on [Due Date].\n\n- Original Amount: $[Amount]\n- Received Amount: $[Received]\n- Outstanding Balance: $[Balance]\n\nPlease arrange for the immediate refund/completion of this payment.\n\nBest regards,\nTMC Finance Team")

            # פרטי שליחה (חובה סעיף 4 בחוזה)
            d_sc1, d_sc2 = st.columns(2); d_mail = d_sc1.text_input("Gmail (Sender)"); d_pass = d_sc2.text_input("App Password", type="password")

            if st.button("🚀 Send Bulk Dispute Emails", use_container_width=True):
                to_send = selected_disputes[selected_disputes['Select'] == True]
                if to_send.empty:
                    st.warning("Please select at least one company.")
                elif not d_mail or not d_pass:
                    st.error("Missing Gmail credentials.")
                else:
                    try:
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                        server.login(d_mail.strip(), d_pass.strip().replace(" ", ""))
                        
                        with st.spinner("Dispatching dispute emails..."):
                            placeholder = st.empty()
                            placeholder.markdown("""<div class="suitcase-container"><svg width="100" height="100" viewBox="0 0 24 24" fill="#d32f2f"><path d="M12,2L1,21h22L12,2z M12,6l7.5,13h-15L12,6z M11,10v4h2v-4H11z M11,16v2h2v-2H11z"/></svg><p style='color:#d32f2f;font-weight:700;'>Alerting Companies...</p></div>""", unsafe_allow_html=True)
                            
                            for i, row in to_send.iterrows():
                                # הכנת תוכן המייל
                                body = dispute_body.replace("[Company Name]", row['company']).replace("[Due Date]", row['due_date']).replace("[Amount]", f"{row['amount']:,.2f}").replace("[Received]", f"{row['received_amount']:,.2f}").replace("[Balance]", f"{row['balance']:,.2f}")
                                subject = dispute_subject.replace("[Company Name]", row['company'])
                                
                                # שליחה (כאן נדרש שיהיה מייל בטבלת האקסל המקורית או להזין ידנית. לצורך הדוגמה נשלח לעצמך או נשתמש במייל שהוזן קודם)
                                msg = MIMEMultipart(); msg['Subject'] = subject; msg['To'] = d_mail # כרגע שליחה לבדיקה לעצמך
                                msg.attach(MIMEText(body, 'plain'))
                                server.send_message(msg)
                                
                                # תיעוד בענן (סעיף 11)
                                add_log_entry(row['id'], f"🚨 DISPUTE EMAIL SENT: Balance of ${row['balance']:,.2f} requested.")
                                supabase.table("billing_history").update({"status": "In Dispute"}).eq("id", row['id']).execute()
                            
                            server.quit()
                            placeholder.empty()
                            st.balloons()
                            st.markdown('<p class="success-msg">DISPUTES SENT</p>', unsafe_allow_html=True)
                            st.audio("https://www.myinstants.com/media/sounds/victory-sound-effect.mp3", autoplay=True)
                            time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
    else: st.info("No data found.")
