import streamlit as st
import pandas as pd
import time
from app import get_cloud_history, supabase, add_log_entry

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

st.title("Operations Control 🔍")

df_raw = get_cloud_history()

if not df_raw.empty:
    cf1, cf2 = st.columns(2)
    c_sel = cf1.multiselect("Search Companies", sorted(df_raw['company'].unique()))
    
    # Filter dates safely
    try:
        min_d = df_raw['due_date_obj'].min()
        max_d = df_raw['due_date_obj'].max()
        c_due = cf2.date_input("Filter Due Date", value=(min_d, max_d))
    except:
        c_due = None
    
    f_df = df_raw.copy()
    if c_sel: 
        f_df = f_df[f_df['company'].isin(c_sel)]
    if isinstance(c_due, tuple) and len(c_due) == 2: 
        f_df = f_df[(f_df['due_date_obj'] >= c_due[0]) & (f_df['due_date_obj'] <= c_due[1])]
    
    def highlight_st(val):
        if val == 'Paid': return 'background-color: #e6fffa; color: #234e52; font-weight: bold;'
        if val == 'Overdue': return 'background-color: #fff5f5; color: #e53e3e; font-weight: bold; border: 1px solid #e53e3e;'
        if val == 'Sent Reminder': return 'background-color: #fefcbf; color: #744210; font-weight: bold;'
        if val == 'Partial': return 'background-color: #e3f2fd; color: #0d47a1; font-weight: bold;'
        return ''

    st.dataframe(f_df[['id', 'company', 'date', 'due_date', 'amount', 'received_amount', 'status']].style.applymap(highlight_st, subset=['status']), use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("Audit & Documentation")
    f_sorted = f_df.sort_values(by=['due_date_obj', 'company'])
    opts = f_sorted.apply(lambda r: f"[{r['due_date']}] - {r['company']} (${r['amount']:,.0f})", axis=1).tolist()
    opt_to_id = dict(zip(opts, f_sorted['id'].tolist()))
    
    sel_l = st.selectbox("Select Record for Detail:", opts)
    if sel_l:
        sid = opt_to_id[sel_l]
        row_data = df_raw[df_raw['id'] == sid].iloc[0]
        
        if str(row_data['notes']) != 'None':
            for line in str(row_data['notes']).split('\n'): 
                if line.strip(): st.markdown(f"<div style='background:#f1f5f9; padding:8px; border-radius:5px; margin-bottom:5px;'>{line}</div>", unsafe_allow_html=True)
        
        ci1, ci2, ci3 = st.columns([2, 1, 1])
        with ci1: ent = st.text_input("New Note Entry:")
        with ci2: rec = st.number_input("Received:", value=float(row_data['received_amount']), key=f"r_{sid}")
        with ci3: nst = st.selectbox("Status Update:", ["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder", "Partial"], index=["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder", "Partial"].index(row_data['status']) if row_data['status'] in ["Sent", "Paid", "Overdue", "In Dispute", "Sent Reminder", "Partial"] else 0, key=f"s_{sid}")
        
        if st.button("Save Update"):
            if ent: add_log_entry(sid, ent)
            # עדכון ללא עמודת balance ליתר ביטחון
            supabase.table("billing_history").update({
                "status": nst, 
                "received_amount": float(rec)
            }).eq("id", sid).execute()
            st.success("Updated.")
            time.sleep(0.5); st.rerun()

    st.divider()
    st.subheader("⚡ Batch Execute Launch (Multi-Edit)")
    
    bulk = f_sorted[['id', 'company', 'due_date', 'amount', 'received_amount']].copy()
    bulk['Select'] = False
    
    sel_bulk = st.data_editor(
        bulk, 
        column_config={
            "Select": st.column_config.CheckboxColumn("V", default=False),
            "id": None,
            "received_amount": st.column_config.NumberColumn("Received ($)", format="$%.2f"),
            "amount": st.column_config.NumberColumn("Total ($)", format="$%.2f", disabled=True)
        }, 
        hide_index=True, use_container_width=True
    )

    if st.button("🚀 Execute Batch Update"):
        rows_to_update = sel_bulk[sel_bulk['Select'] == True]
        
        if rows_to_update.empty:
            st.warning("Please select at least one row.")
        else:
            try:
                for _, row in rows_to_update.iterrows():
                    total_amt = float(row['amount'])
                    input_received = float(row['received_amount'])
                    
                    # הלוגיקה שלך: אם 0 -> הכל. אם לא -> מה שכתבת.
                    if input_received == 0:
                        final_received = total_amt
                    else:
                        final_received = input_received
                    
                    final_status = "Paid" if (total_amt - final_received) <= 0 else "Partial"
                    
                    # עדכון רק של עמודות שאנחנו בטוחים שקיימות
                    supabase.table("billing_history").update({
                        "status": final_status, 
                        "received_amount": final_received
                    }).eq("id", int(row['id'])).execute()
                    
                    add_log_entry(row['id'], f"Batch Update: Received {final_received}$. Status: {final_status}")
                
                st.success("Batch Processing Complete.")
                time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"Database Error: {e}")
