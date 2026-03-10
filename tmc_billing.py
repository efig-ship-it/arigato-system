import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection (🛡️ בסיס נתונים) ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. CSS & Design (🎨 עיצוב ושפה) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .success-msg { font-size: 100px; font-weight: 900; color: #28a745; text-align: center; margin-top: 20px; }
</style>""", unsafe_allow_html=True)

# --- 3. Helper Functions ---
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

def extract_total_amount_from_file(uploaded_file):
    """סורק קובץ חברה ומסכם את כל עמודת ה-amount"""
    try:
        temp_df = pd.read_excel(uploaded_file)
        # מנרמל שמות עמודות לאותיות קטנות
        temp_df.columns = [str(c).lower().strip() for c in temp_df.columns]
        
        if 'amount' in temp_df.columns:
            # המרה למספר וסכימה של כל העמודה
            amounts = pd.to_numeric(temp_df['amount'].apply(clean_amount), errors='coerce').fillna(0.0)
            return float(amounts.sum())
    except Exception as e:
        st.write(f"Debug: Error reading {uploaded_file.name}: {e}")
    return 0.0

# --- 4. Navigation ---
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- PAGE 1: EMAIL SENDER ---
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

    # 🕵️‍♂️ מנגנון הבלש (400px)
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
        with st.expander("🔑 App Password Guide"):
            st.markdown("1. Google Security -> 2-Step Verification -> App Passwords -> Mail -> Generate")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not up_ex or not user_mail or not user_pass:
            st.error("Please fill all details.")
        else:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                with st.spinner("Calculating totals and sending emails..."):
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        
                        # --- סכימת סכומים מכל קבצי האקסל של החברה ---
                        total_company_amount = 0.0
                        for f in company_files:
                            if f.name.endswith('.xlsx'):
                                total_company_amount += extract_total_amount_from_file(f)
                        
                        if emails and company_files:
                            msg = MIMEMultipart()
                            msg['Subject'] = f"Invoice - {company}"; msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, invoices attached for {current_period}.", 'plain'))
                            for f in company_files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                            server.send_message(msg)
                            
                            it = datetime.now() + timedelta(hours=2)
                            supabase.table("billing_history").insert({
                                "date": it.strftime("%d/%m/%Y %H:%M"), "company": company, 
                                "amount": total_company_amount, "status": "Sent", "currency": "$", 
                                "sender": user_mail, "due_date": f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                            }).execute()
                
                server.quit()
                st.balloons(); st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True)
                st.audio("https://www.myinstants.com/media/sounds/victory-sound-effect.mp3", format="audio/mp3", autoplay=True)
                time.sleep(3); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# (דשבורד ולוח בקרה נשארים זהים - מציגים את ה-Amount שנסכם)
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        st.info(f"🕒 **Last Email Sent on:** {df['date'].iloc[0]}")
        m1, m2, m3 = st.columns(3)
        tb = df['amount'].sum(); tp = df[df['status'] == 'Paid']['amount'].sum()
        m1.metric("Total Billed", f"${tb:,.2f}"); m2.metric("Total Received", f"${tp:,.2f}"); m3.metric("Outstanding", f"${tb-tp:,.2f}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Billed by Company**")
            st.dataframe(df.groupby(['company', 'currency']).agg({'amount':'sum'}).reset_index(), use_container_width=True, hide_index=True)
        with c2:
            st.write("**Billed by Date**")
            st.dataframe(df.groupby(['date_obj', 'currency']).agg({'amount':'sum'}).reset_index(), use_container_width=True, hide_index=True)
    else: st.info("No data.")

elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        edited_df = st.data_editor(df[['id', 'company', 'date', 'amount', 'status', 'notes']], 
                                   column_config={"id": None, "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"])},
                                   disabled=['company', 'date'], hide_index=True, use_container_width=True)
        if st.button("💾 Save Changes"):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({"status": row['status'], "notes": str(row.get('notes', '')), "amount": float(row['amount'])}).eq("id", row['id']).execute()
            st.success("Saved!"); time.sleep(0.5); st.rerun()
