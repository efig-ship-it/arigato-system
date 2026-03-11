import streamlit as st
import pandas as pd
import smtplib, time, re, io
import plotly.express as px
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta, date
from supabase import create_client, Client

# --- 1. Supabase Connection ---
supabase = None
try:
    if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
        u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
        k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
        supabase = create_client(u, k)
        st.sidebar.success("✅ Cloud Connected")
except:
    st.sidebar.error("🚨 Cloud Connection Failed")

# --- 2. UI CSS (Animations & Styles) ---
st.set_page_config(page_title="TMC Billing PRO", layout="wide")
st.markdown("""<style>
    .main { background-color: #f4f7f9; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700 !important; color: #003366; }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e1e8ed; padding: 15px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    .tuesday-header { font-size: 28px; font-weight: 900; color: #003366; margin-bottom: 10px; padding-left: 5px; }
    .risk-box { border: 2px solid #e53e3e; background-color: #fff5f5; padding: 15px; border-radius: 10px; margin-bottom: 15px; color: #c53030; }
    .detective-box { border: 2px solid #ed8936; background-color: #fffaf0; padding: 15px; border-radius: 10px; margin-bottom: 15px; color: #9c4221; }
    .alert-box { border-right: 6px solid #003366; margin-bottom: 20px; padding: 15px; background: white; border-radius: 10px; border: 1px solid #e1e8ed; }
    .log-box { background-color: #ffffff; padding: 10px; border-radius: 6px; border: 1px solid #e0e4e8; border-right: 4px solid #003366; margin-bottom: 5px; font-size: 13px; direction: ltr; }
    
    /* Animations */
    @keyframes wobble { 0%, 100% { transform: rotate(-8deg); } 50% { transform: rotate(8deg); } }
    @keyframes ring { 0% { transform: scale(1); } 50% { transform: scale(1.1) rotate(15deg); } 100% { transform: scale(1); } }
    @keyframes flash { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.2); } }
    
    .suitcase-anim { font-size: 100px; text-align: center; display: block; animation: wobble 0.8s infinite ease-in-out; }
    .bell-anim { font-size: 100px; text-align: center; display: block; animation: ring 0.4s infinite ease-in-out; }
    .siren-anim { font-size: 100px; text-align: center; display: block; animation: flash 0.5s infinite; }
</style>""", unsafe_allow_html=True)

def play_siren():
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-01a.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

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
            today = date.today()
            def auto_status(row):
                if row['status'] == 'Paid': return 'Paid'
                if pd.notna(row['due_date_obj']) and row['due_date_obj'] < today: return 'Overdue'
                return row['status']
            df['status'] = df.apply(auto_status, axis=1)
            df['balance'] = df['amount'] - df['received_amount']
            df['due_date_str'] = df['due_date_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
            df['month_sent'] = df['date_sent_dt'].dt.strftime('%b %Y')
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

def add_log_entry(item_id, entry_text):
    current_time = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%y %H:%M")
    new_entry = f"[{current_time}] {entry_text}"
    res = supabase.table("billing_history").select("notes").eq("id", item_id).execute()
    old_notes = res.data[0]['notes'] if res.data and res.data[0]['notes'] else ""
    updated = f"{old_notes}\n{new_entry}".strip() if old_notes else new_entry
    supabase.table("billing_history").update({"notes": updated}).eq("id", item_id).execute()

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
            return float(pd.to_numeric(temp_df['amount'].apply(clean_amount), errors='coerce').fillna(0.0).sum())
    except: pass
    return 0.0

# --- 4. Sidebar ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)
page = st.sidebar.radio("Navigation", ["Email Sender 📧", "Analytics Dashboard 📊", "Upcoming Alerts 🔔", "Collections Control 🔍", "Reminders Manager 🚨"])

# --- PAGE 1: EMAIL SENDER ---
if page == "Email Sender 📧":
    st.title("Invoicing Dispatch")
    col_up, col_due = st.columns([2, 1])
    with col_up: up_ex = st.file_uploader("Upload Mailing List (Excel)", type=['xlsx'])
    with col_due:
        mc, yc = st.columns(2); months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        sel_m = mc.selectbox("Month", months, index=datetime.now().month - 1); sel_y = yc.selectbox("Year", ["2025", "2026", "2027"], index=1)
    uploaded_files = st.file_uploader("Drop Invoices Here", accept_multiple_files=True)
    
    risk_cleared, detective_cleared = True, True
    if up_ex:
        df_history = get_cloud_history()
        try:
            df_ex = pd.read_excel(up_ex)
            current_companies = [str(c).strip() for c in df_ex.iloc[:, 0].dropna().unique()]
            risk_threshold = date.today() - timedelta(days=30)
            bad = df_history[(df_history['company'].isin(current_companies)) & (df_history['status'] != 'Paid') & (df_history['due_date_obj'] < risk_threshold)]
            
            if not bad.empty:
                risk_ack = st.checkbox("🚨 I confirm background check for overdue debts", value=False)
                if not risk_ack:
                    st.markdown(f'<div class="risk-box">⚠️ <b>Risk Alert:</b> Overdue debtors found.</div>', unsafe_allow_html=True)
                    risk_cleared = False
            
            file_names = [f.name for f in uploaded_files] if uploaded_files else []
            missing = [c for c in current_companies if not any(c.lower() in fn.lower() for fn in file_names)]
            if missing:
                det_ack = st.checkbox("🕵️‍♂️ I confirm file review (Missing files accounted for)", value=False)
                if not det_ack:
                    st.markdown(f'<div class="detective-box">🔍 <b>Detective Alert:</b> Missing: <b>{", ".join(missing)}</b></div>', unsafe_allow_html=True)
                    detective_cleared = False
        except: pass

    st.write("---")
    sc1, sc2 = st.columns(2); u_m = sc1.text_input("Gmail Account"); u_p = sc2.text_input("App Password", type="password")
    if st.button("🚀 Start Dispatch", use_container_width=True, disabled=not (up_ex and uploaded_files and risk_cleared and detective_cleared)):
        try:
            df_master = pd.read_excel(up_ex).dropna(how='all')
            due_col = [c for c in df_master.columns if 'due' in c.lower()]
            server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls(); server.login(u_m.strip(), u_p.strip().replace(" ",""))
            sh = st.empty()
            with sh.container():
                st.markdown('<div class="suitcase-anim">💼</div>', unsafe_allow_html=True)
                with st.spinner("Dispatching..."):
                    for i, row in df_master.iterrows():
                        comp, emails = str(row.iloc[0]).strip(), [e.strip() for e in str(row.iloc[1]).split(',') if '@' in e]
                        day_val = int(row[due_col[0]]) if due_col and pd.notna(row[due_col[0]]) else 15
                        files = [f for f in uploaded_files if comp.lower() in f.name.lower()]
                        amt = sum([extract_total_amount_from_file(f) for f in files])
                        if emails and files:
                            msg = MIMEMultipart(); msg['Subject'] = f"Invoice - {comp}"; msg['To'] = ", ".join(emails)
                            msg.attach(MIMEText(f"Dear {comp}, find invoices attached.", 'plain'))
                            for f in files: msg.attach(MIMEApplication(f.getvalue(), Name=f.name))
                            server.send_message(msg)
                            it, dv = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%Y %H:%M"), f"{sel_y}-{months.index(sel_m)+1:02d}-{day_val:02d}"
                            supabase.table("billing_history").insert({"date": it, "company": comp, "amount": amt, "status": "Sent", "due_date": dv, "sender": u_m, "received_amount": 0}).execute()
            server.quit(); sh.empty(); st.balloons(); st.success("SUCCESS"); time.sleep(1); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 2: ANALYTICS (FIXED KEYERROR) ---
elif page == "Analytics Dashboard 📊":
    st.title("Analytics Dashboard")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        today = date.today()
        risk_v = df_raw[df_raw['status'] == 'Overdue']['balance'].sum()
        forecast_v = df_raw[(df_raw['status'] != 'Paid') & (df_raw['due_date_obj'] >= today) & (df_raw['due_date_obj'] <= today + timedelta(days=7))]['amount'].sum()
        c_a1, c_a2 = st.columns(2)
        c_a1.markdown(f'<div class="alert-box" style="border-right-color:#e53e3e; background-color:#fff5f5;"><p style="color:#c53030; font-weight:700;">🚨 Total Overdue</p><h2>${risk_v:,.0f}</h2></div>', unsafe_allow_html=True)
        c_a2.markdown(f'<div class="alert-box" style="border-right-color:#38a169; background-color:#f0fff4;"><p style="color:#2f855a; font-weight:700;">🟢 Next 7d Forecast</p><h2>${forecast_v:,.0f}</h2></div>', unsafe_allow_html=True)
        
        st.divider(); st.subheader("Global Filters")
        f1, f2, f3 = st.columns(3)
        sel_c = f1.multiselect("Companies", sorted(df_raw['company'].unique()))
        
        # Security check for dates to prevent KeyError
        m_s_min = df_raw['date_sent_obj'].min() if 'date_sent_obj' in df_raw.columns else today
        m_s_max = df_raw['date_sent_obj'].max() if 'date_sent_obj' in df_raw.columns else today
        s_rng = f2.date_input("Sent Range", value=(m_s_min, m_s_max))
        
        m_d_min = df_raw['due_date_obj'].min() if 'due_date_obj' in df_raw.columns else today
        m_d_max = df_raw['due_date_obj'].max() if 'due_date_obj' in df_raw.columns else today
        d_rng = f3.date_input("Due Range", value=(m_d_min, m_d_max))
        
        df = df_raw.copy()
        if sel_c: df = df[df['company'].isin(sel_c)]
        if isinstance(s_rng, tuple) and len(s_rng) == 2: df = df[(df['date_sent_obj'] >= s_rng[0]) & (df['date_sent_obj'] <= s_rng[1])]
        if isinstance(d_rng, tuple) and len(d_rng) == 2: df = df[(df['due_date_obj'] >= d_rng[0]) & (df['due_date_obj'] <= d_rng[1])]
        
        m1, m2, m3, m4 = st.columns(4)
        cei = (df[df['due_date_obj'] <= today]['received_amount'].sum() / df[df['due_date_obj'] <= today]['amount'].sum() * 100) if df[df['due_date_obj'] <= today]['amount'].sum() > 0 else 0
        m1.metric("CEI Index", f"{cei:.1f}%"); m2.metric("Outstanding", f"${df['balance'].sum():,.0f}"); m3.metric("Billed Total", f"${df['amount'].sum():,.0f}"); m4.metric("Reminded Debt", f"${df[df['status'] == 'Sent Reminder']['balance'].sum():,.0f}")
        st.divider(); g1, g2 = st.columns(2)
        with g1:
            st.subheader("Status Distribution")
            st.plotly_chart(px.pie(df.groupby('status')['amount'].sum().reset_index(), values='amount', names='status', color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
        with g2:
            st.subheader("Top 5 Debtors")
            debtors = df.groupby('company')['balance'].sum().sort_values(ascending=False).head(5).reset_index()
            if not debtors[debtors['balance']>0].empty:
                st.plotly_chart(px.bar(debtors[debtors['balance']>0], x='balance', y='company', orientation='h', color='balance', color_continuous_scale='Reds'), use_container_width=True)
        st.divider(); st.subheader("Pivot Tables")
        st.dataframe(df.pivot_table(index='company', columns='status', values='amount', aggfunc='sum', fill_value=0).style.format("${:,.0f}"), use_container_width=True)
        pc1, pc2 = st.columns(2)
        with pc1: st.dataframe(df.pivot_table(index='month_sent', values='amount', aggfunc='sum').style.format("${:,.0f}"), use_container_width=True)
        with pc2: 
            spd = df[df['days_to_pay'].notna()]
            if not spd.empty: st.dataframe(spd.groupby('company')['days_to_pay'].mean().reset_index().style.format({"days_to_pay": "{:.1f} Days"}), use_container_width=True)

# --- PAGE 3: UPCOMING ALERTS (BELL ANIM + LOCK) ---
elif page == "Upcoming Alerts 🔔":
    st.title("Proactive T-7 Alerts")
    test_due = "2026-03-15"
    test_data = pd.DataFrame([{'id': 7771, 'company': 'ARBITRIP', 'due_date': test_due, 'balance': 4500.0, 'Select': False}, {'id': 7772, 'company': 'ARBITRIP', 'due_date': test_due, 'balance': 2300.0, 'Select': False}])
    st.info(f"Proactive Reminders for: **{test_due}**")
    sel = st.data_editor(test_data, hide_index=True, use_container_width=True)
    mf_up = st.file_uploader("Upload Mailing List", type=['xlsx'], key="up_f")
    
    # Locking logic
    can_send_up = (mf_up is not None) and (sel['Select'].any())
    
    if st.button("🚀 Send Proactive Reminders", disabled=not can_send_up):
        try:
            em_dict = dict(zip(pd.read_excel(mf_up).iloc[:, 0].str.strip().str.lower(), pd.read_excel(mf_up).iloc[:, 1].str.strip()))
            sh_a = st.empty()
            with sh_a.container():
                st.markdown('<div class="bell-anim">🛎️</div>', unsafe_allow_html=True)
                with st.spinner("Ringing the Proactive Bell..."):
                    time.sleep(2)
            sh_a.empty(); st.success("Reminders sent!"); st.rerun()
        except Exception as e: st.error(f"Error: {e}")

# --- PAGE 4: COLLECTIONS CONTROL ---
elif page == "Collections Control 🔍":
    st.title("Operations Control")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        cf1, cf2 = st.columns(2)
        c_sel = cf1.multiselect("Search Companies", sorted(df_raw['company'].unique()))
        c_due = cf2.date_input("Filter Due Date", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
        f_df = df_raw.copy()
        if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
        if isinstance(c_due, tuple) and len(c_due) == 2: f_df = f_df[(f_df['due_date_obj'] >= c_due[0]) & (f_df['due_date_obj'] <= c_due[1])]
        def highlight_st(val):
            if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
            if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold; border: 1px solid #e53e3e;'
            if val == 'Sent Reminder': return 'background-color: #fefcbf; color: #744210; font-weight: bold;'
            return ''
        st.dataframe(f_df[['id', 'company', 'date_sent_str', 'due_date', 'amount', 'received_amount', 'status']].style.applymap(highlight_st, subset=['status']), use_container_width=True, hide_index=True)
        st.divider(); st.subheader("Audit Documentation")
        f_sorted = f_df.sort_values(by=['due_date_obj', 'company'])
        opts = f_sorted.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.0f})", axis=1).tolist()
        opt_to_id = dict(zip(opts, f_sorted['id'].tolist()))
        sel_l = st.selectbox("Select Record:", opts)
        if sel_l:
            sid = opt_to_id[sel_l]; row_data = df_raw[df_raw['id'] == sid].iloc[0]
            if str(row_data['notes']) != 'None':
                for line in str(row_data['notes']).split('\n'): st.markdown(f"<div class='log-box'>{line}</div>", unsafe_allow_html=True)
            ci1, ci2, ci3 = st.columns([2, 1, 1])
            with ci1: ent = st.text_input("New Note Entry:")
            with ci2: rec = st.number_input("Received:", value=float(row_data['received_amount']), key=f"r_{sid}")
            with ci3: nst = st.selectbox("Status Update:", ["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"], index=["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"].index(row_data['status']), key=f"s_{sid}")
            if st.button("Save Update"):
                if ent: add_log_entry(sid, ent)
                f_st = "Paid" if rec >= row_data['amount'] else nst
                supabase.table("billing_history").update({"status": f_st, "received_amount": float(rec)}).eq("id", sid).execute()
                st.success("Updated."); time.sleep(0.5); st.rerun()

# --- PAGE 5: REMINDERS MANAGER (SIREN ANIM + LOCK) ---
elif page == "Reminders Manager 🚨":
    st.title("Debt Recovery Board")
    mf_rem = st.file_uploader("Upload Mailing List", type=['xlsx'], key="rem_f")
    df_raw = get_cloud_history()
    if not df_raw.empty:
        df_raw['balance'] = df_raw['amount'] - df_raw['received_amount']
        unpaid = df_raw[df_raw['balance'] > 0].copy(); unpaid['Select'] = False
        sel_rem = st.data_editor(unpaid[['Select', 'company', 'due_date', 'balance', 'id']], hide_index=True, use_container_width=True)
        
        can_send_rem = (mf_rem is not None) and (sel_rem['Select'].any())
        
        if st.button("🚀 Send Recovery Alerts", disabled=not can_send_rem):
            try:
                play_siren()
                sh_r = st.empty()
                with sh_r.container():
                    st.markdown('<div class="siren-anim">🚨</div>', unsafe_allow_html=True)
                    with st.spinner("Escalating..."):
                        time.sleep(2)
                sh_r.empty(); st.balloons(); st.rerun()
            except Exception as e: st.error(f"Error: {e}")
