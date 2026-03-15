import streamlit as st
import pandas as pd
import pdfplumber
import re
import time
from datetime import datetime
from supabase import create_client

# --- 1. CORE FUNCTIONS ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_open_invoices():
    res = supabase.table("billing_history").select("*").neq("status", "Paid").execute()
    return pd.DataFrame(res.data)

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
    df_open = get_open_invoices()
    
    for uploaded_file in uploaded_files:
        with st.container():
            st.markdown(f"### סריקת קובץ: {uploaded_file.name}")
            raw_text, receipt_amt = scan_receipt(uploaded_file)
            
            if receipt_amt > 0:
                # זיהוי חברה
                found_company = None
                if not df_open.empty:
                    for comp in df_open['company'].unique():
                        if str(comp).lower() in raw_text.lower():
                            found_company = comp
                            break
                
                # תצוגת הממצאים למשתמש
                col1, col2 = st.columns(2)
                col1.metric("סכום שזוהה", f"₪{receipt_amt:,.2f}")
                col2.metric("חברה משוייכת", found_company if found_company else "לא זוהה")

                if found_company:
                    # מציאת השורה הרלוונטית
                    rel = df_open[df_open['company'] == found_company].sort_values(by='date').iloc[0]
                    
                    st.warning(f"המערכת מוכנה לעדכן את {found_company} (חוב נוכחי: ₪{float(rel['amount']):,.2f})")
                    
                    # --- הכפתור שביקשת ---
                    # רק בלחיצה עליו העדכון יבוצע בפועל
                    if st.button(f"🚀 אשר ועדכן קונטרול - {found_company}", key=f"sync_{rel['id']}"):
                        new_rec = float(rel['received_amount'] or 0) + receipt_amt
                        new_stat = "Paid" if new_rec >= float(rel['amount']) else "Partial"
                        
                        supabase.table("billing_history").update({
                            "received_amount": new_rec,
                            "status": new_stat,
                            "notes": f"עודכן מסריקה: {uploaded_file.name} ({datetime.now().strftime('%d/%m/%Y')})"
                        }).eq("id", rel['id']).execute()
                        
                        st.success(f"עודכן בהצלחה! {found_company} בסטטוס {new_stat}")
                        time.sleep(1)
                        st.rerun()
                else:
                    st.error("לא נמצאה חברה תואמת בקונטרול. וודא ששם החברה מופיע בטקסט של הקבלה.")
            else:
                st.error("לא הצלחתי לחלץ סכום מהקובץ הזה.")
            st.divider()

if st.button("חזרה לקונטרול (עמוד 4)"):
    st.switch_page("pages/4_Operations_Control.py")
