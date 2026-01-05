import streamlit as st
import pandas as pd
import numpy as np
import re

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
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Load Masterlife - Gốc 1625 hồ sơ
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # --- TẦNG 3: TÍNH TOÁN TRỰC TIẾP TỪ MASTERLIFE (ĐÃ CHUẨN) ---
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
        mkt_sum = pd.DataFrame({
            "Hạng mục": ["Tổng Lead thô (MKT File)", "Lead hợp lệ (Đã lên CRM)", "Lead rác"],
            "Số lượng": [len(df_mkt), len(matched_mkt), len(df_mkt) - len(matched_mkt)],
            "Tỷ lệ": ["100%", f"{(len(matched_mkt)/len(df_mkt)*100):.1f}%", f"{((len(df_mkt)-len(matched_mkt))/len(df_mkt)*100):.1f}%"]
        })
        st.table(mkt_sum)

    with t2:
        st.subheader("Ma trận Trạng thái Chi tiết trên CRM")
        
        # 1. NÚT LỌC STAGE
        all_stages = sorted(df_crm['STAGE'].dropna().unique())
        sel_stage = st.multiselect("🔍 Lọc theo STAGE (Bước):", options=all_stages, default=all_stages)
        
        # 2. XỬ LÝ HIỂN THỊ STATUS CHI TIẾT (KHÔNG GỘP)
        df_c_filtered = df_crm[df_crm['STAGE'].isin(sel_stage)] if sel_stage else df_crm
        
        # Chuẩn hóa nguồn cho CRM
        df_c_filtered['SOURCE_STD'] = df_c_filtered['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else '2. Funnel')
        
        # Tạo bảng ma trận với STATUS nguyên bản
        pivot_crm = df_c_filtered.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)
        
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)
        st.caption(f"Đang hiển thị {len(df_c_filtered):,} hồ sơ trên CRM theo các Stage đã chọn.")

    with t3:
        st.subheader("Hiệu suất Doanh thu (100% Masterlife Data)")
        summary_ml = df_ml.groupby('SOURCE_REPORT')['REV'].agg(['sum', 'count']).reset_index()
        summary_ml.columns = ['Nguồn', 'Tổng Doanh Thu', 'Số hồ sơ chốt']
        st.dataframe(summary_ml.style.format({"Tổng Doanh Thu": "${:,.0f}"}), use_container_width=True)
        
        c1, c2 = st.columns(2)
        c1.success(f"Tổng doanh thu: ${df_ml['REV'].sum():,.0f}")
        c2.success(f"Tổng hồ sơ: {len(df_ml):,}")

# SIDEBAR
st.sidebar.header("Upload Files")
f1 = st.sidebar.file_uploader("1. Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
