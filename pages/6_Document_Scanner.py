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
    header_text = ""
    try:
        with pdfplumber.open(file) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            
            # לוקחים את החצי העליון של העמוד הראשון (לפי גובה העמוד)
            height = first_page.height
            header_area = first_page.within_bbox((0, 0, first_page.width, height / 2))
            header_text = header_area.extract_text() or ""
            
        # 1. בדיקת כותרת משופרת
        # מחפש "קבלה" או "חשבונית מס קבלה" בחצי העליון
        is_receipt = "קבלה" in header_text
        
        # 2. חילוץ מספר מסמך מהחצי העליון
        doc_num_match = re.search(r"(?:מספר|מס'|מס|No\.)\s?[:.\-]?\s?(\d+)", header_text)
        if not doc_num_match: # גיבוי בטקסט המלא אם לא נמצא ב-Header
             doc_num_match = re.search(r"(?:מספר|מס'|מס|No\.)\s?[:.\-]?\s?(\d+)", text)
        
        doc_num = doc_num_match.group(1) if doc_num_match else "Unknown"
        
        # 3. חילוץ סכום (הסכום האחרון שמופיע עם סמל ₪)
        all_text = text + "\n" + (pdf.pages[-1].extract_text() if len(pdf.pages) > 1 else "")
        amounts = re.findall(r"₪\s?([\d,]+\.\d{2})", all_text)
        amount = float(amounts[-1].replace(',', '')) if amounts else 0.0
        
        return text, header_text, amount, doc_num, is_receipt
    except Exception as e:
        return str(e), "", 0.0, "Error", False

# --- 2. UI ---
st.set_page_config(page_title="Tuesday | Smart Sync", layout="wide")
st.title("Smart Receipt Sync 🧾")

uploaded_files = st.file_uploader("העלה קבלות לסריקה", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df_all = get_billing_data()
    
    for uploaded_file in uploaded_files:
        with st.container():
            st.markdown(f"### עיבוד קובץ: {uploaded_file.name}")
            raw_text, header_txt, receipt_amt, doc_id, is_receipt = scan_receipt_details(uploaded_file)
            
            # --- שלב א: סינון לפי כותרת (חצי עמוד עליון) ---
            if not is_receipt:
                st.error(f"🚫 **מסמך נדחה:** המילה 'קבלה' לא זוהתה בחלק העליון של המסמך.")
                with st.expander("ראה מה המערכת זיהתה בכותרת"):
                    st.write(header_txt if header_txt else "לא פוענח טקסט בכותרת")
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
                
                # בדיקת כפילות
                is_duplicate = False
                if not df_all.empty and doc_id != "Unknown":
                    is_duplicate = df_all['notes'].str.contains(f"ID-{doc_id}", na=False).any()

                col1, col2, col3 = st.columns(3)
                col1.metric("סכום", f"₪{receipt_amt:,.2f}")
                col2.metric("מספר קבלה", doc_id)
                col3.metric("חברה", found_company if found_company else "לא זוהה")

                allow_action = True
                if is_duplicate:
                    st.error(f"⚠️ **כפילות:** קבלה מספר {doc_id} כבר קיימת.")
                    allow_action = st.checkbox(f"אשר עדכון למרות כפילות מספר ({doc_id})", value=False)

                if found_company and allow_action:
                    rel_rows = df_open[df_open['company'] == found_company].sort_values(by='date')
                    if not rel_rows.empty:
                        rel = rel_rows.iloc[0]
                        
                        if st.button(f"🚀 אשר ועדכן קונטרול - {found_company}", key=f"sync_{doc_id}_{uploaded_file.name}"):
                            new_rec = float(rel['received_amount'] or 0) + receipt_amt
                            new_status = "Paid" if new_rec >= float(rel['amount']) else "Partial"
                            
                            receipt_mark = f"ID-{doc_id}"
                            updated_notes = f"{rel.get('notes', '')}\n[{receipt_mark}] {uploaded_file.name} ({datetime.now().strftime('%d/%m/%Y')})"
                            
                            supabase.table("billing_history").update({
                                "received_amount": new_rec,
                                "status": new_status,
                                "notes": updated_notes
                            }).eq("id", rel['id']).execute()
                            
                            st.success(f"עודכן! {found_company} עבר לסטטוס {new_status}")
                            time.sleep(1); st.rerun()
                elif not found_company:
                    st.error("לא מצאתי חברה תואמת בקונטרול.")
            else:
                st.error("לא נמצא סכום תקין.")
            st.divider()

if st.button("חזרה לקונטרול (עמוד 4)"):
    st.switch_page("pages/4_Operations_Control.py")
