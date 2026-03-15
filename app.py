import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime, timedelta
import re

# --- 1. CONFIG & BRIDGE SETUP ---
# הקובץ הזה הוא הלב של האפליקציה. כל הפונקציות כאן מיוצאות לשאר העמודים.

st.set_page_config(page_title="Tuesday System", page_icon="💼", layout="wide")

@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

# --- 2. EXPORTED FUNCTIONS (Shared Logic) ---

def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = df['amount'].astype(float)
        df['received_amount'] = df['received_amount'].astype(float)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_obj'] = pd.to_datetime(df['due_date']).dt.date
    return df

def add_log_entry(record_id, note_text):
    try:
        res = supabase.table("billing_history").select("notes").eq("id", record_id).single().execute()
        current_notes = res.data.get("notes", "") if res.data else ""
        if current_notes is None: current_notes = ""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"[{timestamp}] {note_text}"
        updated_notes = f"{current_notes}\n{new_entry}" if current_notes else new_entry
        
        supabase.table("billing_history").update({"notes": updated_notes}).eq("id", record_id).execute()
    except Exception as e:
        st.error(f"Error adding log entry: {e}")

def extract_total_amount_from_file(text):
    match = re.search(r"(?:Total|סה\"כ|Amount|שולם)[:\s]*₪?([\d,]+\.?\d*)", text)
    if match:
        return float(match.group(1).replace(',', ''))
    return 0.0

# --- 3. MINIMAL INTERFACE ---
# דף זה משמש כנקודת כניסה בלבד

st.sidebar.markdown("# Tuesday System")
st.title("Welcome to Tuesday 💼")
st.info("Please select a module from the sidebar to begin.")

# הצגת תקציר מהיר מאוד רק כדי שהדף לא יהיה ריק לגמרי
df = get_cloud_history()
if not df.empty:
    st.metric("Total Outstanding Balance", f"${df['balance'].sum():,.0f}")
