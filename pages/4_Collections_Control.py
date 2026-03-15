import streamlit as st
import pandas as pd
import time
from datetime import datetime
from supabase import create_client

# --- 1. CORE FUNCTIONS (עצמאי לחלוטין למניעת שגיאות Import) ---

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
        df['amount'] = df['amount'].astype(float)
        df['received_amount'] = df['received_amount'].astype(float)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_obj'] = pd.to_datetime(df['due_date'], errors='coerce').dt.date
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
    except Exception as e:
        st.error(f"Error updating notes: {e}")

# --- 2. SIDEBAR & STYLE ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.title("Operations Control 🔍")

st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    .note-bubble {
        background-color: #f8fafc; border-right: 4px solid #3b82f6;
        padding: 12px; border-radius: 8px; margin-bottom: 8px;
        font-size: 14px; color: #1e293b;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. MAIN LOGIC ---
df_raw = get_cloud_history()

if not df_raw.empty:
    # Filters
    cf1, cf2 = st.columns(2)
    c_sel = cf1.multiselect("Search Companies", sorted(df_raw['company'].unique()))
    
    f_df = df_raw.copy()
    if c_sel: 
        f_df = f_df[f_df['company'].isin(c_sel)]
    
    # --- צביעת סטטוסים מעודכנת ---
    def highlight_st(val):
        if val == 'Paid': 
            return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
        if val == 'Overdue': 
            return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold;'
        if val == 'Partial': 
            return 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold;'
        if val == 'Sent Reminder': 
            return 'background-color: #fef3c7; color: #92400e; font-weight: bold;' # צהוב
        return ''

    st.dataframe(
        f_df[['id', 'company', 'date', 'due_date', 'amount', 'received_amount', 'status']].style.applymap(highlight_st, subset=['status']), 
        use_container_width=True, 
        hide_index=True
    )
    
    st.divider()

    # --- SINGLE UPDATE & NOTES ---
    st.subheader("Audit & Documentation")
    opts = f_df.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.0f})", axis=1).tolist()
    opt_to_id = dict(zip(opts, f_df['id'].tolist()))
    
    sel_l = st.selectbox("Select Record for Detail:", opts)
    if sel_l:
        sid = opt_to_id[sel_l]
        row_data = df_raw[df_raw['id'] == sid].iloc[0]
        
        with st.expander("📄 View Interaction History", expanded=False):
            if row_data['notes']:
                for line in str(row_data['notes']).split('\n'):
                    if line.strip():
                        st.markdown(f'<div class="note-bubble">🕒 {line}</div>', unsafe_allow_html=True)
            else:
                st.info("No notes yet.")
        
        ci1, ci2, ci3 = st.columns([2, 1, 1])
        with ci1: 
            ent = st.text_input("New Note:")
        with ci2: 
            rec = st.number_input("Received:", value=float(row_data['received_amount']), key=f"r_{sid}")
        with ci3: 
            nst = st.selectbox("Status:", ["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"], index=0)
        
        if st.button("Save Update", use_container_width=True):
            if ent: 
                add_log_entry(sid, ent)
            supabase.table("billing_history").update({"status": nst, "received_amount": float(rec)}).eq("id", sid).execute()
            st.success(f"Update Saved for {row_data['company']}!")
            time.sleep(0.5)
            st.rerun()

    st.divider()

    # --- BATCH EXECUTE ---
    with st.expander("⚡ Batch Execute (Multi-V)", expanded=False):
        bulk = f_df[['id', 'company', 'due_date', 'amount', 'received_amount']].copy()
        bulk['Select'] = False
        sel_bulk = st.data_editor(bulk, column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None}, hide_index=True, use_container_width=True)

        if st.button("🚀 Execute Batch", use_container_width=True):
            to_up = sel_bulk[sel_bulk['Select'] == True]
            if to_up.empty:
                st.warning("Please select at least one record.")
            else:
                for _, row in to_up.iterrows():
                    amt, rcv = float(row['amount']), float(row['received_amount'])
                    fin_rcv = amt if rcv == 0 else rcv
                    fin_stat = "Paid" if (amt - fin_rcv) <= 0 else "Partial"
                    supabase.table("billing_history").update({"status": fin_stat, "received_amount": fin_rcv}).eq("id", int(row['id'])).execute()
                    add_log_entry(row['id'], f"Batch Update: ${fin_rcv} received. Status: {fin_stat}")
                st.success("Batch Done!")
                time.sleep(1)
                st.rerun()
else:
    st.info("No records found in the database.")
