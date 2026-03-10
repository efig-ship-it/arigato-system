import streamlit as st
import pandas as pd
import smtplib, time, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date
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
    else:
        st.sidebar.error("❌ Secrets Missing")
except Exception as e:
    st.sidebar.error("🚨 Cloud Connection Failed")
    st.sidebar.code(f"Error: {e}")

# --- 2. CSS & Design ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- 3. Functions ---
def get_cloud_history():
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        return pd.DataFrame(response.data)
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
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1, label_visibility="collapsed")
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1, label_visibility="collapsed")
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
                    if orphans:
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.error(f"Unrecognized Files: {', '.join(orphans)}")
                    if missing:
                        st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        st.warning(f"Missing Files for: {', '.join(missing)}")
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. Go to [Google Security](https://myaccount.google.com/security)\n2. Enable 2-Step Verification.\n3. Create 'App password' for 'Mail'.")

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    # כפתור שליחה עם הגנה מפני NoneType
    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if not up_ex:
            st.error("❌ Please upload the Mailing List (Excel) first!")
        elif not uploaded_files:
            st.error("❌ Please upload the Invoice files first!")
        elif not user_mail or not user_pass:
            st.error("❌ Missing Gmail Credentials.")
        elif supabase is None:
            st.error("❌ No Cloud Connection.")
        else:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                with st.spinner("Processing..."):
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        due_val = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        
                        if emails and company_files:
                            msg = MIMEMultipart()
                            msg['Subject'] = f"{user_subj} - {company}"
                            msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, invoices attached.", 'plain'))
                            for f in company_files:
                                part = MIMEApplication(f.getvalue(), Name=f.name); msg.attach(part)
                            server.send_message(msg)
                            
                            supabase.table("billing_history").insert({
                                "date": datetime.now().strftime("%d/%m/%Y"),
                                "company": company, "amount": 0.0, "status": "Sent",
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
        
        # פילטרים דינמיים
        if 'company' in df.columns:
            sel_comp = f1.multiselect("Companies", sorted(df['company'].unique()))
            if sel_comp: f_df = f_df[f_df['company'].isin(sel_comp)]
        if 'date' in df.columns:
            sel_date = f2.multiselect("Dates", sorted(df['date'].unique()))
            if sel_date: f_df = f_df[f_df['date'].isin(sel_date)]
        if 'status' in df.columns:
            sel_stat = f3.multiselect("Status", sorted(df['status'].unique()))
            if sel_stat: f_df = f_df[f_df['status'].isin(sel_stat)]

        st.divider()
        m1, m2 = st.columns(2)
        if 'amount' in f_df.columns:
            total_billed = f_df['amount'].sum()
            total_paid = f_df[f_df['status'] == 'Paid']['amount'].sum() if 'status' in f_df.columns else 0
            m1.metric("Total Billed", f"${total_billed:,.2f}")
            m2.metric("Total Paid", f"${total_paid:,.2f}")

        st.divider()
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.write("**Pivot: Company Revenue**")
            if {'company', 'amount'}.issubset(f_df.columns):
                p1 = f_df.groupby(['company', 'currency']).agg({'amount':'sum'}).reset_index()
                st.dataframe(p1, use_container_width=True, hide_index=True)
        with c_p2:
            st.write("**Pivot: Daily Revenue**")
            if {'date', 'amount'}.issubset(f_df.columns):
                p2 = f_df.groupby(['date', 'currency']).agg({'amount':'sum'}).reset_index()
                st.dataframe(p2, use_container_width=True, hide_index=True)
    else: st.info("No data in cloud.")

# --- PAGE 3: CONTROL ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        def color_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white;'
            return ''

        display_cols = [c for c in ['id', 'company', 'due_date', 'amount', 'currency', 'status', 'notes'] if c in df.columns]
        
        edited_df = st.data_editor(
            df[display_cols].style.map(color_status, subset=['status'] if 'status' in display_cols else []),
            column_config={
                "id": None, 
                "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"])
            },
            disabled=['company', 'due_date', 'amount', 'currency'],
            hide_index=True, use_container_width=True, key="ctrl_edt"
        )
        
        if st.button("💾 Save Changes", use_container_width=True):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({
                    "status": row['status'], 
                    "notes": str(row.get('notes', ''))
                }).eq("id", row['id']).execute()
            st.success("Cloud Updated!"); time.sleep(1); st.rerun()
