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

def clean_phone_9(phone):
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 2. ENGINE XỬ LÝ ---
def process_data(f_mkt, f_crm, f_ml):
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Load Masterlife - Gốc doanh số 1625 hồ sơ
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # CHUẨN HÓA CRM TRA CỨU
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone_9)
    
    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source_std)

    # Từ điển tra cứu 1-1
    map_id_to_src = df_crm[df_crm['MATCH_ID'] != ''].drop_duplicates('MATCH_ID').set_index('MATCH_ID')['SOURCE_STD'].to_dict()
    map_name_to_src = df_crm.drop_duplicates('MATCH_NAME').set_index('MATCH_NAME')['SOURCE_STD'].to_dict()

    # --- TẦNG 3: XỬ LÝ TRÊN MASTERLIFE ---
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    
    def lookup_source(row):
        l_id = clean_id_final(row.get('LEAD ID'))
        c_name = clean_name_final(row.get('CONTACT NAME'))
        if l_id in map_id_to_src: return map_id_to_src[l_id]
        if c_name in map_name_to_src: return map_name_to_src[c_name]
        return '4. Ngoài CRM / Lỗi ID'

    df_ml['SOURCE_FINAL'] = df_ml.apply(lookup_source, axis=1)

    # --- GIAO DIỆN ---
    st.title("📊 TMC Strategic Dashboard")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing Efficiency", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Báo cáo chất lượng Lead thô")
        # Giữ nguyên bảng Table Tầng 1
        df_mkt['M_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
        df_mkt['M_PH'] = df_mkt['CELLPHONE'].apply(clean_phone_9)
        matched_mkt = df_mkt[df_mkt['M_ID'].isin(df_crm['MATCH_ID']) | df_mkt['M_PH'].isin(df_crm['MATCH_PHONE'])]
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
        pivot_crm = df_crm.groupby(['SOURCE_STD', 'GROUP_STATUS']).size().unstack(fill_value=0)
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues'), use_container_width=True)

    with t3:
        st.subheader("Hiệu suất Doanh thu (Gốc Masterlife - 1625 Hồ Sơ)")
        
        # ÉP BẢNG HIỆN ĐỦ CÁC DÒNG NGUỒN (BAO GỒM COLD CALL)
        all_sources = ['1. Cold Call', '2. Funnel', '4. Ngoài CRM / Lỗi ID']
        summary = df_ml.groupby('SOURCE_FINAL')['REV'].agg(['sum', 'count']).reindex(all_sources, fill_value=0).reset_index()
        summary.columns = ['Nguồn', 'Tổng Doanh Thu', 'Số hồ sơ chốt']
        
        st.dataframe(summary.style.format({"Tổng Doanh Thu": "${:,.0f}"}), use_container_width=True)
        
        st.success(f"Tổng doanh thu Masterlife khớp: ${df_ml['REV'].sum():,.0f}")
        st.success(f"Tổng số hồ sơ Masterlife khớp: {len(df_ml):,}")

# SIDEBAR
st.sidebar.header("Upload Files")
f1 = st.sidebar.file_uploader("1. Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
