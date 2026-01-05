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

def clean_name_final(name):
    if pd.isna(name): return ""
    # Viết hoa, xóa khoảng trắng thừa
    return re.sub(r'\s+', ' ', str(name).strip().upper())

# --- 2. ENGINE XỬ LÝ SIÊU KHỚP ---
def process_data_v3(f_mkt, f_crm, f_ml):
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Load Masterlife
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row)

    # Làm sạch dữ liệu CRM làm chuẩn
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name_final)
    
    # Tạo từ điển tra cứu nhanh từ CRM (ID -> Source và Name -> Source)
    dict_id_source = dict(zip(df_crm[df_crm['MATCH_ID'] != '']['MATCH_ID'], df_crm['SOURCE']))
    dict_name_source = dict(zip(df_crm['MATCH_NAME'], df_crm['SOURCE']))

    def map_source_std(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'

    # Xử lý File Masterlife
    results = []
    for _, row in df_ml.iterrows():
        lead_id = clean_id_final(row.get('LEAD ID'))
        contact_name = clean_name_final(row.get('CONTACT NAME'))
        rev = float(re.sub(r'[^0-9.]', '', str(row.get('TARGET PREMIUM')))) if pd.notna(row.get('TARGET PREMIUM')) and re.sub(r'[^0-9.]', '', str(row.get('TARGET PREMIUM'))) != '' else 0.0
        
        source = None
        # Bước 1: Thử khớp bằng ID
        if lead_id in dict_id_source:
            source = dict_id_source[lead_id]
        # Bước 2: Nếu ID không khớp hoặc trống, thử khớp bằng Tên
        elif contact_name in dict_name_source:
            source = dict_name_source[contact_name]
        
        source_label = map_source_std(source) if source else '4. Ngoài CRM / Lỗi ID'
        
        results.append({
            'LEAD ID': row.get('LEAD ID'),
            'CONTACT NAME': row.get('CONTACT NAME'),
            'REV': rev,
            'SOURCE_FINAL': source_label
        })

    df_final = pd.DataFrame(results)

    # --- HIỂN THỊ ---
    st.title("🚀 TMC Strategic Portal - Version Double Matching")
    
    total_rev = df_final['REV'].sum()
    st.metric("💰 TỔNG DOANH THU THỰC TẾ", f"${total_rev:,.0f}")

    tab1, tab2, tab3 = st.tabs(["🎯 Tầng 1: MKT", "🏢 Tầng 2: CRM", "💰 Tầng 3: Efficiency"])

    with tab3:
        st.subheader("Doanh thu tách dòng (ID & Name Matching)")
        eff_df = df_final.groupby('SOURCE_FINAL')['REV'].agg(['sum', 'count'])
        eff_df.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        eff_df['ARPL'] = eff_df['Tổng Doanh Thu'] / eff_df['Số hồ sơ chốt']
        st.dataframe(eff_df.style.format("${:,.0f}"), use_container_width=True)

        with st.expander("🔍 Danh sách vẫn còn lệch (Không khớp cả ID lẫn Tên)"):
            st.dataframe(df_final[df_final['SOURCE_FINAL'] == '4. Ngoài CRM / Lỗi ID'])

# (Giữ phần Sidebar như cũ)
