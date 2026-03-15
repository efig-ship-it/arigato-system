import streamlit as st
import pandas as pd
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

def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # המרה בטוחה של מספרים
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0.0)
        df['balance'] = df['amount'] - df['received_amount']
        # פורמט תאריך לתצוגה
        df['due_date_display'] = pd.to_datetime(df['due_date'], errors='coerce').dt.strftime('%d/%m/%Y')
    return df

def add_log_entry(record_id, note_text):
    try:
        res = supabase.table("billing_history").select("notes").eq("id", record_id).single().execute()
        current_notes = res.data.get("notes", "") if res.data else ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"[{timestamp}] {note_text}"
        updated_notes = f"{current_notes}\n{new_entry}" if current_notes else new_entry
        supabase.table("billing_history").update({"notes": updated_notes}).eq("id", record_id).execute()
    except: pass

# --- 2. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Control Center", layout="wide")
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .stDataFrame { border: 1px solid #e2e8f0; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

st.title("Operations Control 🔍")

# --- 3. MAIN LOGIC ---
df_raw = get_cloud_history()

if not df_raw.empty:
    # פילטרים
    f1, f2 = st.columns([2,1])
    with f1: c_sel = st.multiselect("חפש חברה:", sorted(df_raw['company'].unique()))
    with f2: s_sel = st.multiselect("סינון סטטוס:", sorted(df_raw['status'].unique()))

    f_df = df_raw.copy()
    if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
    if s_sel: f_df = f_df[f_df['status'].isin(s_sel)]

    # צבעים
    def highlight_st(val):
        if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
        if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold;'
        if val == 'Partial': return 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold;'
        if val == 'Sent Reminder': return 'background-color: #fef3c7; color: #92400e; font-weight: bold;'
        return ''

    # טבלה ראשית (לקריאה בלבד)
    view_cols = ['id', 'company', 'date', 'due_date_display', 'amount', 'received_amount', 'status']
    st.dataframe(
        f_df[view_cols].style.applymap(highlight_st, subset=['status']).format({'amount': '₪{:,.2f}', 'received_amount': '₪{:,.2f}'}),
        use_container_width=True, hide_index=True
    )

    st.divider()

    # --- 4. ה-BATCH EXECUTE (המולטי שחזר) ---
    st.subheader("⚡ Batch Execute (תשלום מהיר ב-V)")
    bulk_df = f_df[['id', 'company', 'due_date_display', 'amount', 'received_amount']].copy()
    bulk_df['Select'] = False # עמודת ה-V
    
    # עריכת הטבלה כדי לאפשר סימון V
    edited_df = st.data_editor(
        bulk_df,
        column_config={
            "Select": st.column_config.CheckboxColumn("בחר", default=False),
            "id": None, # הסתרת ה-ID מהתצוגה
            "amount": st.column_config.NumberColumn("סכום", format="₪%.2f"),
            "received_amount": st.column_config.NumberColumn("התקבל", format="₪%.2f")
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("🚀 עדכן את כל המסומנים כ-'שולם'", use_container_width=True):
        to_update = edited_df[edited_df['Select'] == True]
        if not to_update.empty:
            for _, row in to_update.iterrows():
                # מעדכן שהסכום שהתקבל שווה לסכום החשבונית
                supabase.table("billing_history").update({
                    "status": "Paid",
                    "received_amount": float(row['amount'])
                }).eq("id", int(row['id'])).execute()
                add_log_entry(row['id'], f"Batch Update: Paid in full (₪{row['amount']})")
            st.success(f"עודכנו {len(to_update)} רשומות בהצלחה!")
            time.sleep(1)
            st.rerun()
        else:
            st.warning("לא נבחרו רשומות לביצוע.")

    st.divider()

    # --- 5. עדכון פרטני (הערות) ---
    st.subheader("📝 הערות ותיעוד פרטני")
    sel_name = st.selectbox("בחר חברה לעדכון הערה:", f_df['company'].unique())
    if sel_name:
        sub_df = f_df[f_df['company'] == sel_name]
        sel_rec = st.selectbox("בחר חשבונית ספציפית:", sub_df.apply(lambda r: f"ID: {r['id']} | {r['date']} | ₪{r['amount']}", axis=1))
        sid = int(sel_rec.split(":")[1].split("|")[0].strip())
        
        row_data = df_raw[df_raw['id'] == sid].iloc[0]
        with st.expander("היסטוריית הערות"):
            st.write(row_data['notes'] if row_data['notes'] else "אין הערות.")
        
        new_note = st.text_input("הערה חדשה:")
        if st.button("שמור הערה"):
            if new_note:
                add_log_entry(sid, new_note)
                st.success("הערה נשמרה.")
                time.sleep(0.5); st.rerun()
else:
    st.info("אין נתונים.")
