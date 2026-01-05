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
    df_ml = pd.read_excel(f_ml, skiprows=h_row)

    # Chuẩn hóa CRM và CHỐT CHẶN CỘNG TRÙNG
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    
    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source_std)

    # Chỉ lấy bản ghi đầu tiên của mỗi ID/Tên trong CRM để tra cứu nguồn (Tránh nhân đôi doanh số)
    lookup_id = df_crm[df_crm['MATCH_ID'] != ''].drop_duplicates('MATCH_ID').set_index('MATCH_ID')['SOURCE_STD'].to_dict()
    lookup_name = df_crm.drop_duplicates('MATCH_NAME').set_index('MATCH_NAME')['SOURCE_STD'].to_dict()

    # Xử lý Masterlife - Quét từng dòng tiền duy nhất
    results_ml = []
    for _, row in df_ml.iterrows():
        l_id = clean_id_final(row.get('LEAD ID'))
        c_name = clean_name_final(row.get('CONTACT NAME'))
        raw_rev = str(row.get('TARGET PREMIUM', '0'))
        rev = float(re.sub(r'[^0-9.]', '', raw_rev)) if re.sub(r'[^0-9.]', '', raw_rev) != '' else 0.0
        
        # Logic gán nguồn: Ưu tiên ID, sau đó tới Tên
        final_source = '4. Ngoài CRM / Lỗi ID'
        if l_id in lookup_id:
            final_source = lookup_id[l_id]
        elif c_name in lookup_name:
            final_source = lookup_name[c_name]
        
        results_ml.append({'REV': rev, 'SOURCE': final_source})
    
    df_eff = pd.DataFrame(results_ml)

    # --- HIỂN THỊ (GIỮ NGUYÊN GIAO DIỆN CŨ) ---
    st.title("📊 TMC Strategic Dashboard")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Báo cáo chất lượng Data Marketing")
        # (Giữ code Tầng 1 như cũ)
        st.write(f"Tổng Lead Marketing: {len(df_mkt):,}")

    with t2:
        st.subheader("Ma trận Trạng thái Lead")
        pivot_crm = df_crm.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues'), use_container_width=True)

    with t3:
        st.subheader("Doanh thu thực tế (Khớp Tuyệt Đối)")
        summary = df_eff.groupby('SOURCE')['REV'].agg(['sum', 'count'])
        summary.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        summary['ARPL'] = summary['Tổng Doanh Thu'] / summary['Số hồ sơ chốt']
        st.dataframe(summary.style.format("${:,.0f}"), use_container_width=True)
        st.write(f"**Tổng Doanh Thu Masterlife:** ${df_eff['REV'].sum():,.0f}")

# SIDEBAR
st.sidebar.header("Upload Files")
f1 = st.sidebar.file_uploader("Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
