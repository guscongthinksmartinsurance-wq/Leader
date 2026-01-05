import streamlit as st
import pandas as pd
import numpy as np
import re

# --- 1. LÀM SẠCH ĐỊNH DANH ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_name_final(name):
    if pd.isna(name): return ""
    return re.sub(r'\s+', ' ', str(name).strip().upper())

def clean_phone_9(phone):
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 2. ENGINE XỬ LÝ CHÍNH ---
def process_data(f_mkt, f_crm, f_ml):
    # Đọc dữ liệu
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Load Masterlife tìm header Target Premium
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row)

    # --- CHUẨN HÓA CRM (LÀM GỐC TRA CỨU) ---
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone_9)
    
    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source_std)

    # Khóa logic 1-1: Mỗi ID hoặc Tên chỉ lấy duy nhất 1 nguồn đầu tiên thấy trong CRM
    crm_id_map = df_crm[df_crm['MATCH_ID'] != ''].drop_duplicates('MATCH_ID').set_index('MATCH_ID')['SOURCE_STD'].to_dict()
    crm_name_map = df_crm.drop_duplicates('MATCH_NAME').set_index('MATCH_NAME')['SOURCE_STD'].to_dict()

    # --- XỬ LÝ TẦNG 3: TRÊN GỐC MASTERLIFE (1625 DÒNG) ---
    def assign_source_to_ml(row):
        l_id = clean_id_final(row.get('LEAD ID'))
        c_name = clean_name_final(row.get('CONTACT NAME'))
        if l_id in crm_id_map: return crm_id_map[l_id]
        if c_name in crm_name_map: return crm_name_map[c_name]
        return '4. Ngoài CRM / Lỗi ID'

    # Tính doanh thu chuẩn từ cột Target Premium
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    # Gán nhãn nguồn cho từng dòng doanh thu
    df_ml['SOURCE_FINAL'] = df_ml.apply(assign_source_to_ml, axis=1)

    # --- HIỂN THỊ (GIAO DIỆN 3 TẦNG ỔN ĐỊNH) ---
    st.title("📊 TMC Strategic Dashboard - Final Verified")
    
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing Efficiency", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Chất lượng Data Marketing")
        df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
        df_mkt['MATCH_PHONE'] = df_mkt['CELLPHONE'].apply(clean_phone_9)
        matched_mkt = df_mkt[df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID']) | df_mkt['MATCH_PHONE'].isin(df_crm['MATCH_PHONE'])]
        mkt_sum = pd.DataFrame({
            "Hạng mục": ["Tổng Lead thô (MKT File)", "Lead hợp lệ (Đã lên CRM)", "Lead rác"],
            "Số lượng": [len(df_mkt), len(matched_mkt), len(df_mkt) - len(matched_mkt)],
            "Tỷ lệ": ["100%", f"{(len(matched_mkt)/len(df_mkt)*100):.1f}%", f"{((len(df_mkt)-len(matched_mkt))/len(df_mkt)*100):.1f}%"]
        })
        st.table(mkt_sum)

    with t2:
        st.subheader("Ma trận Trạng thái Lead trên CRM")
        status_map = {'Done (100%)': '✅ Won (100%)', 'Done (50%)': '⏳ Won (50%)', 'Cold (5%)': 'Pipeline', 'Unidentified (10%)': 'Pipeline', 'Follow Up (50%)': 'Pipeline', 'Interest (75%)': 'Pipeline', 'Hot Interest (85%)': 'Pipeline', 'Stop (0%)': '❌ Lost/Stop'}
        df_crm['GROUP_STATUS'] = df_crm['STATUS'].map(status_map).fillna('Khác')
        sel_stage = st.multiselect("Lọc Stage:", options=df_crm['STAGE'].unique())
        df_c_f = df_crm if not sel_stage else df_crm[df_crm['STAGE'].isin(sel_stage)]
        pivot_crm = df_c_f.groupby(['SOURCE_STD', 'GROUP_STATUS']).size().unstack(fill_value=0)
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues'), use_container_width=True)

    with t3:
        st.subheader("Hiệu suất Doanh thu (Gốc Masterlife)")
        # Thống kê dựa trên df_ml để đảm bảo đúng số dòng hồ sơ
        eff_summary = df_ml.groupby('SOURCE_FINAL')['REV'].agg(['sum', 'count'])
        eff_summary.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        eff_summary['ARPL'] = eff_summary['Tổng Doanh Thu'] / eff_summary['Số hồ sơ chốt']
        st.dataframe(eff_summary.style.format("${:,.0f}"), use_container_width=True)
        
        st.info(f"Tổng doanh thu Masterlife: ${df_ml['REV'].sum():,.0f} | Tổng số hồ sơ: {len(df_ml):,}")

# SIDEBAR
st.sidebar.header("Upload Files")
f1 = st.sidebar.file_uploader("Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
