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
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        
        # 1. בדיקת כותרת (200 תווים ראשונים)
        header_text = text[:200]
        # המסמך חייב להכיל "קבלה" בכותרת, אבל לא רק "חשבונית מס" לבד
        is_receipt = "קבלה" in header_text
        
        # 2. חילוץ מספר מסמך מהכותרת או מהאזור העליון
        # מחפש מספר שמופיע אחרי מילות מפתח של מספר מסמך
        doc_num_match = re.search(r"(?:מספר|מס'|מס|No\.)\s?[:.\-]?\s?(\d+)", header_text)
        if not doc_num_match: # אם לא מצא ב-200 הראשונים, נחפש בכל הטקסט אבל נתעדף התחלה
             doc_num_match = re.search(r"(?:מספר|מס'|מס|No\.)\s?[:.\-]?\s?(\d+)", text)
        
        doc_num = doc_num_match.group(1) if doc_num_match else "Unknown"
        
        # 3. חילוץ סכום (מחפש את הסכום האחרון בפורמט מטבע, לרוב זה הסה"כ)
        amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", text)
        amount = float(amounts[-1].replace(',', '')) if amounts else 0.0
        
        return text, amount, doc_num, is_receipt
    except:
        return "", 0.0, "Error", False

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
            
            # --- שלב א: סינון לפי כותרת ---
            if not is_receipt:
                st.error(f"🚫 **מסמך נדחה:** המילה 'קבלה' לא נמצאה בכותרת המסמך. המערכת מעבדת קבלות בלבד.")
                with st.expander("ראה טקסט שזוהה בכותרת"):
                    st.code(raw_text[:200])
                st.divider()
                continue

            if receipt_amt > 0:
                # זיהוי חברה
                df_open = df_all[df_all['status'] != 'Paid']
                found_company = None
                if not df_open.empty:
                    for comp in df_open['company'].unique():
                        if str(comp).lower() in raw_text.lower():
                            found_company = comp
                            break
                
                # --- שלב ב: בדיקת כפילות לפי מספר קבלה בשדה ההערות ---
                is_duplicate = False
                if not df_all.empty and doc_id != "Unknown":
                    # מחפש את התבנית המדויקת של מספר הקבלה כפי שנשמרה בעבר
                    is_duplicate = df_all['notes'].str.contains(f"ID-{doc_id}", na=False).any()

                col1, col2, col3 = st.columns(3)
                col1.metric("סכום לתשלום", f"₪{receipt_amt:,.2f}")
                col2.metric("מספר קבלה", doc_id)
                col3.metric("חברה משוייכת", found_company if found_company else "לא זוהה")

                allow_action = True
                if is_duplicate:
                    st.error(f"⚠️ **כפילות:** קבלה מספר {doc_id} כבר קיימת במערכת.")
                    allow_action = st.checkbox(f"אשר עדכון כפול למרות שמספר הקבלה ({doc_id}) כבר קיים", value=False)

                if found_company and allow_action:
                    # משיכת החוב הרלוונטי
                    rel_rows = df_open[df_open['company'] == found_company].sort_values(by='date')
                    if not rel_rows.empty:
                        rel = rel_rows.iloc[0]
                        
                        if st.button(f"🚀 אשר ועדכן קונטרול - {found_company}", key=f"sync_{doc_id}_{found_company}"):
                            new_rec = float(rel['received_amount'] or 0) + receipt_amt
                            new_stat = "Paid" if new_rec >= float(rel['amount']) else "Partial"
                            
                            # סימון ייחודי של מספר הקבלה ב-Notes למניעת כפילות עתידית
                            receipt_mark = f"ID-{doc_id}"
                            updated_notes = f"{rel.get('notes', '')}\n[{receipt_mark}] בתאריך {datetime.now().strftime('%d/%m/%Y')}"
                            
                            supabase.table("billing_history").update({
                                "received_amount": new_rec,
                                "status": new_stat,
                                "notes": updated_notes
                            }).eq("id", rel['id']).execute()
                            
                            st.success(f"הקונטרול עודכן בהצלחה! (קבלה {doc_id})")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.warning("לא נמצא חוב פתוח עבור חברה זו.")
                elif not found_company:
                    st.error("לא הצלחתי לשייך את הקבלה לחברה בקונטרול.")
            else:
                st.error("לא נמצא סכום תקין בקובץ.")
            st.divider()

if st.button("חזרה לקונטרול (עמוד 4)"):
    st.switch_page("pages/4_Operations_Control.py")
