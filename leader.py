import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO

# --- 1. HÀM LÀM SẠCH (Đặt ở ngoài để không bị lỗi scope) ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    # Loại bỏ ký tự đặc biệt ở đầu/cuối như #, ', *, -
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
    # Đọc file an toàn
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Xử lý Masterlife tìm Header
    raw_ml = pd.read_excel(f_ml, header=None) if f_ml.name.endswith('.xlsx') else pd.read_csv(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i
            break
    df_ml = pd.read_excel(f_ml, skiprows=h_row) if f_ml.name.endswith('.xlsx') else pd.read_csv(f_ml, skiprows=h_row)

    # Làm sạch CRM làm chuẩn
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone_9)
    
    # Tạo từ điển tra cứu (Dùng để khớp nhanh)
    dict_id_source = dict(zip(df_crm[df_crm['MATCH_ID'] != '']['MATCH_ID'], df_crm['SOURCE']))
    dict_name_source = dict(zip(df_crm['MATCH_NAME'], df_crm['SOURCE']))

    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'

    # Xử lý File Masterlife quét từng dòng tiền
    results = []
    for _, row in df_ml.iterrows():
        l_id = clean_id_final(row.get('LEAD ID'))
        c_name = clean_name_final(row.get('CONTACT NAME'))
        raw_rev = str(row.get('TARGET PREMIUM', '0'))
        rev = float(re.sub(r'[^0-9.]', '', raw_rev)) if re.sub(r'[^0-9.]', '', raw_rev) != '' else 0.0
        
        source = None
        # Khớp 2 lớp: ID trước, Tên sau
        if l_id in dict_id_source:
            source = dict_id_source[l_id]
        elif c_name in dict_name_source:
            source = dict_name_source[c_name]
        
        results.append({
            'LEAD ID': row.get('LEAD ID'),
            'CONTACT NAME': row.get('CONTACT NAME'),
            'REV': rev,
            'SOURCE_LABEL': map_source_std(source) if source else '4. Ngoài CRM / Lỗi ID'
        })

    df_final = pd.DataFrame(results)

    # --- HIỂN THỊ GIAO DIỆN ---
    st.title("🚀 TMC Strategic Portal - Siêu Khớp ID & Name")
    
    t_rev = df_final['REV'].sum()
    c1, c2 = st.columns(2)
    c1.metric("💰 TỔNG DOANH THU (ML)", f"${t_rev:,.0f}")
    c2.metric("📋 TỔNG HỒ SƠ", f"{len(df_final):,}")

    tab1, tab2, tab3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM", "💰 Tầng 3: Efficiency"])

    with tab1:
        st.subheader("Báo cáo Lead thô")
        matched_mkt = df_mkt[df_mkt['LEAD ID'].apply(clean_id_final).isin(df_crm['MATCH_ID'])]
        st.write(f"Tổng Lead MKT: {len(df_mkt)} | Hợp lệ: {len(matched_mkt)}")

    with tab3:
        st.subheader("Doanh thu tách dòng")
        eff = df_final.groupby('SOURCE_LABEL')['REV'].agg(['sum', 'count']).reset_index()
        eff.columns = ['Nguồn', 'Tổng Doanh Thu', 'Số hồ sơ']
        st.dataframe(eff.style.format({"Tổng Doanh Thu": "${:,.0f}"}), use_container_width=True)
        
        with st.expander("🔍 Danh sách lệch (Không khớp ID & Tên)"):
            st.dataframe(df_final[df_final['SOURCE_LABEL'] == '4. Ngoài CRM / Lỗi ID'])

# --- SIDEBAR ---
st.sidebar.header("Nạp dữ liệu")
f1 = st.sidebar.file_uploader("1. Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
