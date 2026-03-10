import streamlit as st
import pandas as pd
import smtplib, time, traceback, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, date
from supabase import create_client, Client

# --- Supabase Connection ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("🚨 Missing Supabase Secrets in Streamlit Settings!")

# --- Page Config ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")

# --- Database Fetch Function ---
def get_cloud_history():
    try:
        response = supabase.table("billing_history").select("*").order("id", desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            # נירמול שמות עמודות לאותיות קטנות כדי למנוע שגיאות תצוגה
            df.columns = [c.lower() for c in df.columns]
            if 'date' in df.columns:
                df['date_obj'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame()

# --- Audio System ---
def play_audio(url):
    st.components.v1.html(f"<script>new Audio('{url}').play();</script>", height=0)

def sound_success(): play_audio("https://www.myinstants.com/media/sounds/trumpet-success.mp3")
def sound_detective(): play_audio("https://www.myinstants.com/media/sounds/spongebob-squarepants-sad-violin_5.mp3")

# --- CSS Design ---
st.markdown("""<style>
    .due-date-container { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 100%; margin-bottom: 5px; }
    .due-date-label { font-size: 14px; font-weight: bold; color: #31333F; margin-bottom: 2px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .detective-header { font-size: 80px; font-weight: 900; color: #d32f2f; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
    .reverse-detective-header { font-size: 80px; font-weight: 900; color: #f57c00; text-align: center; text-transform: uppercase; margin-bottom: 10px; }
</style>""", unsafe_allow_html=True)

# --- Sidebar Navigation ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- Page 1: Email Sender ---
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
                if not confirm:
                    allow_sending = False
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
            st.markdown("1. Go to [Google Security](https://myaccount.google.com/security)\n2. Enable 2-Step Verification.\n3. Create 'App password' for 'Mail'.")

    user_subj = st.text_input("Email Subject", value=f"Invoice Payment Due - {current_period}")

    if st.button("🚀 Start Bulk Sending", use_container_width=True, disabled=not allow_sending):
        if up_ex and uploaded_files and user_mail:
            try:
                df_master = pd.read_excel(up_ex).dropna(how='all')
                server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
                
                with st.spinner("Processing emails..."):
                    for i, row in df_master.iterrows():
                        company = str(row.iloc[0]).strip()
                        emails = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        company_files = [f for f in uploaded_files if company.lower() in f.name.lower()]
                        
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
                            msg = MIMEMultipart()
                            msg['Subject'] = f"{user_subj} - {company}"
                            msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Hello {company},\nTotal: {cur}{total_amount:,.2f}", 'plain'))
                            for f in company_files:
                                part = MIMEApplication(f.getvalue(), Name=f.name)
                                part['Content-Disposition'] = f'attachment; filename="{f.name}"'
                                msg.attach(part)
                            server.send_message(msg)
                            
                            # שמירה לענן (אותיות קטנות למניעת שגיאות ב-Supabase)
                            supabase.table("billing_history").insert({
                                "date": datetime.now().strftime("%d/%m/%Y"),
                                "company": company,
                                "amount": float(total_amount),
                                "status": "Sent",
                                "due_date": f"{sel_y}-{months.index(sel_m)+1:02d}-15",
                                "currency": cur,
                                "sender": user_mail
                            }).execute()
                
                server.quit(); sound_success(); st.balloons(); st.success("Success!"); time.sleep(1); st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- Page 2: Analytics Dashboard ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        sel_comp = st.multiselect("Filter by Company", options=sorted(df['company'].unique()))
        f_df = df[df['company'].isin(sel_comp)] if sel_comp else df
        
        m1, m2 = st.columns(2)
        m1.metric("Total Billed", f"{f_df['amount'].sum():,.2f}")
        m2.metric("Total Records", len(f_df))
        st.divider()
        st.dataframe(f_df[['date', 'company', 'amount', 'currency', 'status']], use_container_width=True, hide_index=True)
    else: st.info("No data yet.")

# --- Page 3: Collections Control ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections & Control")
    df = get_cloud_history()
    if not df.empty:
        def color_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white;'
            return ''

        edited_df = st.data_editor(
            df[['id', 'company', 'due_date', 'amount', 'currency', 'status', 'notes']].style.map(color_status, subset=['status']),
            column_config={
                "id": None, 
                "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute"]),
            },
            disabled=["company", "due_date", "amount"],
            hide_index=True, use_container_width=True, key="control_editor"
        )
        if st.button("💾 Save All Changes", use_container_width=True):
            for _, row in edited_df.iterrows():
                supabase.table("billing_history").update({"status": row['status'], "notes": str(row['notes'])}).eq("id", row['id']).execute()
            st.success("Cloud Updated!"); st.rerun()
    else: st.info("No data.")
