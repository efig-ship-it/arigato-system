import streamlit as st
import pandas as pd
import time
from datetime import datetime
from supabase import create_client

# --- 1. CORE FUNCTIONS (מניעת ImportError) ---
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
        # המרה בטוחה של מספרים כדי שהסכום לא ייעלם
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0.0)
        df['balance'] = df['amount'] - df['received_amount']
        
        # תאריכים לתצוגה
        if 'due_date' in df.columns:
            df['due_date_display'] = pd.to_datetime(df['due_date'], errors='coerce').dt.strftime('%d/%m/%Y')
        else:
            df['due_date_display'] = "N/A"
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
    </style>
""", unsafe_allow_html=True)

st.title("Operations Control 🔍")

# --- 3. MAIN LOGIC ---
df_raw = get_cloud_history()

if not df_raw.empty:
    # פילטרים בראש העמוד
    cf1, cf2 = st.columns([2, 1])
    with cf1:
        c_sel = st.multiselect("חפש חברה:", sorted(df_raw['company'].unique()))
    with cf2:
        s_sel = st.multiselect("סינון סטטוס:", sorted(df_raw['status'].unique()))

    f_df = df_raw.copy()
    if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
    if s_sel: f_df = f_df[f_df['status'].isin(s_sel)]

    # פונקציית צביעת סטטוסים
    def highlight_st(val):
        if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
        if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold;'
        if val == 'Partial': return 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold;'
        if val == 'Sent Reminder': return 'background-color: #fef3c7; color: #92400e; font-weight: bold;' # צהוב
        return ''

    # הצגת הטבלה המרכזית עם פורמט שקלים
    view_cols = ['id', 'company', 'date', 'due_date_display', 'amount', 'received_amount', 'status']
    st.dataframe(
        f_df[view_cols].style.applymap(highlight_st, subset=['status']).format({
            'amount': '₪{:,.2f}',
            'received_amount': '₪{:,.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # --- עדכון פרטני ---
    st.subheader("Manual Update & Documentation")
    opts = f_df.apply(lambda r: f"{r['company']} | {r['due_date_display']} | סכום: ₪{r['amount']:,.0f}", axis=1).tolist()
    opt_to_id = dict(zip(opts, f_df['id'].tolist()))
    
    sel_l = st.selectbox("בחר רשומה לעדכון:", opts)
    
    if sel_l:
        sid = opt_to_id[sel_l]
        row_data = df_raw[df_raw['id'] == sid].iloc[0]
        
        with st.expander("📄 היסטוריית הערות", expanded=False):
            if row_data['notes']:
                for line in str(row_data['notes']).split('\n'):
                    if line.strip(): st.info(line)
            else: st.write("אין הערות קודמות.")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            new_note = st.text_input("הערה חדשה:")
        with c2:
            rec = st.number_input("סכום שהתקבל:", value=float(row_data['received_amount']))
        with c3:
            nst = st.selectbox("סטטוס:", ["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"], 
                               index=["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"].index(row_data['status']) if row_data['status'] in ["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"] else 0)

        if st.button("שמור שינויים", use_container_width=True):
            supabase.table("billing_history").update({"status": nst, "received_amount": float(rec)}).eq("id", sid).execute()
            if new_note: add_log_entry(sid, new_note)
            st.success("עודכן בהצלחה!")
            time.sleep(0.5)
            st.rerun()
else:
    st.info("לא נמצאו נתונים להצגה.")
