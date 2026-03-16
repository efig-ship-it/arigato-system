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

def get_billing_data():
    res = supabase.table("billing_history").select("*").execute()
    return pd.DataFrame(res.data)

def scan_receipt_details(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            # קורא את כל העמוד הראשון כדי לא לפספס
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            
        # --- בדיקת סוג מסמך חסינה (קבלה) ---
        # 1. חיפוש רגיל
        # 2. חיפוש הפוך (עברית ויזואלית)
        # 3. בדיקה אם קיים "סה"כ שולם" (מעיד על קבלה)
        header_area = text[:600] # מרחיבים את אזור הכותרת
        
        is_receipt = (
            "קבלה" in header_area or 
            "הלבק" in header_area or 
            "שולם" in header_area or
            "סה\"כ שולם" in text
        )
        
        # --- חילוץ מספר מסמך ---
        # מחפש מספר שמופיע ליד המילה קבלה או בתחילת הטקסט
        doc_num = "Unknown"
        doc_match = re.search(r"(\d{4,8})", header_area) # מחפש רצף ספרות של מספר מסמך
        if doc_match:
            doc_num = doc_match.group(1)
        
        # --- חילוץ סכום "סה"כ שולם" ---
        amount = 0.0
        # מחפש "סה"כ שולם" או "םלוש כ"הס" (הפוך)
        paid_match = re.search(r"(?:סה\"כ שולם|םלוש כ\"הס)\s?₪?\s?([\d,]+\.\d{2})", text)
        if paid_match:
            amount = float(paid_match.group(1).replace(',', ''))
        else:
            # גיבוי: חיפוש סכום ליד ₪
            amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", text)
            if amounts:
                amount = float(amounts[-1].replace(',', ''))
        
        return text, amount, doc_num, is_receipt
    except Exception as e:
        return str(e), 0.0, "Error", False

# --- 2. UI ---
st.set_page_config(page_title="Tuesday | Smart Sync", layout="wide")
st.title("Smart Receipt Sync 🧾")

uploaded_files = st.file_uploader("העלה קבלות לסריקה", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df_all = get_billing_data()
    
    for uploaded_file in uploaded_files:
        with st.container():
            st.markdown(f"### עיבוד קובץ: {uploaded_file.name}")
            raw_text, receipt_amt, doc_id, is_receipt = scan_receipt_details(uploaded_file)
            
            # הצגת ה-Debug למקרה שזה עדיין נכשל (תוכל לראות מה המערכת "רואה")
            if not is_receipt:
                st.error("🚫 המערכת לא זיהתה את המילה 'קבלה' בכותרת.")
                with st.expander("לחץ כאן כדי לראות מה המערכת קראה מהקובץ"):
                    st.text(raw_text[:1000]) # מציג את הטקסט הגולמי שחולץ
                st.divider()
                continue

            if receipt_amt > 0:
                df_open = df_all[df_all['status'] != 'Paid']
                found_company = None
                if not df_open.empty:
                    for comp in df_open['company'].unique():
                        # בדיקה גמישה לשם החברה
                        if str(comp).lower().strip() in raw_text.lower():
                            found_company = comp
                            break
                
                # בדיקת כפילות
                is_duplicate = False
                if not df_all.empty and doc_id != "Unknown":
                    is_duplicate = df_all['notes'].str.contains(f"ID-{doc_id}", na=False).any()

                col1, col2, col3 = st.columns(3)
                col1.metric("סכום ששולם", f"₪{receipt_amt:,.2f}")
                col2.metric("מספר מסמך", doc_id)
                col3.metric("חברה מזוהה", found_company if found_company else "לא זוהה")

                allow_action = True
                if is_duplicate:
                    st.error(f"⚠️ כפילות: מסמך {doc_id} כבר עודכן.")
                    allow_action = st.checkbox(f"אשר עדכון כפול ({uploaded_file.name})", key=f"check_{uploaded_file.name}")

                if found_company and allow_action:
                    rel_rows = df_open[df_open['company'] == found_company].sort_values(by='date')
                    if not rel_rows.empty:
                        rel = rel_rows.iloc[0]
                        if st.button(f"🚀 אשר ועדכן קונטרול - {found_company}", key=f"btn_{uploaded_file.name}"):
                            new_rec = float(rel['received_amount'] or 0) + receipt_amt
                            new_status = "Paid" if new_rec >= float(rel['amount']) else "Partial"
                            
                            notes = f"{rel.get('notes','')}\n[ID-{doc_id}] {receipt_amt}₪ ({datetime.now().strftime('%d/%m/%Y')})"
                            
                            supabase.table("billing_history").update({
                                "received_amount": new_rec,
                                "status": new_status,
                                "notes": notes
                            }).eq("id", rel['id']).execute()
                            
                            st.success(f"עודכן בהצלחה!")
                            time.sleep(1); st.rerun()
                else:
                    st.warning("לא מצאתי חברה תואמת עם חוב פתוח.")
            else:
                st.error("לא נמצא סכום תקין.")
            st.divider()

if st.button("חזרה לקונטרול"):
    st.switch_page("pages/4_Operations_Control.py")
