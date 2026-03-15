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

# פונקציית שליפה ללא Cache כדי לאפשר עדכון בלחיצת כפתור
def get_cloud_history():
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0.0)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_display'] = pd.to_datetime(df['due_date'], errors='coerce').dt.strftime('%d/%m/%Y')
        # המרה לאובייקט תאריך לצורך חישובים פנימיים
        df['due_date_dt'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
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

# --- 2. UI STYLE ---
st.set_page_config(page_title="Tuesday | Control Center", layout="wide")
st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# כותרת וכפתור עדכון בשורה אחת
c1, c2 = st.columns([4, 1])
with c1:
    st.title("Operations Control 🔍")
with c2:
    if st.button("🔄 עדכן נתונים", use_container_width=True):
        st.cache_resource.clear() # מנקה את החיבור
        st.rerun()

# --- 3. MAIN TABLE ---
df_raw = get_cloud_history()

if not df_raw.empty:
    # פילטרים
    f1, f2 = st.columns([2,1])
    with f1: c_sel = st.multiselect("חפש חברה:", sorted(df_raw['company'].unique()))
    with f2: s_sel = st.multiselect("סינון סטטוס:", sorted(df_raw['status'].unique()))

    f_df = df_raw.copy()
    if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
    if s_sel: f_df = f_df[f_df['status'].isin(s_sel)]

    def highlight_st(val):
        if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
        if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold;'
        if val == 'Partial': return 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold;'
        if val == 'Sent Reminder': return 'background-color: #fef3c7; color: #92400e; font-weight: bold;'
        return ''

    view_cols = ['id', 'company', 'date', 'due_date_display', 'amount', 'received_amount', 'status']
    st.dataframe(
        f_df[view_cols].style.applymap(highlight_st, subset=['status']).format({
            'amount': '₪{:,.2f}',
            'received_amount': '₪{:,.2f}'
        }),
        use_container_width=True, hide_index=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 4. ACTIONS (Expanders) ---
    with st.expander("⚡ Batch Execute (עדכון מהיר ב-V)", expanded=False):
        bulk_df = f_df[['id', 'company', 'due_date_display', 'amount', 'received_amount']].copy()
        bulk_df['Select'] = False
        edited_df = st.data_editor(
            bulk_df,
            column_config={
                "Select": st.column_config.CheckboxColumn("בחר", default=False),
                "id": None, "amount": st.column_config.NumberColumn("סכום", format="₪%.2f"),
                "received_amount": st.column_config.NumberColumn("התקבל", format="₪%.2f")
            },
            hide_index=True, use_container_width=True
        )

        if st.button("🚀 סגור את כל המסומנים כ-'שולם'", use_container_width=True):
            to_update = edited_df[edited_df['Select'] == True]
            if not to_update.empty:
                for _, row in to_update.iterrows():
                    supabase.table("billing_history").update({
                        "status": "Paid", "received_amount": float(row['amount'])
                    }).eq("id", int(row['id'])).execute()
                    add_log_entry(row['id'], f"Batch Update: Paid ₪{row['amount']}")
                st.success(f"עודכנו {len(to_update)} רשומות!")
                time.sleep(1); st.rerun()

    with st.expander("📝 Manual Update & Audit (הערות ועדכון פרטני)", expanded=False):
        sel_name = st.selectbox("בחר חברה:", ["בחר..."] + sorted(f_df['company'].unique().tolist()))
        if sel_name != "בחר...":
            sub_df = f_df[f_df['company'] == sel_name]
            sel_rec = st.selectbox("בחר עסקה:", sub_df.apply(lambda r: f"ID: {r['id']} | {r['date']} | ₪{r['amount']}", axis=1))
            sid = int(sel_rec.split(":")[1].split("|")[0].strip())
            row_data = df_raw[df_raw['id'] == sid].iloc[0]
            
            st.info(row_data['notes'] if row_data['notes'] else "אין הערות.")
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1: new_note = st.text_input("הערה חדשה:")
            with c2: rec_val = st.number_input("סכום שהתקבל:", value=float(row_data['received_amount']))
            with c3: new_stat = st.selectbox("סטטוס:", ["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"], 
                                           index=["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"].index(row_data['status']))
            
            if st.button("שמור שינויים", use_container_width=True):
                supabase.table("billing_history").update({"status": new_stat, "received_amount": float(rec_val)}).eq("id", sid).execute()
                if new_note: add_log_entry(sid, new_note)
                st.success("עודכן!"); time.sleep(0.5); st.rerun()
else:
    st.info("אין נתונים להצגה.")
