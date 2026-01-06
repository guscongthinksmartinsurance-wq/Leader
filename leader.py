import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px
import io

# --- 1. HÀM LÀM SẠCH ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_phone_9(phone):
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 2. ENGINE XỬ LÝ ---
def process_data(f_mkt, f_crm, f_ml):
    # Đọc dữ liệu
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # TẦNG 3: SALES (GỐC MASTERLIFE)
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    df_ml['SOURCE_REPORT'] = df_ml['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else ('2. Funnel' if 'SF' in str(x).upper() else '3. Khác'))
    summary_ml = df_ml.groupby('SOURCE_REPORT')['REV'].agg(['sum', 'count']).reset_index()
    summary_ml.columns = ['Nguồn', 'Tổng Doanh Thu', 'Số hồ sơ chốt']

    # TẦNG 1: MARKETING
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
    matched_mkt = df_mkt[df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID'])]
    mkt_summary_df = pd.DataFrame({
        "Hạng mục": ["Tổng Lead thô", "Lead hợp lệ", "Lead rác"],
        "Số lượng": [len(df_mkt), len(matched_mkt), len(df_mkt) - len(matched_mkt)]
    })

    # TẦNG 2: CRM
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else '2. Funnel')
    pivot_crm = df_crm.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)

    # --- HIỂN THỊ ---
    st.title("📊 TMC Strategic Dashboard")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        c1, c2 = st.columns(2)
        c1.table(mkt_summary_df)
        c2.plotly_chart(px.pie(mkt_summary_df, values='Số lượng', names='Hạng mục', title="Tỷ lệ Lead MKT"), use_container_width=True)

    with t2:
        # Cách hiện bảng an toàn, không bị crash nếu thiếu matplotlib
        try:
            st.dataframe(pivot_crm.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)
        except:
            st.dataframe(pivot_crm, use_container_width=True)
            
        status_counts = df_crm['STATUS'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Số lượng']
        st.plotly_chart(px.bar(status_counts, x='Status', y='Số lượng', title="Số lượng theo Status", text_auto=True), use_container_width=True)

    with t3:
        c31, c32 = st.columns(2)
        with c31:
            st.dataframe(summary_ml.style.format({"Tổng Doanh Thu": "${:,.0f}"}), use_container_width=True)
            st.metric("TỔNG DOANH THU", f"${df_ml['REV'].sum():,.0f}")
            st.metric("TỔNG HỒ SƠ", f"{len(df_ml):,}")
        with c32:
            st.plotly_chart(px.pie(summary_ml, values='Tổng Doanh Thu', names='Nguồn', title="Cơ cấu Doanh số", hole=0.4), use_container_width=True)

    # EXPORT EXCEL
    st.sidebar.markdown("---")
    if st.sidebar.button("📥 Export Report (3 Sheets)"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            mkt_summary_df.to_excel(writer, sheet_name='Marketing', index=False)
            pivot_crm.to_excel(writer, sheet_name='CRM_Pipeline')
            summary_ml.to_excel(writer, sheet_name='Sales_Performance', index=False)
        st.sidebar.download_button(label="💾 Tải file Excel", data=buffer.getvalue(), file_name="Bao_Cao_TMC.xlsx")

# SIDEBAR
f1 = st.sidebar.file_uploader("1. MKT", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])
if f1 and f2 and f3:
    process_data(f1, f2, f3)
