import streamlit as st
import pandas as pd
import pdfplumber
import re
import time
import hashlib
from datetime import datetime
from supabase import create_client

# --- 1. CORE FUNCTIONS ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_billing_data():
    res = supabase.table("billing_history").select("*").execute()
    return pd.DataFrame(res.data)

def generate_file_hash(file):
    """יצירת טביעת אצבע ייחודית לקובץ"""
    file_bytes = file.getvalue()
    return hashlib.md5(file_bytes).hexdigest()

def scan_receipt(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", text)
        amount = float(amounts[-1].replace(',', '')) if amounts else 0.0
        return text, amount
    except:
        return "", 0.0

# --- 2. UI ---
st.set_page_config(page_title="Tuesday | Smart Sync", layout="wide")
st.title("Smart Receipt Sync 🧾")

uploaded_files = st.file_uploader("העלה קבלות לסריקה", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df_all = get_billing_data()
    
    for uploaded_file in uploaded_files:
        with st.container():
            st.markdown(f"### סריקת קובץ: {uploaded_file.name}")
            
            # יצירת האש לקובץ הנוכחי
            current_hash = generate_file_hash(uploaded_file)
            raw_text, receipt_amt = scan_receipt(uploaded_file)
            
            if receipt_amt > 0:
                # בדיקת כפילות לפי האש (Hash)
                is_duplicate = False
                if not df_all.empty and 'file_hash' in df_all.columns:
                    is_duplicate = (df_all['file_hash'] == current_hash).any()

                # זיהוי חברה
                df_open = df_all[df_all['status'] != 'Paid']
                found_company = None
                if not df_open.empty:
                    for comp in df_open['company'].unique():
                        if str(comp).lower() in raw_text.lower():
                            found_company = comp
                            break
                
                col1, col2 = st.columns(2)
                col1.metric("סכום שזוהה", f"₪{receipt_amt:,.2f}")
                col2.metric("חברה משוייכת", found_company if found_company else "לא זוהה")

                # מנגנון חסימת כפילות
                allow_action = True
                if is_duplicate:
                    st.error(f"🚫 **עצור! קבלה זו כבר הוזנה במערכת בעבר.** (זיהוי לפי תוכן הקובץ)")
                    confirm_dup = st.checkbox(f"אני מבין שזו כפילות ובכל זאת רוצה לעדכן ({uploaded_file.name})", value=False)
                    if not confirm_dup:
                        allow_action = False

                if found_company and allow_action:
                    rel = df_open[df_open['company'] == found_company].sort_values(by='date').iloc[0]
                    
                    if st.button(f"🚀 אשר ועדכן קונטרול - {found_company}", key=f"sync_{uploaded_file.name}"):
                        new_rec = float(rel['received_amount'] or 0) + receipt_amt
                        new_stat = "Paid" if new_rec >= float(rel['amount']) else "Partial"
                        
                        # עדכון ה-DB כולל ה-Hash הייחודי
                        supabase.table("billing_history").update({
                            "received_amount": new_rec,
                            "status": new_stat,
                            "file_hash": current_hash, # שמירת טביעת האצבע
                            "notes": f"{rel.get('notes', '')}\nסריקה: {uploaded_file.name}"
                        }).eq("id", rel['id']).execute()
                        
                        st.success(f"עודכן! הקבלה ננעלה במערכת למניעת כפילויות.")
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("לא נמצא סכום תקין.")
            st.divider()

if st.button("חזרה לקונטרול (עמוד 4)"):
    st.switch_page("pages/4_Operations_Control.py")
