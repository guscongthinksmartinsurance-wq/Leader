import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO

# --- 1. CẤU HÌNH & LÀM SẠCH ---
st.set_page_config(page_title="TMC Strategic Portal", layout="wide")

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
    # Đọc dữ liệu
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row)

    # Làm sạch CRM làm chuẩn (Anh khẳng định 100% ID duy nhất nên không sợ trùng)
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone_9)
    
    # Giữ nguyên nhóm Status cho Tầng 2
    status_map = {
        'Done (100%)': '✅ Won (100%)',
        'Done (50%)': '⏳ Won (50% - Need Push)',
        'Cold (5%)': 'Pipeline', 'Unidentified (10%)': 'Pipeline', 
        'Follow Up (50%)': 'Pipeline', 'Interest (75%)': 'Pipeline', 'Hot Interest (85%)': 'Pipeline',
        'Stop (0%)': '❌ Lost/Stop'
    }
    df_crm['GROUP_STATUS'] = df_crm['STATUS'].map(status_map).fillna('Khác')

    # Mapping Source chuẩn
    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source_std)

    # Tạo từ điển tra cứu nhanh từ CRM
    dict_id_source = dict(zip(df_crm[df_crm['MATCH_ID'] != '']['MATCH_ID'], df_crm['SOURCE_STD']))
    dict_name_source = dict(zip(df_crm['MATCH_NAME'], df_crm['SOURCE_STD']))

    # --- TẦNG 1: GIỮ NGUYÊN BẢNG LEAD THÔ ---
    df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
    df_mkt['MATCH_PHONE'] = df_mkt['CELLPHONE'].apply(clean_phone_9)
    matched_mkt = df_mkt[df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID']) | df_mkt['MATCH_PHONE'].isin(df_crm['MATCH_PHONE'])]
    
    # --- TẦNG 3: DOANH THU SIÊU KHỚP (KHÔNG CỘNG TRÙNG) ---
    results_ml = []
    for _, row in df_ml.iterrows():
        l_id = clean_id_final(row.get('LEAD ID'))
        c_name = clean_name_final(row.get('CONTACT NAME'))
        raw_rev = str(row.get('TARGET PREMIUM', '0'))
        rev = float(re.sub(r'[^0-9.]', '', raw_rev)) if re.sub(r'[^0-9.]', '', raw_rev) != '' else 0.0
        
        src_label = '4. Ngoài CRM / Lỗi ID'
        # Chỉ khớp 1 lần duy nhất cho mỗi dòng tiền: ID trước, Tên sau
        if l_id in dict_id_source: src_label = dict_id_source[l_id]
        elif c_name in dict_name_source: src_label = dict_name_source[c_name]
        
        results_ml.append({'REV': rev, 'SOURCE': src_label})
    df_eff = pd.DataFrame(results_ml)

    # --- HIỂN THỊ (KHÔI PHỤC CẤU TRÚC GỐC) ---
    st.title("📊 TMC Strategic Dashboard")
    
    total_rev_ml = df_ml['REV'].sum() if 'REV' in df_ml else df_eff['REV'].sum()
    
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing Efficiency", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Báo cáo chất lượng Data Marketing")
        mkt_sum = pd.DataFrame({
            "Hạng mục": ["Tổng Lead thô (Marketing File)", "Lead hợp lệ (Đã lên CRM)", "Lead rác (Không lên CRM)"],
            "Số lượng": [len(df_mkt), len(matched_mkt), len(df_mkt) - len(matched_mkt)],
            "Tỷ lệ": ["100%", f"{(len(matched_mkt)/len(df_mkt)*100):.1f}%", f"{((len(df_mkt)-len(matched_mkt))/len(df_mkt)*100):.1f}%"]
        })
        st.table(mkt_sum)

    with t2:
        st.subheader("Ma trận Trạng thái Lead trên CRM")
        sel_stage = st.multiselect("Lọc Stage:", options=df_crm['STAGE'].unique())
        df_c_f = df_crm if not sel_stage else df_crm[df_crm['STAGE'].isin(sel_stage)]
        
        pivot_crm = df_c_f.groupby(['SOURCE_STD', 'GROUP_STATUS']).size().unstack(fill_value=0)
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues'), use_container_width=True)

    with t3:
        st.subheader("Hiệu suất Doanh thu (Khớp ID + Name)")
        summary = df_eff.groupby('SOURCE')['REV'].agg(['sum', 'count'])
        summary.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        summary['ARPL'] = summary['Tổng Doanh Thu'] / summary['Số hồ sơ chốt']
        st.dataframe(summary.style.format("${:,.0f}"), use_container_width=True)
        st.write(f"**Tổng tiền khớp được:** ${df_eff[df_eff['SOURCE'] != '4. Ngoài CRM / Lỗi ID']['REV'].sum():,.0f}")
        st.write(f"**Tổng doanh thu Masterlife gốc:** ${total_rev_ml:,.0f}")

# SIDEBAR
st.sidebar.header("Upload Files")
file_mkt = st.sidebar.file_uploader("Marketing", type=['xlsx', 'csv'])
file_crm = st.sidebar.file_uploader("CRM", type=['xlsx', 'csv'])
file_ml = st.sidebar.file_uploader("Masterlife", type=['xlsx', 'csv'])

if file_mkt and file_crm and file_ml:
    process_data(file_mkt, file_crm, file_ml)
