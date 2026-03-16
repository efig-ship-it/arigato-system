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
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0.0)
        df['balance'] = df['amount'] - df['received_amount']
        df['due_date_display'] = pd.to_datetime(df['due_date'], errors='coerce').dt.strftime('%d/%m/%Y')
        return df
    return pd.DataFrame()

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

st.markdown("""
    <style>
    .tuesday-header {
        font-family: 'Helvetica Neue', Arial, sans-serif;
        color: #1E3A8A; font-size: 32px; font-weight: bold;
        letter-spacing: -1px; border-bottom: 2px solid #1E3A8A; margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)
st.title("Operations Control 🔍")

# --- 3. DATA & STATE ---
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False

df_raw = get_cloud_history()

if not df_raw.empty:
    # פילטרים בראש העמוד
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1: c_sel = st.multiselect("חפש חברה:", sorted(df_raw['company'].unique()))
    with f2: s_sel = st.multiselect("סינון סטטוס:", sorted(df_raw['status'].unique()))
    with f3: 
        # כפתור ה-Toggle למעבר בין מצבים
        if st.button("🔄 Switch to " + ("View Mode" if st.session_state.edit_mode else "Edit Mode"), use_container_width=True):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()

    f_df = df_raw.copy()
    if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
    if s_sel: f_df = f_df[f_df['status'].isin(s_sel)]

    # --- 4. DISPLAY LOGIC (VIEW vs EDIT) ---
    
    if st.session_state.edit_mode:
        # --- מוד עריכה (Live Editor) ---
        st.info("💡 **Edit Mode Active:** You can change Status and Received amount directly in the table.")
        edited_df = st.data_editor(
            f_df[['id', 'company', 'due_date_display', 'amount', 'received_amount', 'status']],
            column_config={
                "id": None,
                "company": st.column_config.TextColumn("Company", disabled=True),
                "due_date_display": st.column_config.TextColumn("Due Date", disabled=True),
                "amount": st.column_config.NumberColumn("Billed", format="₪%.2f", disabled=True),
                "received_amount": st.column_config.NumberColumn("Received", format="₪%.2f", min_value=0),
                "status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Sent", "Paid", "Overdue", "Partial", "Sent Reminder"],
                    required=True
                )
            },
            hide_index=True, use_container_width=True, key="main_editor"
        )

        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            changes = 0
            for i in range(len(edited_df)):
                row_id = int(edited_df.iloc[i]['id'])
                orig = df_raw[df_raw['id'] == row_id].iloc[0]
                new_s = edited_df.iloc[i]['status']
                new_r = float(edited_df.iloc[i]['received_amount'])
                
                if new_s != orig['status'] or new_r != orig['received_amount']:
                    supabase.table("billing_history").update({"status": new_s, "received_amount": new_r}).eq("id", row_id).execute()
                    add_log_entry(row_id, f"Edited: {new_s} | ₪{new_r}")
                    changes += 1
            if changes > 0:
                st.success(f"Updated {changes} records!"); time.sleep(1); st.rerun()
    
    else:
        # --- מוד תצוגה (צבעוני ומעוצב) ---
        def highlight_st(val):
            if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
            if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold;'
            if val == 'Partial': return 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold;'
            if val == 'Sent Reminder': return 'background-color: #fef3c7; color: #92400e; font-weight: bold;'
            return ''

        st.dataframe(
            f_df[['id', 'company', 'date', 'due_date_display', 'amount', 'received_amount', 'status']]
            .style.applymap(highlight_st, subset=['status']).format({
                'amount': '₪{:,.2f}',
                'received_amount': '₪{:,.2f}'
            }),
            use_container_width=True, hide_index=True
        )

    st.divider()

    # --- 5. BATCH ACTIONS ---
    with st.expander("⚡ Batch Execute (V)", expanded=False):
        bulk_df = f_df[['id', 'company', 'amount', 'received_amount']].copy()
        bulk_df['Select'] = False
        batch_edit = st.data_editor(
            bulk_df,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", default=False),
                "id": None,
                "amount": st.column_config.NumberColumn("Billed", format="₪%.2f", disabled=True),
                "received_amount": st.column_config.NumberColumn("Current Received", format="₪%.2f", disabled=True)
            },
            hide_index=True, use_container_width=True, key="batch_editor"
        )
        if st.button("🚀 Close Selected as 'Paid'", use_container_width=True):
            to_pay = batch_edit[batch_edit['Select'] == True]
            for _, r in to_pay.iterrows():
                supabase.table("billing_history").update({"status": "Paid", "received_amount": float(r['amount'])}).eq("id", int(r['id'])).execute()
                add_log_entry(r['id'], "Batch Execute: Paid")
            st.success("Updated!"); time.sleep(1); st.rerun()

    # --- 6. NOTES ---
    with st.expander("💬 Audit Logs & Manual Notes", expanded=False):
        sel_comp = st.selectbox("Company Hist:", ["Select..."] + sorted(f_df['company'].unique().tolist()))
        if sel_comp != "Select...":
            sub = f_df[f_df['company'] == sel_comp]
            for _, r in sub.iterrows():
                st.write(f"**Transaction ID: {r['id']} ({r['date']})**")
                if r['notes']:
                    for l in str(r['notes']).split('\n'):
                        if l.strip(): st.info(l)
                n_note = st.text_input(f"Add note for ID {r['id']}:", key=f"note_in_{r['id']}")
                if st.button("Add Note", key=f"btn_note_{r['id']}"):
                    add_log_entry(r['id'], n_note)
                    st.rerun()
else:
    st.info("No data.")
