import streamlit as st
import pandas as pd
import smtplib, time, re, io
import plotly.express as px
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

# --- 2. UI CSS (🎨 Tuesday Style + Nuvei Soft) ---
st.set_page_config(page_title="TMC Billing PRO", layout="wide")
st.markdown("""<style>
    .main { background-color: #f4f7f9; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700 !important; color: #003366; }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e1e8ed; padding: 15px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    .tuesday-header { font-size: 28px; font-weight: 900; color: #003366; margin-bottom: 10px; padding-left: 5px; }
    .risk-box { border: 2px solid #e53e3e; background-color: #fff5f5; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    .detective-box { border: 2px solid #ed8936; background-color: #fffaf0; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    .alert-box { border-right: 6px solid #003366; margin-bottom: 20px; padding: 15px; background: white; border-radius: 10px; border: 1px solid #e1e8ed; }
    .log-box { background-color: #ffffff; padding: 10px; border-radius: 6px; border: 1px solid #e0e4e8; border-right: 4px solid #003366; margin-bottom: 5px; font-size: 13px; direction: rtl; }
    .success-msg { font-size: 80px; font-weight: 900; color: #28a745; text-align: center; margin-top: 10px; display: block; }
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
            df['date_sent_str'] = df['date_sent_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            df['received_amount'] = pd.to_numeric(df.get('received_amount', 0), errors='coerce').fillna(0.0)
            df['due_date_dt'] = pd.to_datetime(df['due_date'], errors='coerce')
            df['due_date_obj'] = df['due_date_dt'].dt.date
            
            # --- Auto-Status Overdue Logic ---
            today = date.today()
            def auto_status(row):
                if row['status'] == 'Paid': return 'Paid'
                if pd.notna(row['due_date_obj']) and row['due_date_obj'] < today: return 'Overdue'
                return row['status']
            df['status'] = df.apply(auto_status, axis=1)
            
            df['due_date_str'] = df['due_date_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
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

# --- PAGE 1: EMAIL SENDER ---
if page == "Email Sender 📧":
    st.title("Invoicing Center")
    col_up, col_due = st.columns([2, 1])
    with col_up: up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_due:
        st.markdown('<p style="font-weight:700; color:#4a5568;">SET DUE DATE</p>', unsafe_allow_html=True)
        mc, yc = st.columns(2); months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1); sel_y = yc.selectbox("Year", ["2025", "2026", "2027"], index=1)
    
    uploaded_files = st.file_uploader("Drop Company Invoices Here", accept_multiple_files=True)
    
    risk_cleared, detective_cleared = True, True
    if up_ex:
        df_history = get_cloud_history()
        try:
            df_ex = pd.read_excel(up_ex)
            current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            
            # --- Risk Control ---
            risk_threshold = date.today() - timedelta(days=30)
            bad_debtors = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            if not bad_debtors.empty:
                risk_cleared = st.checkbox("🚨 אני מאשר שבדקתי את חובות העבר (Risk Control)", value=False)
                if not risk_cleared:
                    st.markdown('<div class="risk-box">⚠️ <b>Risk Alert:</b> לקוחות אלו בחריגת תשלום מעל חודש:</div>', unsafe_allow_html=True)
                    for _, row in bad_debtors.drop_duplicates('company').iterrows():
                        st.error(f"● {row['company']} חייבת ${row['balance']:,.2f} מאז {row['due_date']}")

            # --- Detective ---
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
            name_issue = "emails" not in up_ex.name.lower()
            if missing or name_issue:
                detective_cleared = st.checkbox("🕵️‍♂️ אני מאשר תקינות קבצים (Detective)", value=False)
                if not detective_cleared:
                    st.markdown('<div class="detective-box">🔍 <b>Detective Alert:</b></div>', unsafe_allow_html=True)
                    if name_issue: st.warning("קובץ המיילים אינו מכיל 'Emails' בשמו.")
                    if missing: st.warning(f"חסרים קבצי חשבוניות עבור: {', '.join(missing)}")
        except: pass

    st.write("---")
    with st.expander("💡 How to get App Password"):
        st.markdown("1. [Google App Passwords](https://myaccount.google.com/apppasswords)\n2. וודא ש-2FA פעיל.\n3. צור סיסמה תחת השם 'Tuesday'.")
    
    sc1, sc2 = st.columns(2); u_m = sc1.text_input("Gmail Account"); u_p = sc2.text_input("App Password", type="password")

    can_send = up_ex and uploaded_files and risk_cleared and detective_cleared
    if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not can_send):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(u_m.strip(), u_p.strip().replace(" ",""))
            with st.spinner("Dispatching..."):
                for i, row in df_master.iterrows():
                    comp, emails = str(row.iloc[0]).strip(), [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                    files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                    amt = sum([extract_total_amount_from_file(f) for f in files])
                    if emails and files:
                        msg = MIMEMultipart(); msg['Subject'] = f"Invoice - {comp}"; msg['To'] = ", ".join(emails)
                        msg.attach(MIMEText(f"Dear {comp}, find invoices attached.", 'plain'))
                        for f in files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                        server.send_message(msg)
                        it, dv = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M"), f"{sel_y}-{months.index(sel_m)+1:02d}-15"
                        supabase.table("billing_history").insert({"date": it, "company": comp, "amount": amt, "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0}).execute()
                server.quit(); st.balloons(); st.markdown('<p class="success-msg">SUCCESS</p>', unsafe_allow_html=True); time.sleep(2); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS DASHBOARD ---
elif page == "Analytics Dashboard 📊":
    st.title("Analytics Dashboard")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        today = date.today()
        # 🚨 Alerts
        risk_v = df_raw[df_raw['status'] == 'Overdue']['balance'].sum()
        forecast_v = df_raw[(df_raw['status'] != 'Paid') & (df_raw['due_date_obj'] >= today) & (df_raw['due_date_obj'] <= today + timedelta(days=7))]['amount'].sum()
        
        c_alert1, c_alert2 = st.columns(2)
        c_alert1.markdown(f'<div class="alert-box" style="border-right-color:#e53e3e; background-color:#fff5f5;"><p style="color:#c53030; font-weight:700;">🚨 Total Overdue (חריגה)</p><h2>${risk_v:,.0f}</h2></div>', unsafe_allow_html=True)
        c_alert2.markdown(f'<div class="alert-box" style="border-right-color:#38a169; background-color:#f0fff4;"><p style="color:#2f855a; font-weight:700;">🟢 Next 7d Forecast (צפי)</p><h2>${forecast_v:,.0f}</h2></div>', unsafe_allow_html=True)
        
        # 📈 KPIs
        m1, m2, m3, m4 = st.columns(4)
        due_until_now = df_raw[df_raw['due_date_obj'] <= today]
        cei_score = (due_until_now['received_amount'].sum() / due_until_now['amount'].sum() * 100) if due_until_now['amount'].sum() > 0 else 0
        m1.metric("Collection Index (CEI)", f"{cei_score:.1f}%")
        m2.metric("Total Outstanding", f"${df_raw['balance'].sum():,.0f}")
        m3.metric("Reminded Debt", f"${df_raw[df_raw['status'] == 'Sent Reminder']['balance'].sum():,.0f}")
        m4.metric("Billed This Month", f"${df_raw[df_raw['date_sent_dt'].dt.month == today.month]['amount'].sum():,.0f}")

        st.divider()
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("📊 Status Overview")
            status_df = df_raw.groupby('status')['amount'].sum().reset_index()
            fig_pie = px.pie(status_df, values='amount', names='status', color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_g2:
            st.subheader("🔥 Top 5 Debtors")
            debtors = df_raw.groupby('company')['balance'].sum().sort_values(ascending=False).head(5).reset_index()
            debtors = debtors[debtors['balance'] > 0]
            if not debtors.empty:
                fig_bar = px.bar(debtors, x='balance', y='company', orientation='h', color='balance', color_continuous_scale='Reds')
                st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()
        st.write("**📉 Efficiency: Billed vs Received (By Due Date)**")
        c_billed = df_raw.groupby('due_date_str')['amount'].sum().reset_index().rename(columns={'amount': 'Val'}); c_billed['Type'] = 'Billed'
        c_paid = df_raw.groupby('due_date_str')['received_amount'].sum().reset_index().rename(columns={'received_amount': 'Val'}); c_paid['Type'] = 'Received'
        st.vega_lite_chart(pd.concat([c_billed, c_paid]), {
            'mark': {'type': 'bar', 'width': 20, 'cornerRadiusTopLeft': 3},
            'encoding': {'x': {'field': 'due_date_str', 'type': 'nominal', 'title': 'Due Date'}, 'y': {'field': 'Val', 'type': 'quantitative', 'title': 'Amount ($)'},
                         'xOffset': {'field': 'Type'}, 'color': {'field': 'Type', 'type': 'nominal', 'scale': {'range': ['#003366', '#87CEEB']}}}
        }, use_container_width=True)

        st.divider(); st.subheader("Filters & Details")
        f1, f2, f3 = st.columns(3)
        sel_c = f1.multiselect("Companies", sorted(df_raw['company'].unique()))
        s_rng = f2.date_input("Sent Range", value=(df_raw['date_sent_obj'].min(), df_raw['date_sent_obj'].max()))
        d_rng = f3.date_input("Due Range", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
        
        df_f = df_raw.copy()
        if sel_c: df_f = df_f[df_f['company'].isin(sel_c)]
        if isinstance(s_rng, tuple) and len(s_rng) == 2: df_f = df_f[(df_f['date_sent_obj'] >= s_rng[0]) & (df_f['date_sent_obj'] <= s_rng[1])]
        if isinstance(d_rng, tuple) and len(d_rng) == 2: df_f = df_f[(df_f['due_date_obj'] >= d_rng[0]) & (df_f['due_date_obj'] <= d_rng[1])]
        st.dataframe(df_f.pivot_table(index='company', columns='status', values='amount', aggfunc='sum', fill_value=0).style.format("${:,.0f}"), use_container_width=True)

# --- PAGE 3: COLLECTIONS CONTROL ---
elif page == "Collections Control 🔍":
    st.title("Operations Control")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        cf1, cf2 = st.columns(2)
        c_sel = cf1.multiselect("Companies", sorted(df_raw['company'].unique()))
        c_due = cf2.date_input("Due Date Filter", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
        f_df = df_raw.copy()
        if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
        if isinstance(c_due, tuple) and len(c_due) == 2: f_df = f_df[(f_df['due_date_obj'] >= c_due[0]) & (f_df['due_date_obj'] <= c_due[1])]
        
        def highlight_st(val):
            if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
            if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold; border: 1px solid #e53e3e;'
            if val == 'Sent Reminder': return 'background-color: #fefcbf; color: #744210; font-weight: bold;'
            return ''
        
        st.dataframe(f_df[['id', 'company', 'date_sent_str', 'due_date', 'amount', 'received_amount', 'status']]
                     .rename(columns={'date_sent_str': 'Sent Date'})
                     .style.applymap(highlight_st, subset=['status']).format({"amount": "{:,.2f}", "received_amount": "{:,.2f}"}), use_container_width=True, hide_index=True)
        
        st.divider(); st.subheader("Audit & Notes History")
        f_sorted = f_df.sort_values(by=['due_date_obj', 'company'])
        opts = f_sorted.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.2f})", axis=1).tolist()
        opt_to_id = dict(zip(opts, f_sorted['id'].tolist()))
        sel_l = st.selectbox("Select Record:", opts)
        if sel_l:
            sid = opt_to_id[sel_l]; row_data = df_raw[df_raw['id'] == sid].iloc[0]
            if str(row_data['notes']) and str(row_data['notes']) != 'None':
                for line in str(row_data['notes']).split('\n'):
                    if line.strip(): st.markdown(f"<div class='log-box'>{line}</div>", unsafe_allow_html=True)
            ci1, ci2, ci3 = st.columns([2, 1, 1])
            with ci1: ent = st.text_input("New Note:")
            with ci2: rec = st.number_input("Received ($):", value=float(row_data['received_amount']), key=f"rec_{sid}")
            with ci3: nst = st.selectbox("Status:", ["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"], index=["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"].index(row_data['status']), key=f"st_{sid}")
            if st.button("Save Update"):
                if ent: add_log_entry(sid, ent)
                f_st = "Paid" if rec >= row_data['amount'] else nst
                supabase.table("billing_history").update({"status": f_st, "received_amount": float(rec)}).eq("id", sid).execute()
                add_log_entry(sid, f"Update: {f_st} | ${rec:,.2f}")
                st.success("Updated."); time.sleep(0.5); st.rerun()

        st.divider(); st.subheader("⚡ Batch Execute Launch")
        bulk_prep = f_sorted[['id', 'company', 'due_date', 'amount', 'received_amount']].copy()
        bulk_prep['Select'] = False
        sel_bulk = st.data_editor(bulk_prep[['Select', 'company', 'due_date', 'amount', 'received_amount', 'id']], column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None}, disabled=['company', 'due_date', 'amount'], hide_index=True, use_container_width=True)
        if st.button("🚀 Batch Execute Update"):
            for i, row in sel_bulk[sel_bulk['Select']].iterrows():
                f_rec = row['received_amount'] if row['received_amount'] > 0 else row['amount']
                f_st = "Paid" if f_rec >= row['amount'] else "Sent"
                supabase.table("billing_history").update({"status": f_st, "received_amount": f_rec}).eq("id", row['id']).execute()
                add_log_entry(row['id'], f"Batch Update: {f_st}"); st.success("Batch done."); time.sleep(1); st.rerun()

# --- PAGE 4: REMINDERS MANAGER ---
elif page == "Reminders Manager 🚨":
    st.title("Reminders Manager")
    m_file = st.file_uploader("Upload Emails List", type=['xlsx'])
    df_raw = get_cloud_history()
    if not df_raw.empty:
        df_raw['balance'] = df_raw['amount'] - df_raw['received_amount']
        unpaid = df_raw[df_raw['balance'] > 0].copy()
        if unpaid.empty: st.success("All paid!")
        else:
            unpaid['Select'] = False
            sel_d = st.data_editor(unpaid[['Select', 'company', 'due_date', 'balance', 'id']], column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None}, use_container_width=True)
            d1, d2 = st.columns(2); mu = d1.text_input("Gmail Account"); mp = d2.text_input("App Password", type="password")
            if st.button("🚀 Send Reminders"):
                if not sel_d[sel_d['Select']].empty and m_file:
                    em_map = pd.read_excel(m_file)
                    em_dict = dict(zip(em_map.iloc[:, 0].str.strip().str.lower(), em_map.iloc[:, 1].str.strip()))
                    server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(mu.strip(), mp.strip().replace(" ",""))
                    for i, row in sel_d[sel_d['Select']].iterrows():
                        target = em_dict.get(str(row['company']).strip().lower())
                        if target:
                            msg = MIMEMultipart(); msg['Subject'] = f"Reminder - {row['company']}"; msg['To'] = target
                            msg.attach(MIMEText(f"שלום {row['company']},\nלתשומת לבכם יתרת חוב של ${row['balance']:,.2f}.\nנא להסדיר בהקדם.", 'plain'))
                            server.send_message(msg); add_log_entry(row['id'], f"🚨 Reminder to {target}"); supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
                    server.quit(); st.balloons(); st.rerun()
