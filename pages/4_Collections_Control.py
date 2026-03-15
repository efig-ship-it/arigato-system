st.divider()
    st.subheader("⚡ Batch Execute Launch (Multi-Edit)")
    
    # 1. הכנת הנתונים לטבלה
    bulk = f_sorted[['id', 'company', 'due_date', 'amount', 'received_amount']].copy()
    bulk['Select'] = False
    
    # 2. עריכת הטבלה (Data Editor)
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

    # 3. כפתור הביצוע
    if st.button("🚀 Execute Batch Update"):
        rows_to_update = sel_bulk[sel_bulk['Select'] == True]
        
        if rows_to_update.empty:
            st.warning("Please select at least one row using the checkbox.")
        else:
            for _, row in rows_to_update.iterrows():
                total_amt = float(row['amount'])
                input_received = float(row['received_amount'])
                
                # --- הלוגיקה שביקשת ---
                # אם הסכום שהוזן הוא 0 או לא שונה מהמקור (והמשתמש רק סימן V), ניקח את הכל
                # אם המשתמש שינה את הסכום למשהו אחר, ניקח את מה שהוא רשם
                if input_received == 0:
                    final_received = total_amt
                else:
                    final_received = input_received
                
                new_balance = total_amt - final_received
                
                # קביעת סטטוס אוטומטי
                if new_balance <= 0:
                    final_status = "Paid"
                else:
                    final_status = "Partial"
                
                # עדכון ב-Supabase
                supabase.table("billing_history").update({
                    "status": final_status, 
                    "received_amount": final_received,
                    "balance": new_balance
                }).eq("id", row['id']).execute()
                
                # תיעוד ביומן
                add_log_entry(row['id'], f"Batch Update: Received {final_received}$. Status: {final_status}")
            
            st.success(f"Successfully processed {len(rows_to_update)} updates.")
            time.sleep(1)
            st.rerun()
