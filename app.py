import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime
import re

# --- 1. CORE LOGIC (The "Backend") ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

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
    res = supabase.table("billing_history").select("notes").eq("id", record_id).single().execute()
    current_notes = res.data.get("notes", "") if res.data else ""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = f"[{timestamp}] {note_text}"
    updated_notes = f"{current_notes}\n{new_entry}" if current_notes else new_entry
    supabase.table("billing_history").update({"notes": updated_notes}).eq("id", record_id).execute()

def extract_total_amount_from_file(text):
    match = re.search(r"(?:Total|סה\"כ|Amount|שולם)[:\s]*₪?([\d,]+\.?\d*)", text)
    return float(match.group(1).replace(',', '')) if match else 0.0

# --- 2. THE REDIRECT (The "Magic") ---
# ברגע שמישהו נכנס לכתובת הראשית, הוא עובר אוטומטית לעמוד השליחה
st.switch_page("pages/1_Email_Sender.py")
