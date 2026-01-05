import streamlit as st
import pandas as pd
import numpy as np
import re

# --- 1. LÀM SẠCH ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_name_final(name):
    if pd.isna(name): return ""
    return re.sub(r'\s+', ' ', str(name).strip().upper())

# --- 2. ENGINE XỬ LÝ ---
def process_data(f_mkt, f_crm, f_ml):
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Load Masterlife
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # CHUẨN HÓA CRM (Xóa trùng trước khi tạo bộ tra cứu)
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    
    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source_std)

    # TẠO BỘ TRA CỨU 1-1 TUYỆT ĐỐI (Dùng Series để map)
    # Nếu trùng ID/Tên, chỉ lấy dòng đầu tiên xuất hiện
    map_id_to_source = df_crm[df_crm['MATCH_ID'] != ''].drop_duplicates('MATCH_ID').set_index('MATCH_ID')['SOURCE_STD']
    map_name_to_source = df_crm.drop_duplicates('MATCH_NAME').set_index('MATCH_NAME')['SOURCE_STD']

    # XỬ LÝ TRÊN MASTERLIFE (GỐC)
    # Bước 1: Tính doanh thu trước
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    
    # Bước 2: Chuẩn hóa ID/Tên trong Masterlife để tra cứu
    df_ml['ML_ID_CLEAN'] = df_ml['LEAD ID'].apply(clean_id_final)
    df_ml['ML_NAME_CLEAN'] = df_ml['CONTACT NAME'].apply(clean_name_final)

    # Bước 3: Gán nguồn (Sử dụng Map - Không tạo thêm dòng)
    df_ml['SOURCE_FINAL'] = df_ml['ML_ID_CLEAN'].map(map_id_to_source)
    # Nếu ID chưa có nguồn, mới dùng Tên để điền vào những chỗ còn trống (NaN)
    df_ml['SOURCE_FINAL'] = df_ml['SOURCE_FINAL'].fillna(df_ml['ML_NAME_CLEAN'].map(map_name_to_source))
    # Còn lại là Ngoài CRM
    df_ml['SOURCE_FINAL'] = df_ml['SOURCE_FINAL'].fillna('4. Ngoài CRM / Lỗi ID')

    # --- HIỂN THỊ (GIỮ NGUYÊN GIAO DIỆN) ---
    st.title("📊 TMC Strategic Dashboard - Anti-Duplication Edition")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t3:
        st.subheader("Doanh thu thực tế (Fixed 1625 Rows)")
        # Thống kê dựa trên df_ml gốc
        summary = df_ml.groupby('SOURCE_FINAL')['REV'].agg(['sum', 'count'])
        summary.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        summary['ARPL'] = summary['Tổng Doanh Thu'] / summary['Số hồ sơ chốt']
        st.dataframe(summary.style.format("${:,.0f}"), use_container_width=True)
        
        st.warning(f"Tổng doanh thu Masterlife: ${df_ml['REV'].sum():,.0f} | Tổng số hồ sơ: {len(df_ml):,}")

    # (Giữ code Tầng 1 và Tầng 2 như cũ)
