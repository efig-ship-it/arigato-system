import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client
from datetime import datetime

# --- 1. חיבור לבסיס הנתונים (עצמאי לחלוטין) ---
@st.cache_resource
def init_connection():
    u = st.secrets["SUPABASE_URL"].strip().replace('"', '')
    k = st.secrets["SUPABASE_KEY"].strip().replace('"', '')
    return create_client(u, k)

supabase = init_connection()

def get_data():
    res = supabase.table("billing_history").select("*").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # המרת שדות למספרים ותאריכים
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
        df['received_amount'] = pd.to_numeric(df['received_amount'], errors='coerce').fillna(0)
        df['balance'] = df['amount'] - df['received_amount']
        # המרת תאריך לפורמט פייתון
        df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        df['month_year'] = df['date_dt'].dt.strftime('%m/%Y')
    return df

# --- 2. עיצוב הממשק ---
st.set_page_config(page_title="Tuesday | Analytics", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: bold; color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">Financial Performance Dashboard 📊</p>', unsafe_allow_html=True)

# כפתור ריענון בסרגל הצדי
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_resource.clear()
    st.rerun()

# --- 3. עיבוד נתונים ---
df = get_data()

if df.empty:
    st.warning("לא נמצאו נתונים להצגה. וודא שביצעת שליחות בעמוד 1.")
    st.stop()

# חישוב מדדים מרכזיים (KPIs)
total_billed = df['amount'].sum()
total_received = df['received_amount'].sum()
total_pending = df['balance'].sum()
collection_rate = (total_received / total_billed * 100) if total_billed > 0 else 0

# תצוגת כרטיסי מדדים
m1, m2, m3, m4 = st.columns(4)
m1.metric("סה\"כ חויב (Billed)", f"₪{total_billed:,.0f}")
m2.metric("סה\"כ נגבה (Collected)", f"₪{total_received:,.0f}")
m3.metric("יתרה פתוחה (Outstanding)", f"₪{total_pending:,.0f}", delta=f"{collection_rate:.1f}% גבייה", delta_color="normal")
m4.metric("מספר תיקים", len(df))

st.divider()

# --- 4. גרפים ---
c1, c2 = st.columns(2)

with c1:
    st.subheader("התפלגות לפי סטטוס")
    status_summary = df.groupby('status')['amount'].sum().reset_index()
    fig_pie = px.pie(status_summary, values='amount', names='status', 
                     hole=0.4, 
                     color='status',
                     color_discrete_map={'Paid':'#10B981', 'Sent':'#3B82F6', 'Overdue':'#EF4444', 'Partial':'#F59E0B'})
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.subheader("מגמת חיוב מול גבייה")
    trend_df = df.dropna(subset=['date_dt']).sort_values('date_dt')
    trend_df = trend_df.groupby('month_year').agg({'amount':'sum', 'received_amount':'sum'}).reset_index()
    
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(x=trend_df['month_year'], y=trend_df['amount'], name='חויב', marker_color='#3B82F6'))
    fig_trend.add_trace(go.Bar(x=trend_df['month_year'], y=trend_df['received_amount'], name='נגבה', marker_color='#10B981'))
    fig_trend.update_layout(barmode='group', xaxis_title="חודש/שנה")
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# --- 5. טבלת פיבוט - סיכום לפי חברה ---
st.subheader("ניתוח גבייה לפי חברה (Pivot Analysis)")

pivot_table = df.groupby('company').agg({
    'amount': 'sum',
    'received_amount': 'sum',
    'balance': 'sum',
    'id': 'count'
}).rename(columns={'id': 'חשבוניות'}).reset_index()

# חישוב אחוז גבייה פר חברה
pivot_table['% גבייה'] = (pivot_table['received_amount'] / pivot_table['amount'] * 100).round(1)
pivot_table = pivot_table.sort_values(by='balance', ascending=False)

# הצגת הטבלה עם עיצוב מותנה
st.dataframe(
    pivot_table.style.background_gradient(subset=['balance'], cmap="Reds")
    .format({'amount': '₪{:,.0f}', 'received_amount': '₪{:,.0f}', 'balance': '₪{:,.0f}', '% גבייה': '{:.1f}%'}),
    use_container_width=True, hide_index=True
)

# --- 6. 5 החייבים הגדולים ---
st.subheader("⚠️ 5 החייבים הגדולים ביותר")
top_5 = pivot_table[pivot_table['balance'] > 0].head(5)
if not top_5.empty:
    fig_debt = px.bar(top_5, x='company', y='balance', 
                      text='balance',
                      labels={'balance': 'חוב פתוח', 'company': 'חברה'},
                      color='balance', color_continuous_scale='Reds')
    fig_debt.update_traces(texttemplate='₪%{text:,.0f}', textposition='outside')
    st.plotly_chart(fig_debt, use_container_width=True)
else:
    st.success("אין חובות פתוחים במערכת!")
