import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# --- 1. Supabase Connection ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        supabase.table("billing_history").select("id").limit(1).execute()
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. CSS & Design ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- 3. Helper Functions ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            # המרה בטוחה לתאריכים - מטפל בשגיאות המרה
            df['date_obj'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce').dt.date
            df = df.dropna(subset=['date_obj']) # מסיר שורות עם תאריך לא תקין שגורם לקריסה
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        return df
    except: return pd.DataFrame()

def clean_amount(val):
    try:
        if pd.isna(val): return 0.0
        clean_val = re.sub(r'[^\d.]', '', str(val))
        return float(clean_val) if clean_val else 0.0
    except: return 0.0

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
                    if missing:
                        st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        st.warning(f"Missing Files: {', '.join(missing)}")
                    if orphans:
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.error(f"Unrecognized Files: {', '.join(orphans)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. Go to Google Security\n2. Enable 2-Step Verification\n3. Create App Password for 'Mail'")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not up_ex or not user_mail:
            st.error("Missing details.")
        else:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                amount_col = next((c for c in df_master.columns if any(x in str(c).lower() for x in ['amount', 'סכום'])), None)
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                for i, row in df_master.iterrows():
                    company = str(row.iloc[0]).strip()
                    emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                    if emails and company_files:
                        msg = MIMEMultipart()
                        msg['Subject'] = f"Invoice - {company}"; msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText("Attached invoices.", 'plain'))
                        for f in company_files:
                            msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        server.send_message(msg)
                        supabase.table("billing_history").insert({
                            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "company": company, "amount": clean_amount(row[amount_col]) if amount_col else 0.0,
                            "status": "Sent", "currency": "$", "sender": user_mail,
                            "due_date": f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        }).execute()
                server.quit(); st.balloons(); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        # שליחה אחרונה
        st.info(f"🕒 **Last Email Sent on:** {df['date'].iloc[0]}")
        
        st.write("### 🛠 Filters")
        f1, f2 = st.columns(2)
        f_df = df.copy()
        
        sel_comp = f1.multiselect("Filter Companies", sorted(df['company'].unique()))
        if sel_comp: f_df = f_df[f_df['company'].isin(sel_comp)]
        
        # תיקון השגיאה: שימוש בערכי מחדל בטוחים
        min_date = df['date_obj'].min() if not df['date_obj'].empty else date.today()
        max_date = df['date_obj'].max() if not df['date_obj'].empty else date.today()
        
        date_range_dash = f2.date_input("Filter Dates", value=[min_date, max_date])
        if isinstance(date_range_dash, list) and len(date_range_dash) == 2:
            f_df = f_df[(f_df['date_obj'] >= date_range_dash[0]) & (f_df['date_obj'] <= date_range_dash[1])]

        st.divider()
        m1, m2, m3 = st.columns(3)
        total_billed = f_df['amount'].sum()
        total_paid = f_df[f_df['status'] == 'Paid']['amount'].sum()
        m1.metric("Total Billed", f"${total_billed:,.2f}")
        m2.metric("Total Received", f"${total_paid:,.2f}")
        m3.metric("Outstanding", f"${total_billed - total_paid:,.2f}")
        
        st.divider()
        st.write("**Revenue by Company**")
        p1 = f_df.groupby(['company', 'currency']).agg({'amount':'sum'}).reset_index()
        st.dataframe(p1, use_container_width=True, hide_index=True)
    else: st.info("No data in cloud.")

# --- PAGE 3: CONTROL ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        st.write("### 📅 Filter by Date Range")
        min_d = df['date_obj'].min() if not df['date_obj'].empty else date.today()
        max_d = df['date_obj'].max() if not df['date_obj'].empty else date.today()
        date_range = st.date_input("Select Range", value=[min_d, max_d])
        
        f_df = df.copy()
        if isinstance(date_range, list) and len(date_range) == 2:
            f_df = f_df[(f_df['date_obj'] >= date_range[0]) & (f_df['date_obj'] <= date_range[1])]

        sel_comp_ctrl = st.multiselect("Filter by Company", sorted(f_df['company'].unique()))
        if sel_comp_ctrl: f_df = f_df[f_df['company'].isin(sel_comp_ctrl)]

        def color_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white;'
            return ''

        display_cols = ['id', 'company', 'date', 'amount', 'status', 'notes']
        edited_df = st.data_editor(
            f_df[display_cols].style.map(color_status, subset=['status']),
            column_config={
                "id": None, "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"]),
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            },
            disabled=['company', 'date'], hide_index=True, use_container_width=True, key="ctrl_editor"
        )
        if st.button("💾 Save All Changes", use_container_width=True):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({
                    "status": row['status'], "notes": str(row.get('notes', '')), "amount": float(row['amount'])
                }).eq("id", row['id']).execute()
            st.success("Updated!"); time.sleep(0.5); st.rerun()
    else: st.info("No records.")
