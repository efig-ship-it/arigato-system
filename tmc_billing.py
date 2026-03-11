import streamlit as st
import pandas as pd
import smtplib, time, re, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection (🛡️ סעיף 1 בחוזה) ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. UI CSS (🎨 Nuvei Soft Style + Tuesday Header) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .main { background-color: #f4f7f9; }
    div[data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 700 !important; }
    div[data-testid="stMetricLabel"] { font-size: 12px !important; }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e1e8ed; padding: 10px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    h1 { color: #1a202c; font-weight: 800; margin-bottom: 20px; }
    .alert-box { border-right: 6px solid #003366; margin-bottom: 25px; padding: 15px; background: white; border-radius: 10px; border: 1px solid #e1e8ed; }
    .risk-box { border: 2px solid #e53e3e; background-color: #fff5f5; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    .log-box { background-color: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #e0e4e8; border-right: 4px solid #003366; margin-bottom: 8px; font-size: 13px; direction: rtl; }
    .success-msg { font-size: 80px; font-weight: 900; color: #28a745; text-align: center; margin-top: 10px; display: block; }
    .suitcase-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 20px 0; text-align: center; }
    .big-detective { font-size: 350px; text-align: center; margin: 20px 0; display: block; }
    .tuesday-header { font-size: 28px; font-weight: 900; color: #003366; margin-bottom: 10px; padding-left: 5px; }
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
            def extract_days(note, sent_date):
                match = re.search(r'Paid on (\d{2}/\d{2}/\d{2})', str(note))
                if match and not pd.isna(sent_date):
                    try:
                        p_dt = pd.to_datetime(match.group(1), format='%d/%m/%y')
                        return (p_dt - sent_date).days
                    except: return None
                return None
            df['days_to_pay'] = df.apply(lambda r: extract_days(r['notes'], r['date_sent_dt']), axis=1)
        return df
    except: return pd.DataFrame()

def clean_amount(val):
    if pd.isna(val) or val == "": return 0.0
    try:
        clean_val = re.sub(r'[^\d.]', '', str(val))
        return float(clean_val) if clean_val else 0.0
    except: return 0.0

def extract_total_amount_from_file(uploaded_file):
    try:
        temp_df = pd.read_excel(uploaded_file)
        temp_df.columns = [str(c).lower().strip() for c in temp_df.columns]
        if 'amount' in temp_df.columns:
            amounts = pd.to_numeric(temp_df['amount'].apply(clean_amount), errors='coerce').fillna(0.0)
            return float(amounts.sum())
    except: pass
    return 0.0

def add_log_entry(item_id, entry_text):
    current_time = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%y %H:%M")
    new_entry = f"[{current_time}] {entry_text}"
    res = supabase.table("billing_history").select("notes").eq("id", item_id).execute()
    old_notes = res.data[0]['notes'] if res.data and res.data[0]['notes'] else ""
    updated = f"{old_notes}\n{new_entry}".strip() if old_notes else new_entry
    supabase.table("billing_history").update({"notes": updated}).eq("id", item_id).execute()

# --- 4. Sidebar & Navigation ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)
page = st.sidebar.radio("Navigation", ["Email Sender 📧", "Analytics Dashboard 📊", "Collections Control 🔍", "Reminders Manager 🚨"])

# --- PAGE 1: EMAIL SENDER (עם Risk Control חודש) ---
if page == "Email Sender 📧":
    st.title("Invoicing Center")
    col_up, col_due = st.columns([2, 1])
    with col_up: up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_due:
        st.markdown('<p style="font-weight:700; color:#4a5568;">SET DUE DATE</p>', unsafe_allow_html=True)
        mc, yc = st.columns(2); months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1); sel_y = yc.selectbox("Year", ["2025", "2026", "2027"], index=1)
    
    uploaded_files = st.file_uploader("Drop Company Invoices Here", accept_multiple_files=True)
    
    confirm_dispatch = False
    if up_ex:
        df_history = get_cloud_history()
        try:
            df_ex = pd.read_excel(up_ex)
            current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            
            # Risk Control חודש
            today = date.today()
            risk_threshold = today - timedelta(days=30)
            bad_debtors = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
            name_issue = "emails" not in up_ex.name.lower()

            if not bad_debtors.empty or missing or name_issue:
                if not bad_debtors.empty:
                    st.markdown('<div class="risk-box">⚠️ <b>Credit Risk Alert:</b> חברות אלו חייבות כסף מעל חודש:</div>', unsafe_allow_html=True)
                    for _, row in bad_debtors.drop_duplicates('company').iterrows():
                        st.error(f"● {row['company']} owes ${row['balance']:,.2f} since {row['due_date']}")

                confirm_dispatch = st.checkbox("🚨 אני מאשר שהנתונים והסיכונים נבדקו (הסתר אזהרות)", value=False)
                if not confirm_dispatch:
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if name_issue: st.error("הבלש מזהה: שם הקובץ אינו מכיל 'Emails'.")
                    if missing: st.warning(f"הבלש מזהה חוסרים עבור: {', '.join(missing)}")
            else: confirm_dispatch = True
        except: confirm_dispatch = True

    st.write("---")
    with st.expander("💡 How to get App Password"):
        st.markdown("1. [Google App Passwords](https://myaccount.google.com/apppasswords)\n2. Enable 2FA\n3. Create 'Tuesday' password.")
    
    sc1, sc2 = st.columns(2); user_mail = sc1.text_input("Gmail Account"); user_pass = sc2.text_input("App Password", type="password")

    if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (confirm_dispatch and up_ex and uploaded_files)):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(user_mail.strip(), user_pass.strip())
            with st.spinner("Dispatching..."):
                placeholder = st.empty()
                placeholder.markdown("""<div class="suitcase-container"><svg width="100" height="100" viewBox="0 0 24 24" fill="#8B4513"><path d="M17,6H16V5c0-1.1-0.9-2-2-2h-4C8.9,3,8,3.9,8,5v1H7C5.9,6,5,6.9,5,8v11c0,1.1,0.9,2,2,2h10c1.1,0,2-0.9,2-2V8 C19,6.9,18.1,6,17,6z M10,5h4v1h-4V5z M17,19H7V8h10V19z"/></svg></div>""", unsafe_allow_html=True)
                for i, row in df_master.iterrows():
                    comp, mail = str(row.iloc[0]).strip(), [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    amt = sum([extract_total_amount_from_file(f) for f in files])
                    if mail and files:
                        msg = MIMEMultipart(); msg['Subject'] = f"Invoice - {comp}"; msg['To'] = ", ".join(mail)
                        msg.attach(MIMEText(f"Dear {comp}, find invoices attached.", 'plain'))
                        for f in files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        server.send_message(msg)
                        it, dv = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M"), f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        supabase.table("billing_history").insert({"date": it, "company": comp, "amount": amt, "status": "Sent", "due_date": dv, "sender": user_mail, "received_amount": 0}).execute()
                server.quit(); placeholder.empty(); st.balloons(); st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True); time.sleep(3); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS ---
elif page == "Analytics Dashboard 📊":
    st.title("Financial Overview")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        today = date.today()
        m1, m2, m3, m4 = st.columns(4)
        tb, tr = df_raw['amount'].sum(), df_raw['received_amount'].sum()
        m1.metric("Billed", f"${tb:,.0f}"); m2.metric("Received", f"${tr:,.0f}"); m3.metric("Outstanding", f"${tb-tr:,.0f}"); m4.metric("Reminded", f"${df_raw[df_raw['status'] == 'Sent Reminder']['balance'].sum():,.0f}")
        st.dataframe(df_raw.pivot_table(index='company', columns='status', values='amount', aggfunc='sum', fill_value=0).style.format("${:,.0f}"), use_container_width=True)

# --- PAGE 3: CONTROL (🔍 הוחזר ה-Multi-Edit) ---
elif page == "Collections Control 🔍":
    st.title("Operations Control")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        cf1, cf2 = st.columns(2)
        c_sel = cf1.multiselect("Companies", sorted(df_raw['company'].unique()))
        c_due = cf2.date_input("Due Date", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
        f_df = df_raw.copy()
        if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
        if isinstance(c_due, tuple) and len(c_due) == 2: f_df = f_df[(f_df['due_date_obj'] >= c_due[0]) & (f_df['due_date_obj'] <= c_due[1])]
        
        def highlight_st(val):
            if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
            if val == 'Overdue': return 'background-color: #fff5f5; color: #822727; font-weight: bold;'
            if val == 'Sent Reminder': return 'background-color: #fefcbf; color: #744210; font-weight: bold;'
            return ''
        
        st.dataframe(f_df[['id', 'company', 'due_date', 'amount', 'received_amount', 'status']].style.applymap(highlight_st, subset=['status']).format({"amount": "{:,.2f}", "received_amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
        
        st.divider(); st.subheader("Audit & Documentation")
        f_df_sorted = f_df.sort_values(by=['due_date_obj', 'company'])
        options = f_df_sorted.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.2f})", axis=1).tolist()
        option_to_id = dict(zip(options, f_df_sorted['id'].tolist()))
        sel_label = st.selectbox("Record:", options)
        if sel_label:
            sid = option_to_id[sel_label]; row_data = df_raw[df_raw['id'] == sid].iloc[0]
            if str(row_data['notes']) and str(row_data['notes']) != 'None':
                for line in str(row_data['notes']).split('\n'):
                    if line.strip(): st.markdown(f"<div class='log-box'>{line}</div>", unsafe_allow_html=True)
            c_i1, c_i2, c_i3 = st.columns([2, 1, 1])
            with c_i1: entry = st.text_input("Note Entry:")
            with c_i2: rec_amt = st.number_input("Received ($):", value=float(row_data['received_amount']), key=f"ind_{sid}")
            with c_i3: nst = st.selectbox("Status:", ["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"], index=["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"].index(row_data['status']), key=f"st_{sid}")
            if st.button("Save Update"):
                if entry: add_log_entry(sid, entry)
                f_st = "Paid" if rec_amt >= row_data['amount'] else nst
                supabase.table("billing_history").update({"status": f_st, "received_amount": float(rec_amt)}).eq("id", sid).execute()
                add_log_entry(sid, f"Update: {f_st} | ${rec_amt:,.2f}")
                st.success("Saved."); time.sleep(0.5); st.rerun()

        st.divider(); st.subheader("⚡ Batch Execute Launch (Multi-Edit)")
        bulk_prep = f_df_sorted[['id', 'company', 'due_date', 'amount', 'received_amount']].copy()
        bulk_prep['Select'] = False
        selected_bulk = st.data_editor(bulk_prep[['Select', 'company', 'due_date', 'amount', 'received_amount', 'id']], column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None, "amount": st.column_config.NumberColumn("Bill", disabled=True, format="%.2f"), "received_amount": st.column_config.NumberColumn("Pay", format="%.2f")}, disabled=['company', 'due_date', 'amount'], hide_index=True, use_container_width=True)
        if st.button("🚀 Batch Execute Launch", use_container_width=True):
            to_launch = selected_bulk[selected_bulk['Select'] == True]
            if not to_launch.empty:
                for i, row in to_launch.iterrows():
                    orig, cur = float(row['amount']), float(row['received_amount'])
                    f_rec = cur if cur > 0 else orig
                    f_st = "Paid" if f_rec >= orig else "Sent"
                    supabase.table("billing_history").update({"status": f_st, "received_amount": f_rec}).eq("id", row['id']).execute()
                    add_log_entry(row['id'], f"Batch Update: {f_st} | ${f_rec:,.2f}")
                st.success("Bulk update successful."); time.sleep(1); st.rerun()

# --- PAGE 4: REMINDERS MANAGER ---
elif page == "Reminders Manager 🚨":
    st.title("Reminders Manager")
    mail_file = st.file_uploader("Upload Emails", type=['xlsx'])
    df_raw = get_cloud_history()
    if not df_raw.empty:
        df_raw['balance'] = df_raw['amount'] - df_raw['received_amount']
        unpaid_df = df_raw[df_raw['balance'] > 0].copy()
        if unpaid_df.empty: st.success("All paid!")
        else:
            unpaid_df['Select'] = False
            sel_disp = st.data_editor(unpaid_df[['Select', 'company', 'due_date', 'amount', 'received_amount', 'balance', 'id']], column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None}, disabled=['company', 'due_date', 'amount', 'received_amount', 'balance'], hide_index=True, use_container_width=True)
            d_sc1, d_sc2 = st.columns(2); d_mail = d_sc1.text_input("Gmail"); d_pass = d_sc2.text_input("Pass", type="password")
            if st.button("🚀 Send Alerts"):
                to_send = sel_disp[sel_disp['Select'] == True]
                if not to_send.empty and mail_file:
                    try:
                        email_map = pd.read_excel(mail_file)
                        email_dict = dict(zip(email_map.iloc[:, 0].str.strip().str.lower(), email_map.iloc[:, 1].str.strip()))
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(d_mail.strip(), d_pass.strip())
                        for i, row in to_send.iterrows():
                            target = email_dict.get(str(row['company']).strip().lower())
                            if target:
                                msg = MIMEMultipart(); msg['Subject'] = f"Reminder - {row['company']}"; msg['To'] = target
                                msg.attach(MIMEText(f"תביאו את הכסף.\nיתרה: ${row['balance']:,.2f}", 'plain'))
                                server.send_message(msg)
                                add_log_entry(row['id'], f"🚨 Sent to {target}")
                                supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                        server.quit(); st.balloons(); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
