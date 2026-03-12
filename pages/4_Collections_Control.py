import streamlit as st
import pandas as pd
import time
from app import get_cloud_history, supabase, add_log_entry

st.title("Operations Control 🔍")
df_raw = get_cloud_history()
if not df_raw.empty:
    cf1, cf2 = st.columns(2)
    c_sel = cf1.multiselect("Search Companies", sorted(df_raw['company'].unique()))
    c_due = cf2.date_input("Filter Due Date", value=(df_raw['due_date_obj'].min(), df_raw['due_date_obj'].max()))
    f_df = df_raw.copy()
    if c_sel: f_df = f_df[f_df['company'].isin(c_sel)]
    if isinstance(c_due, tuple) and len(c_due) == 2: f_df = f_df[(f_df['due_date_obj'] >= c_due[0]) & (f_df['due_date_obj'] <= c_due[1])]
    
    def highlight_st(val):
        if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
        if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold; border: 1px solid #e53e3e;'
        if val == 'Sent Reminder': return 'background-color: #fefcbf; color: #744210; font-weight: bold;'
        return ''
    st.dataframe(f_df[['id', 'company', 'date_sent_str', 'due_date', 'amount', 'received_amount', 'status']].style.applymap(highlight_st, subset=['status']), use_container_width=True, hide_index=True)
    
    st.divider(); st.subheader("Audit & Documentation")
    f_sorted = f_df.sort_values(by=['due_date_obj', 'company'])
    opts = f_sorted.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.0f})", axis=1).tolist()
    opt_to_id = dict(zip(opts, f_sorted['id'].tolist()))
    sel_l = st.selectbox("Select Record for Detail:", opts)
    if sel_l:
        sid = opt_to_id[sel_l]; row_data = df_raw[df_raw['id'] == sid].iloc[0]
        if str(row_data['notes']) != 'None':
            for line in str(row_data['notes']).split('\n'): st.markdown(f"<div class='log-box'>{line}</div>", unsafe_allow_html=True)
        ci1, ci2, ci3 = st.columns([2, 1, 1])
        with ci1: ent = st.text_input("New Note Entry:")
        with ci2: rec = st.number_input("Received:", value=float(row_data['received_amount']), key=f"r_{sid}")
        with ci3: nst = st.selectbox("Status Update:", ["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"], index=["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder"].index(row_data['status']), key=f"s_{sid}")
        if st.button("Save Update"):
            if ent: add_log_entry(sid, ent)
            supabase.table("billing_history").update({"status": nst, "received_amount": float(rec)}).eq("id", sid).execute()
            st.success("Updated."); time.sleep(0.5); st.rerun()

    st.divider(); st.subheader("⚡ Batch Execute Launch (Multi-Edit)")
    bulk = f_sorted[['id', 'company', 'due_date', 'amount', 'received_amount']].copy(); bulk['Select'] = False
    sel_bulk = st.data_editor(bulk, column_config={"Select": st.column_config.CheckboxColumn("V", default=False), "id": None}, hide_index=True, use_container_width=True)
    if st.button("🚀 Execute Batch Update"):
        for _, row in sel_bulk[sel_bulk['Select']].iterrows():
            f_rec = row['received_amount'] if row['received_amount'] > 0 else row['amount']
            supabase.table("billing_history").update({"status": "Paid", "received_amount": f_rec}).eq("id", row['id']).execute()
            add_log_entry(row['id'], "Batch Execute: Settled.")
        st.success("Batch done."); time.sleep(1); st.rerun()
