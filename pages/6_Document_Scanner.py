import streamlit as st
import pandas as pd
import pdfplumber
import re
import time
from app import get_cloud_history, supabase, add_log_entry

# --- PAGE CONFIG ---
st.set_page_config(page_title="Tuesday | Receipt Sync", page_icon="🧾", layout="wide")

# --- CSS (Tuesday Branding) ---
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .status-card {
        padding: 15px; border-radius: 10px; margin-bottom: 10px; border-right: 5px solid;
    }
    .match-success { background-color: #f0fdf4; border-color: #22c55e; color: #166534; }
    .match-error { background-color: #fef2f2; border-color: #ef4444; color: #991b1b; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- LOGIC: EXTRACTING DATA ---
def scan_receipt(file):
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        
        # חיפוש סכום הקבלה
        amount_match = re.search(r"(?:סה\"כ|שולם|Total|Amount)[:\s]*₪?([\d,]+\.?\d*)", text)
        amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0.0
        
        # חיפוש מספר חשבונית מקושרת (אם קיים בטקסט)
        inv_match = re.search(r"(?:חשבונית|Inv|Ref)[:\s]*(\d+)", text)
        inv_ref = inv_match.group(1) if inv_match else None
        
        return text, amount, inv_ref
    except:
        return "", 0.0, None

# --- UI ---
st.title("Bulk Receipt Sync 🧾")
st.write("גררו לכאן את כל הקבלות שהפקתם ב-iCount כדי לעדכן אוטומטית את לוח הבקרה.")

uploaded_files = st.file_uploader("Upload Receipts (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    df_cloud = get_cloud_history()
    
    if not df_cloud.empty:
        results = []
        for uploaded_file in uploaded_files:
            raw_text, amt, inv_ref = scan_receipt(uploaded_file)
            
            # 1. זיהוי חברה
            found_company = None
            for comp in df_cloud['company'].unique():
                if comp.lower() in raw_text.lower():
                    found_company = comp
                    break
            
            if found_company and amt > 0:
                # 2. חיפוש החוב הכי מתאים (לפי שם חברה וסכום זהה)
                # מחפשים שורות שהן לא Paid ושהסכום שלהן פחות מה שקיבלנו תואם לקבלה
                match = df_cloud[
                    (df_cloud['company'] == found_company) & 
                    (df_cloud['status'] != 'Paid') &
                    (df_cloud['amount'] == amt) # כאן אפשר להוסיף גמישות
                ]
                
                if not match.empty:
                    target = match.iloc[0]
                    # עדכון בענן
                    supabase.table("billing_history").update({
                        "received_amount": amt,
                        "status": "Paid",
                        "balance": 0
                    }).eq("id", target['id']).execute()
                    
                    add_log_entry(target['id'], f"✅ Auto-Sync: Receipt matched for ${amt}")
                    
                    st.markdown(f"""<div class="status-card match-success">
                        <b>{found_company}</b>: זוהתה קבלה על סך ${amt:,.2f}. החוב נסגר בהצלחה.
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div class="status-card match-error">
                        <b>{found_company}</b>: זוהתה קבלה (${amt}), אך לא נמצאה חשבונית פתוחה תואמת בעמוד 4.
                    </div>""", unsafe_allow_html=True)
            else:
                st.error(f"לא הצלחתי לזהות חברה או סכום בקובץ: {uploaded_file.name}")

        if st.button("Refresh Control Center"):
            st.switch_page("pages/4_Operations_Control.py")
