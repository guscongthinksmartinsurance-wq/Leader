import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px

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
    
    # Load Masterlife - Gốc 1625 hồ sơ
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # --- TẦNG 3: XỬ LÝ TRỰC TIẾP TỪ MASTERLIFE ---
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    def classify_ml_source(src):
        s = str(src).upper().strip()
        if 'CC' in s: return '1. Cold Call'
        if 'SF' in s: return '2. Funnel'
        return '3. Khác/Trống'
    df_ml['SOURCE_REPORT'] = df_ml['SOURCE'].apply(classify_ml_source)

    # --- GIAO DIỆN ---
    st.title("📊 TMC Strategic Dashboard")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing Efficiency", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Báo cáo chất lượng Lead thô")
        df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
        df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
        matched_mkt = df_mkt[df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID'])]
        
        count_tho = len(df_mkt)
        count_hop_le = len(matched_mkt)
        count_rac = count_tho - count_hop_le

        col1, col2 = st.columns([1, 1])
        with col1:
            mkt_sum = pd.DataFrame({
                "Hạng mục": ["Tổng Lead thô", "Lead hợp lệ", "Lead rác"],
                "Số lượng": [count_tho, count_hop_le, count_rac],
                "Tỷ lệ": ["100%", f"{(count_hop_le/count_tho*100):.1f}%", f"{(count_rac/count_tho*100):.1f}%"]
            })
            st.table(mkt_sum)
        
        with col2:
            fig1 = px.pie(mkt_sum, values='Số lượng', names='Hạng mục', 
                          color='Hạng mục',
                          color_discrete_map={'Tổng Lead thô':'#636EFA', 'Lead hợp lệ':'#00CC96', 'Lead rác':'#EF553B'},
                          title="Tỷ lệ phân loại Lead Marketing")
            st.plotly_chart(fig1, use_container_width=True)

    with t2:
        st.subheader("Ma trận Trạng thái Chi tiết trên CRM")
        all_stages = sorted(df_crm['STAGE'].dropna().unique())
        sel_stage = st.multiselect("🔍 Lọc theo STAGE:", options=all_stages, default=all_stages)
        df_c_f = df_crm[df_crm['STAGE'].isin(sel_stage)] if sel_stage else df_crm
        
        df_c_f['SOURCE_STD'] = df_c_f['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else '2. Funnel')
        pivot_crm = df_c_f.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)

        # Biểu đồ cột Status
        status_counts = df_c_f['STATUS'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Số lượng']
        fig2 = px.bar(status_counts, x='Status', y='Số lượng', 
                      title="Số lượng Lead theo Status",
                      color='Status', text_auto=True)
        st.plotly_chart(fig2, use_container_width=True)

    with t3:
        st.subheader("Hiệu suất Doanh thu (100% Masterlife Data)")
        summary_ml = df_ml.groupby('SOURCE_REPORT')['REV'].agg(['sum', 'count']).reset_index()
        summary_ml.columns = ['Nguồn', 'Tổng Doanh Thu', 'Số hồ sơ chốt']
        
        col_t3_1, col_t3_2 = st.columns([1, 1])
        with col_t3_1:
            st.dataframe(summary_ml.style.format({"Tổng Doanh Thu": "${:,.0f}"}), use_container_width=True)
            st.metric("TỔNG DOANH THU", f"${df_ml['REV'].sum():,.0f}")
            st.metric("TỔNG HỒ SƠ", f"{len(df_ml):,}")

        with col_t3_2:
            # Biểu đồ tròn doanh số
            fig3 = px.pie(summary_ml, values='Tổng Doanh Thu', names='Nguồn',
                          title=f"Cơ cấu Doanh số (Tổng: ${df_ml['REV'].sum():,.0f})",
                          hole=0.4) # Dạng Donut cho hiện đại
            st.plotly_chart(fig3, use_container_width=True)

# SIDEBAR
st.sidebar.header("Upload Files")
f1 = st.sidebar.file_uploader("1. Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
