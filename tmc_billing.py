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

# --- 2. CSS & Design (🎨 סעיף 7) ---
st.set_page_config(page_title="TMC Billing PRO", layout="wide") # רחב כדי שכל העמודות ייכנסו
st.markdown("""<style>
    .main { padding-top: 0rem; }
    .due-date-container { display: flex; flex-direction: column; align-items: center; margin-bottom: 5px; }
    .big-detective { font-size: 400px; text-align: center; margin: 10px 0; line-height: 1; display: block; } 
    .success-msg { font-size: 100px; font-weight: 900; color: #28a745; text-align: center; margin-top: 20px; }
    .suitcase-container { display: flex; flex-direction: column; align-items: center; justify-content: center; margin: 20px 0; }
    div[data-testid="metric-container"] { padding: 5px 10px; border: 1px solid #f0f2f6; border-radius: 10px; }
    .alert-box { padding: 15px; border-radius: 10px; margin-bottom: 10px; }
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
        st.markdown('<div class="due-date-container"><p class="due-date-label">Due Date</p></div>', unsafe_allow_html=True)
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
                st.markdown("""<div class="suitcase-container"><svg width="50" height="50" viewBox="0 0 24 24" fill="#8B4513"><path d="M17,6H16V5c0-1.1-0.9-2-2-2h-4C8.9,3,8,3.9,8,5v1H7C5.9,6,5,6.9,5,8v11c0,1.1,0.9,2,2,2h10c1.1,0,2-0.9,2-2V8 C19,6.9,18.1,6,17,6z M10,5h4v1h-4V5z M17,19H7V8h10V19z"/></svg><p style='color: #8B4513;'>Sending...</p></div>""", unsafe_allow_html=True)
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

# --- PAGE 2: ANALYTICS (📊 דגש על סכום שהתקבל בפועל) ---
elif page == "Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    df = get_cloud_history()
    if not df.empty:
        today = date.today()
        risk = df[(df['status'] != 'Paid') & (df['due_date_obj'] < today - timedelta(days=7))]['amount'].sum()
        forecast = df[(df['status'] != 'Paid') & (df['due_date_obj'] >= today) & (df['due_date_obj'] <= today + timedelta(days=7))]['amount'].sum()
        
        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="alert-box" style="background-color: #ffebee; border-right: 5px solid #d32f2f;"><p style="margin:0; font-size:14px; color: #d32f2f;">🚩 High Risk (>7d)</p><h3>${risk:,.2f}</h3></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="alert-box" style="background-color: #e8f5e9; border-right: 5px solid #2e7d32;"><p style="margin:0; font-size:14px; color: #2e7d32;">💰 Forecast (Next 7d)</p><h3>${forecast:,.2f}</h3></div>', unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Billed", f"${df['amount'].sum():,.2f}")
        m2.metric("Actually Received", f"${df['received_amount'].sum():,.2f}")
        m3.metric("Balance Owed", f"${df['amount'].sum() - df['received_amount'].sum():,.2f}")
        
        st.divider()
        p1, p2 = st.columns(2)
        p1.write("**By Company**")
        p1.dataframe(df.pivot_table(index='company', columns='status', values='amount', aggfunc='sum', fill_value=0).style.format("${:,.2f}"))
        p2.write("**Actually Received Timeline**")
        p2.bar_chart(df.groupby('due_date_obj')[['amount', 'received_amount']].sum(), color=["#003366", "#87CEEB"])
    else: st.info("No data.")

# --- PAGE 3: CONTROL (🔍 עדכון גורף + סכום שהתקבל) ---
elif page == "Collections Control 🔍":
    st.title("🔍 Collections Control")
    df = get_cloud_history()
    if not df.empty:
        # 1. פילטרים
        f_df = df.copy()
        sc = st.multiselect("Filter Companies", sorted(df['company'].unique()))
        if sc: f_df = f_df[f_df['company'].isin(sc)]

        # 2. כלי עדכון גורף (Bulk Update)
        st.subheader("⚡ Bulk Actions")
        selected_rows = st.multiselect("Select invoices for Full Payment:", f_df.apply(lambda r: f"ID {r['id']} | {r['company']} | ${r['amount']:,.2f}", axis=1))
        if st.button("✅ Mark All Selected as Fully Paid"):
            for item in selected_rows:
                sid = int(item.split('|')[0].replace('ID', '').strip())
                amt = df[df['id'] == sid]['amount'].values[0]
                supabase.table("billing_history").update({"status": "Paid", "received_amount": float(amt)}).eq("id", sid).execute()
                add_log_entry(sid, f"Bulk update: Marked as Paid (${amt:,.2f})")
            st.success("Updated all selected!"); time.sleep(0.5); st.rerun()

        st.divider()
        # 3. עריכה פרטנית (כולל received_amount)
        st.subheader("📋 Detailed Management")
        edit_mode = st.toggle("✏️ Edit Mode", value=False)
        display_cols = ['id', 'company', 'due_date', 'amount', 'received_amount', 'status', 'notes']
        
        if not edit_mode:
            st.dataframe(f_df[display_cols].style.format({"amount": "{:,.2f}", "received_amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
        else:
            edited = st.data_editor(f_df[display_cols], column_config={
                "received_amount": st.column_config.NumberColumn("Received", format="$%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "Overdue", "In Dispute"])
            }, hide_index=True)
            if st.button("💾 Save Changes"):
                for i, row in edited.iterrows():
                    sid = row['id']
                    # לוגיקה אוטומטית: אם שולם הכל, הופך ל-Paid
                    new_status = "Paid" if row['received_amount'] >= row['amount'] else row['status']
                    supabase.table("billing_history").update({
                        "received_amount": float(row['received_amount']),
                        "status": new_status,
                        "notes": f"{row['notes']} [Manual Update: {row['received_amount']} on {date.today()}]"
                    }).eq("id", sid).execute()
                st.success("Saved!"); st.rerun()

        # 4. תיעוד היסטורי למטה
        st.divider()
        sid_log = st.selectbox("View History for:", f_df['id'], format_func=lambda x: f"ID: {x} | {f_df[f_df['id']==x]['company'].values[0]}")
        if sid_log:
            notes = str(f_df[f_df['id']==sid_log]['notes'].values[0]).split('\n')
            for n in notes:
                if n and n != 'None': st.markdown(f"<div class='log-box'>{n}</div>", unsafe_allow_html=True)
    else: st.info("No data.")
