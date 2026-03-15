import streamlit as st
import pandas as pd
import pdfplumber
import re
import time
from datetime import datetime
from supabase import create_client

# --- 1. CORE FUNCTIONS (עצמאי לחלוטין למניעת שגיאות Import) ---

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
        df['due_date_obj'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
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
        st.error(f"Error updating notes: {e}")

# --- 2. LOGIC: SMART ICOUNT SCANNER ---
def scan_receipt(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        
        # חיפוש סכום בשקלים בלבד (₪) - פותר בעיית מטבע חוץ ב-iCount
        # מחפש סימן שקל ואחריו מספרים עם פסיק/נקודה
        amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", text)
        
        if amounts:
            # לוקח את הסכום האחרון שמופיע (בדרך כלל ה-Grand Total בתחתית)
            amount = float(amounts[-1].replace(',', ''))
        else:
            # גיבוי: חיפוש לפי מילות מפתח של iCount אם לא נמצא סימן ₪
            match = re.search(r"(?:סה\"כ שולם|סה\"כ כולל מע\"מ|שולם|Total|Amount)[:\s]*₪?([\d,]+\.?\d*)", text)
            amount = float(match.group(1).replace(',', '')) if match else 0.0
            
        return text, amount
    except:
        return "", 0.0

# --- 3. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Receipt Sync", page_icon="🧾", layout="wide")

st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .sync-card {
        padding: 15px; border-radius: 10px; margin-bottom: 10px; border-right: 5px solid;
    }
    .match-success { background-color: #f0fdf4; border-color: #22c55e; color: #166534; }
    .match-error { background-color: #fef2f2; border-color: #ef4444; color: #991b1b; }
    </style>
""", unsafe_allow_html=True)

st.title("Bulk Receipt Sync 🧾")
st.write("גררו לכאן את קבצי ה-PDF של iCount (קבלות/חשבוניות) לעדכון אוטומטי של המערכת.")

# --- 4. MAIN INTERFACE ---
uploaded_files = st.file_uploader("Drop iCount PDFs here", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df_cloud = get_cloud_history()
    
    if not df_cloud.empty:
        for uploaded_file in uploaded_files:
            with st.spinner(f"Analyzing {uploaded_file.name}..."):
                raw_text, amt = scan_receipt(uploaded_file)
                
                # זיהוי חברה מתוך הטקסט
                found_company = None
                for comp in df_cloud['company'].unique():
                    if comp.lower() in raw_text.lower():
                        found_company = comp
                        break
                
                if found_company and amt > 0:
                    # חיפוש התאמה ב-Supabase (חברה + סכום זהה + לא שולם)
                    # הוספנו מרווח ביטחון קטן לסכום (Round) למקרה של עיגול אגורות
                    match = df_cloud[
                        (df_cloud['company'] == found_company) & 
                        (df_cloud['status'] != 'Paid') & 
                        (df_cloud['amount'].round(2) == round(amt, 2))
                    ]
                    
                    if not match.empty:
                        target = match.iloc[0]
                        sid = target['id']
                        
                        # עדכון ב-Supabase לסגירת החוב
                        supabase.table("billing_history").update({
                            "received_amount": amt,
                            "status": "Paid",
                            "balance": 0
                        }).eq("id", sid).execute()
                        
                        add_log_entry(sid, f"🤖 Auto-Sync: Receipt matched from {uploaded_file.name} (₪{amt:,.2f})")
                        
                        st.markdown(f"""<div class="sync-card match-success">
                            <b>✅ {found_company}</b>: זוהתה התאמה! החוב על סך ₪{amt:,.2f} עודכן כבוצע.
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div class="sync-card match-error">
                            <b>⚠️ {found_company}</b>: נמצאה קבלה על סך ₪{amt:,.2f}, אך לא נמצאה חשבונית פתוחה תואמת במערכת.
                        </div>""", unsafe_allow_html=True)
                else:
                    st.error(f"לא הצלחתי לזהות חברה או סכום תקין בקובץ: {uploaded_file.name}")

        if st.button("View Updated Control Center"):
            st.switch_page("pages/4_Collections_Control.py")
