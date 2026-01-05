import streamlit as st
import pandas as pd
import numpy as np
import re

# --- 1. HÀM LÀM SẠCH (GIỮ NGUYÊN) ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_name_final(name):
    if pd.isna(name): return ""
    return re.sub(r'\s+', ' ', str(name).strip().upper())

# --- 2. ENGINE XỬ LÝ TẬP TRUNG VÀO MASTERLIFE ---
def process_data(f_mkt, f_crm, f_ml):
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Đọc Masterlife - Giữ đúng 1625 hồ sơ của anh
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()
    
    # Làm sạch cột doanh thu ngay lập tức
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)

    # CHUẨN HÓA CRM ĐỂ LÀM BỘ TRA CỨU (KHÔNG LÀM GỐC)
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    
    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source_std)

    # Tạo bộ từ điển tra cứu (Chỉ lấy 1 kết quả duy nhất cho mỗi ID/Tên)
    id_to_source = df_crm[df_crm['MATCH_ID'] != ''].drop_duplicates('MATCH_ID').set_index('MATCH_ID')['SOURCE_STD'].to_dict()
    name_to_source = df_crm.drop_duplicates('MATCH_NAME').set_index('MATCH_NAME')['SOURCE_STD'].to_dict()

    # TRA CỨU NGUỒN CHO 1625 HỒ SƠ MASTERLIFE
    def assign_source(row):
        l_id = clean_id_final(row.get('LEAD ID'))
        c_name = clean_name_final(row.get('CONTACT NAME'))
        # Ưu tiên ID, hụt ID mới dùng Tên
        if l_id in id_to_source: return id_to_source[l_id]
        if c_name in name_to_source: return name_to_source[c_name]
        return '4. Ngoài CRM / Lỗi ID'

    df_ml['SOURCE_FINAL'] = df_ml.apply(assign_source, axis=1)

    # --- HIỂN THỊ (TẦNG 1 & 2 GIỮ NGUYÊN - TẦNG 3 ĐIỀU CHỈNH) ---
    st.title("📊 TMC Strategic Dashboard")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Báo cáo chất lượng Lead thô")
        st.write(f"Tổng Lead thô: {len(df_mkt):,}")
        # Bảng Table Tầng 1 của anh ở đây...
        st.table(pd.DataFrame({"Hạng mục": ["Lead MKT"], "Số lượng": [len(df_mkt)]}))

    with t2:
        st.subheader("Ma trận Trạng thái Lead (CRM)")
        pivot_crm = df_crm.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)
        st.dataframe(pivot_crm, use_container_width=True)

    with t3:
        st.subheader("Doanh thu thực tế từ Masterlife (Khớp 1625 hồ sơ)")
        
        # Bảng doanh thu tách dòng Cold Call và Funnel
        summary = df_ml.groupby('SOURCE_FINAL')['REV'].agg(['sum', 'count'])
        summary.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        summary = summary.sort_index() # Sắp xếp để hiện Cold Call, Funnel thứ tự
        
        st.dataframe(summary.style.format("${:,.0f}"), use_container_width=True)
        
        # Dòng tổng kết để đối soát
        total_ml_rev = df_ml['REV'].sum()
        total_ml_count = len(df_ml)
        
        c1, c2 = st.columns(2)
        c1.warning(f"Tổng Doanh thu Masterlife: ${total_ml_rev:,.0f}")
        c2.warning(f"Tổng Số hồ sơ Masterlife: {total_ml_count}")

        if total_ml_count != 1625:
            st.error(f"Cảnh báo: File Masterlife đang nhận {total_ml_count} dòng, anh kiểm tra lại filter trong file gốc.")

# SIDEBAR
st.sidebar.header("Upload Files")
f1 = st.sidebar.file_uploader("1. Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
