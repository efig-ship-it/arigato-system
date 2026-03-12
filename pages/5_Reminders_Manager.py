import streamlit as st
import pandas as pd
import smtplib, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app import get_cloud_history, supabase

# --- SIDEBAR BRANDING ---
st.sidebar.markdown('<p class="tuesday-header">Tuesday</p>', unsafe_allow_html=True)

# --- CSS & ANIMATIONS (צ'קלקות בלבד) ---
st.markdown("""
    <style>
    .police-lights {
        background: linear-gradient(90deg, rgba(255,0,0,1) 0%, rgba(0,0,255,1) 100%);
        height: 8px; border-radius: 4px; animation: blinker 0.2s linear infinite; margin: 10px 0;
    }
    @keyframes blinker { 50% { opacity: 0; } }
    </style>
""", unsafe_allow_html=True)

# --- CENTRAL LAYOUT ---
left_pad, center_col, right_pad = st.columns([0.1, 0.8, 0.1])

with center_col:
    st.title("Reminders Manager 🚨")
    
    df_history = get_cloud_history()

    if df_history.empty:
        st.info("No billing history found.")
    else:
        today = datetime.now().date()
        overdue_df = df_history[(df_history['status'] != 'Paid') & (df_history['due_date_obj'] < today)].copy()

        if overdue_df.empty:
            st.success("All clear! No overdue payments. ☕")
        else:
            st.warning(f"Found {len(overdue_df)} Overdue Invoices.")
            
            overdue_df['Select'] = True
            edited_df = st.data_editor(
                overdue_df[['Select', 'company', 'amount', 'due_date', 'balance']],
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=["company", "amount", "due_date", "balance"],
                hide_index=True, use_container_width=True
            )

            st.divider()

            # הגדרות שליחה
            st.subheader("Send Official Reminders")
            c_auth, c_guide = st.columns([1.5, 1])
            with c_auth:
                u_m = st.text_input("Gmail Account")
                u_p = st.text_input("App Password", type="password")
            with c_guide:
                with st.expander("🔐 Guide"):
                    st.markdown("[Google App Passwords](https://myaccount.google.com/apppasswords)")

            # כפתור השליחה
            if st.button("🚨 EXECUTE COLLECTION DISPATCH", use_container_width=True):
                selected = edited_df[edited_df['Select'] == True]
                
                if selected.empty or not u_m or not u_p:
                    st.error("Missing selection or credentials.")
                else:
                    try:
                        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
                        server.login(u_m.strip(), u_p.strip().replace(" ",""))
                        
                        # הנה החלק של הספינר והצ'קלקה - רק בזמן השליחה!
                        status_msg = st.empty() 
                        
                        for i, row in selected.iterrows():
                            # חילוץ חודש ושנה
                            dt_obj = datetime.strptime(str(row['due_date']), "%Y-%m-%d")
                            month_name = dt_obj.strftime("%B")
                            year_val = dt_obj.year
                            
                            # הצגת הצ'קלקה והסטטוס
                            with status_msg.container():
                                st.markdown('<div class="police-lights"></div>', unsafe_allow_html=True)
                                st.write(f"🕵️‍♂️ **Tuesday is collecting from:** {row['company']}...")
                            
                            # בניית המייל
                            email_body = f"""שלום,
נכון להיום, התשלום עבור חודש {month_name} {year_val} טרם הוסדר, וזאת על אף שמועד התשלום חלף.
דוח חשבוניות פתוחות לתשלום נשלח בתחילת החודש.

אנא הסדירו את התשלום באופן מיידי ועדכנו אותנו עם ביצוע ההעברה.
אי־הסדרת התשלום עלולה להוביל לסגירת החשבון ולהפסקת השירות.

במידה והתשלום בוצע בימים האחרונים, אנא שלחו אישור העברה ופירוט חשבוניות רלוונטיות.

בברכה,
Tuesday Team"""

                            msg = MIMEMultipart()
                            msg['Subject'] = f"דרישת תשלום מיידית - {row['company']}"
                            msg['To'] = u_m # כאן מומלץ להחליף למייל הלקוח
                            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
                            server.send_message(msg)
                            
                            # עדכון דאטה בייס
                            supabase.table("billing_history").update({"status": "Reminder Sent"}).eq("company", row['company']).eq("due_date", row['due_date']).execute()
                            time.sleep(1) # רק כדי שתספיק לראות את הצ'קלקה עובדת
                        
                        server.quit()
                        status_msg.empty() # מעלים את הצ'קלקה בסיום
                        st.balloons()
                        st.success("All reminders sent!")
                        time.sleep(2); st.rerun()
                        
                    except Exception as e: st.error(f"Error: {e}")
