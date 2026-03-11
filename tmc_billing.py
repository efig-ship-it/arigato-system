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

# --- 2. CSS & Design (🎨 סעיף 7 - הכל כולל הגדלת תיבות התראה) ---
st.set_page_config(page_title="TMC Billing PRO", layout="centered")
st.markdown("""<style>
    .main { padding-top: 0rem; }
    .due-date-container { display: flex; flex-direction: column; align-items: center; margin-bottom: 5px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; display: block; } 
    .success-msg { font-size: 100px; font-weight: 900; color: #28a745; text-align: center; margin-top: 20px; }
    .suitcase-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 20px 0; }
    div[data-testid="metric-container"] { padding: 15px; border: 1px solid #f0f2f6; border-radius: 10px; background-color: #ffffff; }
    .alert-box { padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .alert-box h2 { font-size: 36px; margin: 0; }
    .alert-box p { font-size: 16px; margin: 0; font-weight: bold; }
    .log-box { background-color: #f9f9f9; padding: 10px; border-radius: 5px; border-right: 3px solid #003366; margin-top: 5px; font-size: 12px; direction: rtl; }
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
            df['month_sent'] = df['date_sent_dt'].dt.strftime('%b %Y')
            
            def extract_days(note, sent_date):
                match = re.search(r'Paid on (\d{2}/\d{2}/\d{2})', str(note))
                if match and not pd.isna(sent_date):
                    try:
                        paid_dt = pd.to_datetime(match.group(1), format='%d/%m/%y')
                        return (paid_dt - sent_date).days
                    except: return None
                return None
            df['days_to_pay'] = df.apply(lambda r: extract_days(r['notes'], r['date_sent_dt']), axis=1)
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

# --- 4. Navigation ---
page = st.sidebar.radio("Go to:", ["Email Sender", "Analytics Dashboard", "Collections Control 🔍"])

# --- PAGE 1: EMAIL SENDER ---
if page == "Email Sender":
    st.title("TMC Billing System")
    c1, c2 = st.columns([2, 1])
    with c1: up_ex = st.file_uploader("Mailing List (Excel)", type=['xlsx'])
    with c2:
        st.markdown('<div class="due-date-container"><p style="font-weight:bold;margin:0;">Due Date</p></div>', unsafe_allow_html=True)
        mc, yc = st.columns(2)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Mo", months, index=datetime.now().month - 1)
        sel_y = yc.selectbox("Yr", ["2025", "2026", "2027"], index=1)
    
    uploaded_files = st.file_uploader("Upload Company Invoices", accept_multiple_files=True)
    if up_ex and uploaded_files:
        try:
            df_ex = pd.read_excel(up_ex)
            excel_comps = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            file_names = [f.name for f in uploaded_files]
            missing = [c for c in excel_comps if not any(c.lower() in fn.lower() for fn in file_names)]
            orphans = [fn for fn in file_names if not any(c.lower() in fn.lower() for c in excel_comps)]
            if missing or orphans:
                if not st.toggle("🚨 I confirm all is correct", value=False):
                    st.markdown('<p class="big-detective">🕵️‍♂️</p>', unsafe_allow_html=True)
                    if missing: st.warning(f"Missing Files: {', '.join(missing)}")
                    if orphans: st.error(f"Unrecognized Files: {', '.join(orphans)}")
        except: pass

    st.write("---")
    sc1, sc2 = st.columns(2); user_mail = sc1.text_input("Gmail Address"); user_pass = sc2.text_input("App Password", type="password")

    if st.button("🚀 Start Bulk Sending", use_container_width=True):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
            server.login(user_mail.strip(), user_pass.strip().replace(" ", ""))
            with st.spinner(""):
                st.markdown("""<div class="suitcase-container"><svg width="50" height="50" viewBox="0 0 24 24" fill="#8B4513"><path d="M17,6H16V5c0-1.1-0.9-2-2-2h-4C8.9,3,8,3.9,8,5v1H7C5.9,6,5,6.9,5,8v11c0,1.1,0.9,2,2,2h10c1.1,0,2-0.9,2-2V8 C19,6.9,18.1,6,17,6z M10,5h4v1h-4V5z M17,19H7V8h10V19z"/></svg></div>""", unsafe_allow_html=True)
                for i, row in df_master.iterrows():
                    comp = str(row.iloc[0]).strip(); mail = [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    amt = sum([extract_total_amount_from_file(f) for f in files])
                    if mail and files:
                        msg = MIMEMultipart(); msg['Subject'] = f"Invoice - {comp}"; msg['To'] = ", ".join(mail)
                        msg.attach(MIMEText(f"Hello {comp}, invoices attached.", 'plain'))
                        for f in files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        server.send_message(msg)
                        it = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M")
                        dv = f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        supabase.table("billing_history").insert({"date": it, "company": comp, "amount": amt, "status": "Sent", "due_date": dv, "sender": user_mail, "received_amount": 0}).execute()
            server.quit(); st.balloons(); st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True); time.sleep(2); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS (📊 פיבוטים מלאים + פילטרים + תיבות גדולות) ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        today = date.today()
        risk = df[(df['status'] != 'Paid') & (df['due_date_obj'] < today - timedelta(days=7))]['amount'].sum()
        forecast = df[(df['status'] != 'Paid') & (df['due_date_obj'] >= today) & (df['due_date_obj'] <= today + timedelta(days=7))]['amount'].sum()
        
        st.write("### 🚨 התראות מנהל")
        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="alert-box" style="background-color: #ffebee; border-right: 8px solid #d32f2f;"><p style="color: #d32f2f;">🚩 HIGH RISK (OVERDUE > 7D)</p><h2>${risk:,.2f}</h2></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="alert-box" style="background-color: #e8f5e9; border-right: 8px solid #2e7d32;"><p style="color: #2e7d32;">💰 FORECAST (NEXT 7D)</p><h2>${forecast:,.2f}</h2></div>', unsafe_allow_html=True)

        st.divider()
        f1, f2, f3 = st.columns(3)
        sel_comps = f1.multiselect("Companies", sorted(df['company'].unique()))
        send_range = f2.date_input("Send Range", value=(df['date_sent_obj'].min(), df['date_sent_obj'].max()))
        due_range = f3.date_input("Due Range", value=(df['due_date_obj'].min(), df['due_date_obj'].max()))
        
        df_filt = df.copy()
        if sel_comps: df_filt = df_filt[df_filt['company'].isin(sel_comps)]
        if isinstance(send_range, tuple) and len(send_range) == 2: df_filt = df_filt[(df_filt['date_sent_obj'] >= send_range[0]) & (df_filt['date_sent_obj'] <= send_range[1])]
        if isinstance(due_range, tuple) and len(due_range) == 2: df_filt = df_filt[(df_filt['due_date_obj'] >= due_range[0]) & (df_filt['due_date_obj'] <= due_range[1])]

        m1, m2, m3 = st.columns(3)
        tb, tr = df_filt['amount'].sum(), df_filt['received_amount'].sum()
        m1.metric("Total Billed", f"${tb:,.2f}")
        m2.metric("Received", f"${tr:,.2f}")
        m3.metric("Outstanding", f"${tb-tr:,.2f}")
        
        st.divider()
        st.write("### 🧮 Data Pivots")
        p1, p2 = st.columns(2)
        with p1:
            st.write("**Sent vs. Paid (by Company)**")
            pivot_comp = df_filt.pivot_table(index=['company'], columns='status', values='amount', aggfunc='sum', fill_value=0)
            st.dataframe(pivot_comp.style.format("${:,.2f}"), use_container_width=True)
        with p2:
            st.write("**Payment Performance (Avg. Days)**")
            speed_df = df_filt[df_filt['days_to_pay'].notna()]
            if not speed_df.empty:
                avg_speed = speed_df.groupby('company')['days_to_pay'].mean().reset_index()
                st.dataframe(avg_speed.style.format({"days_to_pay": "{:.1f} Days"}), use_container_width=True, hide_index=True)

        st.write("### 📅 Monthly Summary")
        pivot_month = df_filt.pivot_table(index='month_sent', values='amount', aggfunc='sum')
        st.dataframe(pivot_month.style.format("${:,.2f}"), use_container_width=True)

        st.write("### 📉 Billed vs. Received")
        chart_billed = df_filt.groupby('due_date_obj')['amount'].sum().reset_index(); chart_billed['Type'] = 'Billed'
        chart_paid = df_filt.groupby('due_date_obj')['received_amount'].sum().reset_index(); chart_paid['Type'] = 'Received'
        st.vega_lite_chart(pd.concat([chart_billed, chart_paid]), {
            'mark': {'type': 'bar', 'width': 18, 'cornerRadiusTopLeft': 2, 'cornerRadiusTopRight': 2},
            'encoding': {
                'x': {'field': 'due_date_obj', 'type': 'nominal', 'title': 'Due Date'},
                'y': {'field': 'amount', 'type': 'quantitative'},
                'xOffset': {'field': 'Type'},
                'color': {'field': 'Type', 'type': 'nominal', 'scale': {'range': ['#003366', '#87CEEB']}}
            }
        }, use_container_width=True)
    else: st.info("No data.")

# --- PAGE 3: CONTROL (🔍 צבעים בטבלה חזרו + פילטרים + מולטי) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        cf1, cf2, cf3 = st.columns(3)
        c_sel = cf1.multiselect("Filter Companies", sorted(df_raw['company'].unique()))
        c_send = cf2.date_input("Filter Send Date", value=(df_raw['date_sent_obj'].min(), df_raw['date_sent_obj'].max()))
        c_due = cf3.date_input("Filter Due Date", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
        
        f_df = df_raw.copy()
        if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
        if isinstance(c_send, tuple) and len(c_send) == 2: f_df = f_df[(f_df['date_sent_obj'] >= c_send[0]) & (f_df['date_sent_obj'] <= c_send[1])]
        if isinstance(c_due, tuple) and len(c_due, tuple) == 2: f_df = f_df[(f_df['due_date_obj'] >= c_due[0]) & (f_df['due_date_obj'] <= c_due[1])]

        edit_mode = st.toggle("✏️ Edit Mode", value=False)
        display_cols = ['id', 'company', 'date', 'due_date', 'amount', 'received_amount', 'status', 'notes']
        
        def highlight_status(val):
            if val == 'Paid': return 'background-color: #28a745; color: white;'
            if val == 'Overdue': return 'background-color: #d32f2f; color: white;'
            return ''

        with st.expander("📋 Billing Records", expanded=True):
            if not edit_mode:
                st.dataframe(f_df[display_cols].style.map(highlight_status, subset=['status']).format({"amount": "{:,.2f}", "received_amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
            else:
                edited = st.data_editor(f_df[display_cols], column_config={
                    "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "In Dispute", "Overdue"]),
                    "received_amount": st.column_config.NumberColumn("Received", format="%.2f")
                }, disabled=['company', 'date', 'due_date'], hide_index=True, use_container_width=True)
                if st.button("💾 Save Table Changes"):
                    for i, row in edited.iterrows():
                        supabase.table("billing_history").update({"status": row['status'], "received_amount": float(row['received_amount'])}).eq("id", row['id']).execute()
                    st.success("Updated!"); st.rerun()

        st.divider()
        st.subheader("📝 Individual Documentation")
        f_df_sorted = f_df.sort_values(by=['due_date_obj', 'company'])
        options = f_df_sorted.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.2f})", axis=1).tolist()
        option_to_id = dict(zip(options, f_df_sorted['id'].tolist()))
        sel_label = st.selectbox("Select Invoice to Document:", options)
        
        if sel_label:
            sid = option_to_id[sel_label]; row_data = f_df[f_df['id'] == sid].iloc[0]
            for n in str(row_data['notes']).split('\n'):
                if n and n != 'None': st.markdown(f"<div class='log-box'>{n}</div>", unsafe_allow_html=True)
            
            c_in1, c_in2, c_in3 = st.columns([2, 1, 1])
            with c_in1: entry = st.text_input("New Note:")
            with c_in2: rec_amt = st.number_input("Received ($):", value=float(row_data['received_amount']))
            with c_in3: nst = st.selectbox("New Status:", ["Sent", "Paid", "Overdue", "In Dispute"], index=["Sent", "Paid", "Overdue", "In Dispute"].index(row_data['status']))
            
            if st.button("Save Documentation"):
                if entry: add_log_entry(sid, entry)
                final_status = "Paid" if rec_amt >= row_data['amount'] else nst
                supabase.table("billing_history").update({"status": final_status, "received_amount": float(rec_amt)}).eq("id", sid).execute()
                add_log_entry(sid, f"Update: {final_status} | Received: ${rec_amt:,.2f}")
                st.success("Documented!"); st.rerun()

        st.divider()
        st.subheader("⚡ Bulk Actions (Multi-Select)")
        bulk_list = st.multiselect("Select invoices for Bulk Full Payment:", options)
        if st.button("✅ Mark All Selected as Fully Paid", use_container_width=True):
            for item in bulk_list:
                bid = option_to_id[item]; b_amt = df_raw[df_raw['id'] == bid]['amount'].values[0]
                supabase.table("billing_history").update({"status": "Paid", "received_amount": float(b_amt)}).eq("id", bid).execute()
                add_log_entry(bid, "Bulk update: Fully Paid")
            st.success("Bulk update complete!"); st.rerun()
    else: st.info("No records.")
