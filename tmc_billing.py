import streamlit as st
import pandas as pd
import smtplib, time, traceback, re, io
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
except Exception as e:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. CSS & Design ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- 3. Functions ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            # המרת תאריכים לאובייקט תאריך לצורך פילטר ה-Calendar
            df['date_obj'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce').dt.date
        return df
    except: return pd.DataFrame()

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
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, key="m_sel")
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1, key="y_sel")
        current_period = f"{sel_m} {sel_y}"

    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)

    allow_sending = True
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            comp_col = df_ex.columns[0]
            excel_comps = [str(c).strip() for c in df_ex[comp_col].dropna().unique()]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in f.name.lower() for f in uploaded_files)]
            
            if orphans or missing:
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if orphans: st.error(f"Unrecognized Files: {', '.join(orphans)}")
                    if missing: st.warning(f"Missing Files for: {', '.join(missing)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 App Password Info"):
            st.write("Create a 16-character code in Google Security settings.")

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not up_ex or not user_mail or not user_pass:
            st.error("Please fill all details and upload Excel.")
        else:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                # זיהוי עמודת הסכום (Amount)
                amount_col = next((c for c in df_master.columns if 'amount' in str(c).lower()), None)

                with st.spinner("Sending..."):
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        
                        # לקיחת סכום מהאקסל (אם קיים)
                        amount_val = row[amount_col] if amount_col else 0.0
                        due_val = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        
                        if emails and company_files:
                            msg = MIMEMultipart()
                            msg['Subject'] = f"{user_subj} - {company}"; msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, invoices attached.", 'plain'))
                            for f in company_files:
                                part = MIMEApplication(f.getvalue(), Name=f.name); msg.attach(part)
                            server.send_message(msg)
                            
                            supabase.table("billing_history").insert({
                                "date": datetime.now().strftime("%d/%m/%Y"),
                                "company": company, "amount": float(amount_val), "status": "Sent",
                                "due_date": due_val, "currency": "$", "sender": user_mail
                            }).execute()

                server.quit(); st.balloons(); st.success("Finished!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        st.write("### 🛠 Filters")
        f1, f2, f3 = st.columns(3)
        f_df = df.copy()
        if 'company' in df.columns:
            sel_comp = f1.multiselect("Companies", sorted(df['company'].unique()))
            if sel_comp: f_df = f_df[f_df['company'].isin(sel_comp)]
        if 'status' in df.columns:
            sel_stat = f3.multiselect("Status", sorted(df['status'].unique()))
            if sel_stat: f_df = f_df[f_df['status'].isin(sel_stat)]
        
        st.divider()
        m1, m2 = st.columns(2)
        total_billed = f_df['amount'].sum()
        total_paid = f_df[f_df['status'] == 'Paid']['amount'].sum()
        m1.metric("Total Billed", f"${total_billed:,.2f}")
        m2.metric("Total Paid", f"${total_paid:,.2f}")
        
        st.divider()
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.write("**Pivot: Company Revenue**")
            p1 = f_df.groupby(['company', 'currency']).agg({'amount':'sum'}).reset_index()
            st.dataframe(p1, use_container_width=True, hide_index=True)
        with c_p2:
            st.write("**Pivot: Daily Revenue**")
            p2 = f_df.groupby(['date', 'currency']).agg({'amount':'sum'}).reset_index()
            st.dataframe(p2, use_container_width=True, hide_index=True)
    else: st.info("No data.")

# --- PAGE 3: CONTROL (עם פילטר CALENDAR) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    
    if not df.empty:
        # פילטר לוח שנה (Calendar)
        st.write("### 📅 Date Range Filter")
        date_range = st.date_input("Select Range", 
                                  value=[df['date_obj'].min(), df['date_obj'].max()],
                                  key="calendar_filter")
        
        f_df = df.copy()
        if isinstance(date_range, list) and len(date_range) == 2:
            f_df = f_df[(f_df['date_obj'] >= date_range[0]) & (f_df['date_obj'] <= date_range[1])]

        def color_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white;'
            return ''

        display_cols = ['id', 'company', 'date', 'due_date', 'amount', 'currency', 'status', 'notes']
        
        edited_df = st.data_editor(
            f_df[display_cols].style.map(color_status, subset=['status']),
            column_config={
                "id": None, 
                "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"]),
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            },
            disabled=['company', 'date', 'due_date', 'currency'],
            hide_index=True, use_container_width=True, key="ctrl_edt_main"
        )
        
        if st.button("💾 Save Changes", use_container_width=True):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({
                    "status": row['status'], 
                    "notes": str(row.get('notes', '')),
                    "amount": float(row['amount']) # מאפשר לעדכן סכום ידנית במידה וחסר
                }).eq("id", row['id']).execute()
            st.success("Cloud Updated!"); time.sleep(0.5); st.rerun()
    else: st.info("No records found.")
