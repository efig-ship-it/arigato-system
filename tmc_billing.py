import streamlit as st
import pandas as pd
import smtplib, time, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date
from supabase import create_client, Client

# --- 1. Supabase Connection ---
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    else:
        st.warning("⚠️ Supabase Secrets are missing in Streamlit Settings.")
except Exception as e:
    st.error(f"🚨 Connection Error: {e}")

# --- 2. Page Config & CSS (The Original Design) ---
st.set_page_config(page_title="TMC Billing System PRO", layout="centered")

st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- 3. Functions ---
def get_cloud_history():
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty and 'Date' in df.columns:
            df['Date_obj'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        return df
    except:
        return pd.DataFrame()

def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- 4. Navigation ---
st.sidebar.title("📌 Navigation")
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
            file_names = [f.name.lower() for f in uploaded_files]
            orphans = [f.name for f in uploaded_files if not any(c.lower() in f.name.lower() for c in excel_comps)]
            missing = [c for c in excel_comps if not any(c.lower() in fname for fname in file_names)]
            
            if orphans or missing:
                confirm = st.toggle("🚨 I confirm all is correct", value=False)
                allow_sending = confirm
                if not confirm:
                    if 'sound_triggered' not in st.session_state:
                        sound_detective(); st.session_state.sound_triggered = True
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if orphans: 
                        st.markdown('<p class="detective-header">Detective Alert!</p>', unsafe_allow_html=True)
                        st.error(f"Unrecognized files: {', '.join(orphans)}")
                    if missing: 
                        st.markdown('<p class="reverse-detective-header">Reverse Detective!</p>', unsafe_allow_html=True)
                        st.warning(f"Missing files for: {', '.join(missing)}")
                else:
                    if 'sound_triggered' in st.session_state: del st.session_state.sound_triggered
        except: pass

    st.write("---")
    st.subheader("2. Sender Details")
    sc1, sc2, sc3 = st.columns([1.2, 1.2, 1.4])
    user_mail = sc1.text_input("Gmail Address")
    user_pass = sc2.text_input("App Password", type="password")
    with sc3:
        with st.expander("🔑 How to create an App Password?"):
            st.markdown("1. Go to [Google Security](https://myaccount.google.com/security)\n2. Enable 2-Step Verification.\n3. Create 'App password' (16 chars).")

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                with st.spinner("Processing emails and saving to cloud..."):
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        due_date_val = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        
                        total_amount = 0.0
                        cur = "$"
                        for f in company_files:
                            if f.name.endswith('.xlsx'):
                                df_temp = pd.read_excel(io.BytesIO(f.getvalue()))
                                amt_col = next((c for c in df_temp.columns if 'amount' in str(c).lower()), None)
                                if amt_col:
                                    sample_val = str(df_temp[amt_col].iloc[0])
                                    if '₪' in sample_val: cur = '₪'
                                    elif '€' in sample_val: cur = '€'
                                    df_temp[amt_col] = pd.to_numeric(df_temp[amt_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
                                    total_amount += df_temp[amt_col].sum()

                        if emails and company_files:
                            # 1. Send Gmail
                            msg = MIMEMultipart()
                            msg['Subject'] = f"{user_subj} - {company}"
                            msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company}, invoices attached.\nTotal: {cur}{total_amount:,.2f}", 'plain'))
                            for f in company_files:
                                part = MIMEApplication(f.getvalue(), Name=f.name)
                                part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                                msg.attach(part)
                            server.send_message(msg)
                            
                            # 2. Save to Supabase (Exact Column Names)
                            supabase.table("billing_history").insert({
                                "Date": datetime.now().strftime("%d/%m/%Y"),
                                "Company": company,
                                "Amount": float(total_amount),
                                "Status": "Sent",
                                "Due_Date": due_date_val,
                                "Currency": cur,
                                "Sender": user_mail
                            }).execute()
                
                server.quit(); sound_success(); st.balloons(); st.success("All sent and saved!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"❌ Error: {e}")

# --- PAGE 2: ANALYTICS DASHBOARD ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        c1, c2 = st.columns(2)
        sel_comp = c1.multiselect("Filter by Company", options=sorted(df['Company'].unique()))
        sel_range = c2.date_input("Filter by Date", value=[df['Date_obj'].min().date(), df['Date_obj'].max().date()])
        
        f_df = df.copy()
        if sel_comp: f_df = f_df[f_df['Company'].isin(sel_comp)]
        if len(sel_range) == 2:
            f_df = f_df[(f_df['Date_obj'].dt.date >= sel_range[0]) & (f_df['Date_obj'].dt.date <= sel_range[1])]

        m1, m2, m3 = st.columns(3)
        total_billed = f_df['Amount'].sum()
        total_paid = f_df[f_df['Status'] == 'Paid']['Amount'].sum()
        m1.metric("Total Billed", f"${total_billed:,.2f}")
        m2.metric("Total Collected", f"${total_paid:,.2f}")
        m3.metric("Outstanding", f"${total_billed - total_paid:,.2f}")
        
        st.divider()
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.write("**Pivot by Company**")
            p1 = f_df.groupby(['Company', 'Currency']).agg({'Amount':'sum'}).reset_index()
            st.dataframe(p1, use_container_width=True, hide_index=True)
        with col_p2:
            st.write("**Pivot by Date**")
            p2 = f_df.groupby(['Date', 'Currency']).agg({'Amount':'sum'}).reset_index()
            st.dataframe(p2, use_container_width=True, hide_index=True)
    else: st.info("No records in cloud.")

# --- PAGE 3: COLLECTIONS CONTROL ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections & Control")
    df = get_cloud_history()
    if not df.empty:
        def color_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white; font-weight: bold;'
            return ''

        edited_df = st.data_editor(
            df[['id', 'Company', 'Due_Date', 'Amount', 'Currency', 'Status', 'Notes']].style.map(color_status, subset=['Status']),
            column_config={
                "id": None, 
                "Status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"]),
            },
            disabled=["Company", "Due_Date", "Amount", "Currency"],
            hide_index=True, use_container_width=True, key="control_editor"
        )
        if st.button("💾 Save All Changes", use_container_width=True):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({"Status": row['Status'], "Notes": str(row['Notes'])}).eq("id", row['id']).execute()
            st.success("Cloud Updated!"); time.sleep(1); st.rerun()
    else: st.info("No data.")
