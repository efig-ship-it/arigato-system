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
    # הורדנו Cache כדי שהטבלה תהיה תמיד מסונכרנת
    res = supabase.table("billing_history").select("*").order("date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0.0)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_display'] = pd.to_datetime(df['due_date'], errors='coerce').dt.strftime('%d/%m/%Y')
    return df

def add_log_entry(record_id, note_text):
    try:
        res = supabase.table("billing_history").select("notes").eq("id", record_id).single().execute()
        current_notes = res.data.get("notes", "") or ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        updated_notes = f"{current_notes}\n[{timestamp}] {note_text}".strip()
        supabase.table("billing_history").update({"notes": updated_notes}).eq("id", record_id).execute()
    except: pass

# --- 2. UI & STYLE ---
st.set_page_config(page_title="Tuesday | Control Center", layout="wide")

if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False

st.markdown("""
    <style>
    .tuesday-header { font-family: 'Inter', sans-serif; color: #1E3A8A; font-size: 32px; font-weight: bold; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.title("Operations Control 🔍")

# --- 3. DATA LOAD ---
df_raw = get_cloud_history()

if not df_raw.empty:
    # פילטרים בראש העמוד
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1: c_sel = st.multiselect("Search Company:", sorted(df_raw['company'].unique()))
    with f2: s_sel = st.multiselect("Filter Status:", sorted(df_raw['status'].unique()))
    with f3: 
        if st.button("🔄 " + ("View Mode" if st.session_state.edit_mode else "Edit Mode"), use_container_width=True):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()

    f_df = df_raw.copy()
    if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
    if s_sel: f_df = f_df[f_df['status'].isin(s_sel)]

    # --- 4. VIEW / EDIT MODES ---
    if st.session_state.edit_mode:
        st.info("📝 **Edit Mode Enabled** - Changes update the Cloud directly upon Save.")
        edited_df = st.data_editor(
            f_df[['id', 'company', 'due_date_display', 'amount', 'received_amount', 'status']],
            column_config={
                "id": None,
                "company": st.column_config.TextColumn("Company", disabled=True),
                "due_date_display": st.column_config.TextColumn("Due Date", disabled=True),
                "amount": st.column_config.NumberColumn("Billed", format="₪%.2f", disabled=True),
                "received_amount": st.column_config.NumberColumn("Received", format="₪%.2f"),
                "status": st.column_config.SelectboxColumn("Status", options=["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"])
            },
            hide_index=True, use_container_width=True, key="control_editor"
        )

        if st.button("💾 Save All Changes", type="primary", use_container_width=True):
            with st.spinner("Syncing with Cloud..."):
                for i in range(len(edited_df)):
                    row_id = int(edited_df.iloc[i]['id'])
                    orig = df_raw[df_raw['id'] == row_id].iloc[0]
                    new_s = edited_df.iloc[i]['status']
                    new_r = float(edited_df.iloc[i]['received_amount'])
                    
                    if new_s != orig['status'] or new_r != orig['received_amount']:
                        supabase.table("billing_history").update({
                            "status": new_s,
                            "received_amount": new_r
                        }).eq("id", row_id).execute()
                        add_log_entry(row_id, f"Status changed to {new_s}")
                
                st.success("Cloud Updated! You can now check Page 5.")
                time.sleep(1)
                st.rerun()
    else:
        def highlight_st(val):
            if val == 'Paid': return 'background-color: #dcfce7; color: #166534;'
            if val == 'Overdue': return 'background-color: #fee2e2; color: #991b1b;'
            if val == 'Sent Reminder': return 'background-color: #fef3c7; color: #92400e;'
            return ''

        st.dataframe(
            f_df[['id', 'company', 'date', 'due_date_display', 'amount', 'received_amount', 'status']]
            .style.applymap(highlight_st, subset=['status']).format({'amount': '₪{:,.2f}', 'received_amount': '₪{:,.2f}'}),
            use_container_width=True, hide_index=True
        )

    st.divider()

    # --- 5. BATCH EXECUTE (V) ---
    with st.expander("⚡ Batch Close as Paid", expanded=False):
        batch_df = f_df[['id', 'company', 'amount', 'status']].copy()
        batch_df['Select'] = False
        edit_batch = st.data_editor(batch_df, column_config={"Select": st.column_config.CheckboxColumn("Select"), "id": None}, hide_index=True, use_container_width=True)
        
        if st.button("Confirm Paid for Selected", use_container_width=True):
            selected = edit_batch[edit_batch['Select'] == True]
            for _, r in selected.iterrows():
                supabase.table("billing_history").update({"status": "Paid", "received_amount": float(r['amount'])}).eq("id", int(r['id'])).execute()
            st.success("Batch Update Done!")
            time.sleep(1); st.rerun()

else:
    st.info("No data available.")
