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
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            
        # 1. בדיקת סוג מסמך (חיפוש גמיש יותר למילה קבלה)
        # אנחנו מחפשים את המילה "קבלה" בכל העמוד הראשון אבל רק בחלק העליון
        header_text = text.split("לכבוד")[0] if "לכבוד" in text else text[:500]
        is_receipt = "קבלה" in header_text
        
        # 2. חילוץ מספר מסמך (לפי התמונה: המספר מופיע ליד המילה קבלה)
        doc_num_match = re.search(r"(\d+)\s?\(?תצוגה מקדימה\)?", header_text)
        if not doc_num_match:
            doc_num_match = re.search(r"(?:מספר|מס'|מס)\s?[:.\-]?\s?(\d+)", header_text)
        
        doc_num = doc_num_match.group(1) if doc_num_match else "Unknown"
        
        # 3. חילוץ סכום "סה"כ שולם" (לפי התמונה זה הסכום שמעניין אותנו)
        # מחפש את הסכום שמופיע מיד אחרי "סה"כ שולם"
        paid_match = re.search(r"סה\"כ שולם\s?₪\s?([\d,]+\.\d{2})", text)
        if paid_match:
            amount = float(paid_match.group(1).replace(',', ''))
        else:
            # גיבוי: אם לא מצא "סה"כ שולם", מחפש את ה-₪ האחרון במסמך
            amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", text)
            amount = float(amounts[-1].replace(',', '')) if amounts else 0.0
        
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
            
            # --- שלב א: סינון ---
            if not is_receipt:
                st.error(f"🚫 **מסמך נדחה:** המילה 'קבלה' לא זוהתה בכותרת המסמך.")
                st.divider()
                continue

            if receipt_amt > 0:
                # זיהוי חברה (למשל Arbitrip מהתמונה)
                df_open = df_all[df_all['status'] != 'Paid']
                found_company = None
                if not df_open.empty:
                    for comp in df_open['company'].unique():
                        # חיפוש חברה בטקסט (התעלמות מרווחים ואותיות גדולות)
                        if str(comp).lower().strip() in raw_text.lower():
                            found_company = comp
                            break
                
                # בדיקת כפילות
                is_duplicate = False
                if not df_all.empty and doc_id != "Unknown":
                    is_duplicate = df_all['notes'].str.contains(f"ID-{doc_id}", na=False).any()

                col1, col2, col3 = st.columns(3)
                col1.metric("סכום ששולם", f"₪{receipt_amt:,.2f}")
                col2.metric("מספר קבלה", doc_id)
                col3.metric("חברה מזוהה", found_company if found_company else "לא זוהה")

                allow_action = True
                if is_duplicate:
                    st.error(f"⚠️ **כפילות:** קבלה {doc_id} כבר עודכנה.")
                    allow_action = st.checkbox(f"אשר בכל זאת ({uploaded_file.name})", value=False)

                if found_company and allow_action:
                    rel_rows = df_open[df_open['company'] == found_company].sort_values(by='date')
                    if not rel_rows.empty:
                        rel = rel_rows.iloc[0]
                        if st.button(f"🚀 אשר ועדכן קונטרול - {found_company}", key=f"sync_{doc_id}_{uploaded_file.name}"):
                            new_rec = float(rel['received_amount'] or 0) + receipt_amt
                            new_status = "Paid" if new_rec >= float(rel['amount']) else "Partial"
                            
                            notes = f"{rel.get('notes','')}\n[ID-{doc_id}] {receipt_amt}₪ ({datetime.now().strftime('%d/%m/%Y')})"
                            
                            supabase.table("billing_history").update({
                                "received_amount": new_rec,
                                "status": new_status,
                                "notes": notes
                            }).eq("id", rel['id']).execute()
                            
                            st.success(f"עודכן! {found_company} עודכן ב-₪{receipt_amt}")
                            time.sleep(1); st.rerun()
                else:
                    st.warning("לא מצאתי חברה תואמת או שאין חוב פתוח.")
            else:
                st.error("לא זוהה סכום.")
            st.divider()

if st.button("חזרה לקונטרול"):
    st.switch_page("pages/4_Operations_Control.py")
