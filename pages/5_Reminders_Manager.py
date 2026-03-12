import streamlit as st
import pandas as pd
import time
from app import get_cloud_history, play_siren, supabase

st.title("Debt Recovery Board 🚨")
mf_rem = st.file_uploader("Upload Mailing List to unlock", type=['xlsx'], key="rem_f")
df_raw = get_cloud_history()
if not df_raw.empty:
    df_raw['balance'] = df_raw['amount'] - df_raw['received_amount']
    unpaid = df_raw[df_raw['balance'] > 0].copy(); unpaid['Select'] = False
    sel_rem = st.data_editor(unpaid[['Select', 'company', 'due_date', 'balance', 'id']], hide_index=True, use_container_width=True)
    can_send_rem = (mf_rem is not None) and (sel_rem['Select'].any())
    if st.button("🚀 Send Recovery Alerts", use_container_width=True, disabled=not can_send_rem):
        play_siren()
        sh_r = st.empty()
        with sh_r.container():
            st.markdown('<div class="siren-anim">🚨</div>', unsafe_allow_html=True)
            with st.spinner("Escalating..."):
                time.sleep(2)
                for i, row in sel_rem[sel_rem['Select']].iterrows():
                    supabase.table("billing_history").update({"status": "Sent Reminder"}).eq("id", row['id']).execute()
        sh_r.empty(); st.balloons(); st.rerun()
