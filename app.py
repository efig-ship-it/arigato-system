import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta, date
from supabase import create_client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="TMC Billing PRO", layout="wide")

# --- 2. DATABASE CONNECTION ---
if "supabase" not in st.session_state:
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    st.session_state.supabase = create_client(u, k)

supabase = st.session_state.supabase

# --- 3. GLOBAL CSS & ANIMATIONS ---
st.markdown("""<style>
    .main { background-color: #f4f7f9; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; font-weight: 700 !important; color: #003366; }
    div[data-testid="stMetric"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e1e8ed; padding: 15px !important; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    .tuesday-header { font-size: 28px; font-weight: 900; color: #003366; margin-bottom: 10px; padding-left: 5px; }
    .risk-box { border: 2px solid #e53e3e; background-color: #fff5f5; padding: 15px; border-radius: 10px; margin-bottom: 15px; color: #c53030; }
    .detective-box { border: 2px solid #ed8936; background-color: #fffaf0; padding: 15px; border-radius: 10px; margin-bottom: 15px; color: #9c4221; }
    .alert-box { border-right: 6px solid #003366; margin-bottom: 20px; padding: 15px; background: white; border-radius: 10px; border: 1px solid #e1e8ed; }
    .log-box { background-color: #ffffff; padding: 10px; border-radius: 6px; border: 1px solid #e0e4e8; border-right: 4px solid #003366; margin-bottom: 5px; font-size: 13px; direction: ltr; }
    
    /* Live Animations */
    @keyframes wobble { 0%, 100% { transform: rotate(-8deg); } 50% { transform: rotate(8deg); } }
    @keyframes ring { 0% { transform: scale(1); } 50% { transform: scale(1.2) rotate(15deg); } 100% { transform: scale(1); } }
    @keyframes flash { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.7; transform: scale(1.25); filter: drop-shadow(0 0 15px red); } }
    
    .suitcase-anim { font-size: 100px; text-align: center; display: block; animation: wobble 0.8s infinite ease-in-out; }
    .bell-anim { font-size: 100px; text-align: center; display: block; animation: ring 0.4s infinite ease-in-out; }
    .siren-anim { font-size: 100px; text-align: center; display: block; animation: flash 0.5s infinite; }
</style>""", unsafe_allow_html=True)

# --- 4. SHARED FUNCTIONS (The Engine) ---

def get_cloud_history():
    """מושך את כל היסטוריית הגבייה מהענן ומבצע עיבוד נתונים ראשוני"""
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
            df['due_date_str'] = df['due_date_obj'].apply(lambda x: x.strftime('%Y-%m-%d') if not pd.isna(x) else "")
            df['month_sent'] = df['date_sent_dt'].dt.strftime('%b %Y')
            
            today = date.today()
            def auto_status(row):
                if row['status'] == 'Paid': return 'Paid'
                if pd.notna(row['due_date_obj']) and row['due_date_obj'] < today: return 'Overdue'
                return row['status']
            
            df['status'] = df.apply(auto_status, axis=1)
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
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def add_log_entry(item_id, entry_text):
    """מוסיף הערה עם חותמת זמן להיסטוריית התיעוד של חוב ספציפי"""
    current_time = (datetime.now() + timedelta(hours=2)).strftime("%d/%m/%y %H:%M")
    new_entry = f"[{current_time}] {entry_text}"
    res = supabase.table("billing_history").select("notes").eq("id", item_id).execute()
    old_notes = res.data[0]['notes'] if res.data and res.data[0]['notes'] else ""
    updated = f"{old_notes}\n{new_entry}".strip() if old_notes else new_entry
    supabase.table("billing_history").update({"notes": updated}).eq("id", item_id).execute()

def clean_amount(val):
    """מנקה תווים לא רלוונטיים מסכומי כסף (למשל סימן דולר או פסיקים)"""
    try:
        if pd.isna(val): return 0.0
        return float(re.sub(r'[^\d.]', '', str(val)))
    except:
        return 0.0

def extract_total_amount_from_file(uploaded_file):
    """סורק קובץ אקסל מצורף ומחבר את כל הערכים בעמודת amount"""
    try:
        temp_df = pd.read_excel(uploaded_file)
        temp_df.columns = [str(c).lower().strip() for c in temp_df.columns]
        if 'amount' in temp_df.columns:
            return float(pd.to_numeric(temp_df['amount'].apply(clean_amount), errors='coerce').fillna(0.0).sum())
    except:
        pass
    return 0.0

def play_siren():
    """מפעיל צליל התראה (משמש ב-Reminders Manager)"""
    st.markdown("""<audio autoplay><source src="https://www.soundjay.com/buttons/beep-01a.mp3" type="audio/mpeg"></audio>""", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday PRO</p>', unsafe_allow_html=True)
st.title("TMC Billing PRO - Command Center")
st.write("### Welcome, Admin")
st.info("Select a module from the sidebar to begin managing invoices, analytics, or collections.")

# הצגת תקציר מהיר בעמוד הבית
df_quick = get_cloud_history()
if not df_quick.empty:
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Outstanding", f"${df_quick['balance'].sum():,.0f}")
    col2.metric("Overdue Count", len(df_quick[df_quick['status'] == 'Overdue']))
    col3.metric("Latest Sync", datetime.now().strftime("%H:%M:%S"))
