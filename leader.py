import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TMC Strategic CRM Portal", layout="wide")

# --- 2. HÀM LÀM SẠCH ID SIÊU CẤP (XỬ LÝ DẤU #, ', *...) ---
def clean_id_final(lead_id):
    if pd.isna(lead_id): return ""
    # Chuyển về string và viết hoa
    s = str(lead_id).strip().upper()
    # Loại bỏ tất cả ký tự không phải chữ cái và số ở đầu/cuối (như #, ', *, -)
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    # Loại bỏ đuôi .0 nếu có
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_phone_9(phone):
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 3. ENGINE XỬ LÝ ---
def process_data(f_mkt, f_crm, f_ml):
    # Đọc file
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Masterlife logic tìm Target Premium
    raw_ml = pd.read_excel(f_ml, header=None) if f_ml.name.endswith('.xlsx') else pd.read_csv(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row)

    # --- CHUẨN HÓA ĐỊNH DANH ---
    df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
    df_mkt['MATCH_PHONE'] = df_mkt['CELLPHONE'].apply(clean_phone_9)
    
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone_9)
    
    df_ml['MATCH_ID'] = df_ml['LEAD ID'].apply(clean_id_final)
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda v: float(re.sub(r'[^0-9.]', '', str(v))) if pd.notna(v) and re.sub(r'[^0-9.]', '', str(v)) != '' else 0.0)

    # Map Source
    def map_source(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL', '1.']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL', '2.']): return '2. Funnel'
        return '3. Khác'
    
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source)

    # --- TẦNG 1: BẢNG BÁO LEAD THÔ ---
    total_mkt = len(df_mkt)
    # Khớp sang CRM để tìm lead hợp lệ
    matched_in_crm = df_mkt[df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID']) | df_mkt['MATCH_PHONE'].isin(df_crm['MATCH_PHONE'])]
    valid_count = len(matched_in_crm)
    junk_count = total_mkt - valid_count

    # --- TẦNG 3: DOANH THU ---
    df_final = pd.merge(df_ml, df_crm[['MATCH_ID', 'SOURCE_STD', 'STATUS']], on='MATCH_ID', how='left')
    df_final['SOURCE_STD'] = df_final['SOURCE_STD'].fillna('4. Ngoài CRM / Lỗi ID')

    # --- GIAO DIỆN ---
    st.title("🚀 TMC Strategic Portal - Bản Full 3 Tầng")
    
    total_rev = df_ml['REV'].sum()
    rev_ok = df_final[df_final['SOURCE_STD'] != '4. Ngoài CRM / Lỗi ID']['REV'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("📥 TỔNG LEAD MKT", f"{total_mkt:,}")
    c2.metric("💰 TỔNG DOANH THU", f"${total_rev:,.0f}")
    c3.metric("⚠️ DOANH THU LỆCH", f"${(total_rev - rev_ok):,.0f}")

    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM", "💰 Tầng 3: Efficiency"])

    with t1:
        st.subheader("Báo cáo chất lượng Lead thô")
        mkt_report = pd.DataFrame({
            "Hạng mục": ["Tổng Lead đổ về (File Marketing)", "Lead hợp lệ (Đã lên CRM)", "Lead rác (Không liên lạc được/Không lên CRM)"],
            "Số lượng": [total_mkt, valid_count, junk_count],
            "Tỷ lệ %": ["100%", f"{(valid_count/total_mkt*100):.1f}%", f"{(junk_count/total_mkt*100):.1f}%"]
        })
        st.table(mkt_report) # Dùng bảng table cho rõ ràng

    with t2:
        st.subheader("Quản trị Trạng thái & Giai đoạn")
        status_pivot = df_crm.groupby(['SOURCE_STD', 'STATUS']).size().reset_index(name='Số lượng')
        st.dataframe(status_pivot.style.background_gradient(cmap='Blues'), use_container_width=True)

    with t3:
        st.subheader("Doanh thu thực tế (Tách dòng)")
        eff_df = df_final.groupby('SOURCE_STD')['REV'].agg(['sum', 'count'])
        eff_df.columns = ['Tổng Doanh Thu', 'Số hồ sơ chốt']
        eff_df['ARPL'] = eff_df['Tổng Doanh Thu'] / eff_df['Số hồ sơ chốt']
        st.dataframe(eff_df.style.format("${:,.0f}"), use_container_width=True)
        
        if (total_rev - rev_ok) > 0:
            with st.expander("🔍 Chi tiết danh sách lệch (Check mã ID có dấu #, ')"):
                st.dataframe(df_final[df_final['SOURCE_STD'] == '4. Ngoài CRM / Lỗi ID'][['LEAD ID', 'CONTACT NAME', 'REV']])

# SIDEBAR UPLOAD
st.sidebar.header("Tải file lên")
f1 = st.sidebar.file_uploader("File Marketing", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("File CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("File Masterlife", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
