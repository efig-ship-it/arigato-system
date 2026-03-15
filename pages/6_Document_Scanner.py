import streamlit as st
import pandas as pd
import pdfplumber
import re
import time
from datetime import datetime
from supabase import create_client

# --- 1. CORE FUNCTIONS (עצמאי למניעת שגיאות Import) ---

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
        df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
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
    except: pass

# --- 2. SMART ICOUNT SCANNER ---
def scan_receipt(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        
        # חיפוש סכום בשקלים (₪) - לוקח את האחרון שמופיע (הסכום הסופי בשורה התחתונה)
        amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", text)
        if amounts:
            amount = float(amounts[-1].replace(',', ''))
        else:
            # גיבוי במידה ואין סימן ₪
            match = re.search(r"(?:סה\"כ שולם|סה\"כ כולל מע\"מ|Total|Amount)[:\s]*₪?([\d,]+\.\d{2})", text)
            amount = float(match.group(1).replace(',', '')) if match else 0.0
            
        return text, amount
    except:
        return "", 0.0

# --- 3. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Smart Receipt Sync", page_icon="🧾", layout="wide")

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
    .match-partial { background-color: #eff6ff; border-color: #3b82f6; color: #1e40af; }
    .match-error { background-color: #fef2f2; border-color: #ef4444; color: #991b1b; }
    </style>
""", unsafe_allow_html=True)

st.title("Flexible Receipt Sync 🧾")
st.write("מערכת סריקה חכמה: הכסף מהקבלה יחולק אוטומטית בין החובות הפתוחים של הלקוח.")

# --- 4. MAIN INTERFACE ---
uploaded_files = st.file_uploader("Upload iCount Receipts (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df_cloud = get_cloud_history()
    
    if not df_cloud.empty:
        for uploaded_file in uploaded_files:
            with st.spinner(f"סורק את {uploaded_file.name}..."):
                raw_text, receipt_total = scan_receipt(uploaded_file)
                
                # זיהוי חברה
                found_company = None
                for comp in df_cloud['company'].unique():
                    if comp.lower() in raw_text.lower():
                        found_company = comp
                        break
                
                if found_company and receipt_total > 0:
                    # מציאת כל החובות הפתוחים של החברה (מסודר מהישן לחדש)
                    open_invoices = df_cloud[
                        (df_cloud['company'] == found_company) & 
                        (df_cloud['status'] != 'Paid')
                    ].sort_values(by='date_dt', ascending=True)
                    
                    if not open_invoices.empty:
                        remaining_money = receipt_total
                        updated_count = 0
                        
                        for _, inv in open_invoices.iterrows():
                            if remaining_money <= 0: break
                            
                            inv_id = inv['id']
                            current_balance = inv['balance']
                            
                            if remaining_money >= current_balance:
                                # הקבלה מכסה את כל החוב הספציפי הזה
                                payment_to_apply = current_balance
                                new_received = inv['amount'] # סגירה מלאה
                                new_status = "Paid"
                                remaining_money -= current_balance
                            else:
                                # הקבלה מכסה רק חלק מהחוב הזה
                                payment_to_apply = remaining_money
                                new_received = inv['received_amount'] + remaining_money
                                new_status = "Partial"
                                remaining_money = 0
                            
                            # עדכון ב-Supabase
                            supabase.table("billing_history").update({
                                "received_amount": new_received,
                                "status": new_status
                            }).eq("id", inv_id).execute()
                            
                            add_log_entry(inv_id, f"Auto-Sync: Applied ₪{payment_to_apply:,.2f} from {uploaded_file.name}")
                            updated_count += 1
                        
                        # הודעת הצלחה מפורטת
                        msg_type = "match-success" if remaining_money == 0 else "match-partial"
                        st.markdown(f"""<div class="sync-card {msg_type}">
                            <b>✅ {found_company}</b>: שוייך סכום של ₪{receipt_total:,.2f} עבור {updated_count} חשבוניות פתוחות.
                        </div>""", unsafe_allow_html=True)
                        
                    else:
                        st.markdown(f"""<div class="sync-card match-error">
                            <b>⚠️ {found_company}</b>: נמצאה קבלה על סך ₪{receipt_total:,.2f}, אך לא קיימים חובות פתוחים במערכת.
                        </div>""", unsafe_allow_html=True)
                else:
                    st.error(f"לא הצלחתי לזהות חברה או סכום בקובץ: {uploaded_file.name}")

        if st.button("Refresh Control Center"):
            st.switch_page("pages/4_Collections_Control.py")
