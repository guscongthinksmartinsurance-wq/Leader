import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="TMC Strategic CRM Portal", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FFFFFF; }
    [data-testid="stMetricValue"] { color: #00D4FF !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. HÀM LÀM SẠCH SIÊU CẤP ---
def clean_id_ultra(lead_id):
    """Bóc dấu nháy đơn, khoảng trắng và chuẩn hóa về dạng chuỗi số"""
    if pd.isna(lead_id): return ""
    # Xóa dấu nháy đơn, khoảng trắng, và chuyển về string
    s = str(lead_id).replace("'", "").strip()
    # Loại bỏ đuôi .0 nếu Excel hiểu lầm là số thập phân
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_phone_9(phone):
    """Lấy 9 số cuối để khớp điện thoại bất kể định dạng"""
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 3. ENGINE PHÂN TÍCH ---
def process_data(f_mkt, f_crm, f_ml):
    # Đọc dữ liệu
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Masterlife dùng logic smart_load để tìm Target Premium
    raw_ml = pd.read_excel(f_ml, header=None) if f_ml.name.endswith('.xlsx') else pd.read_csv(f_ml, header=None)
    header_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            header_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=header_row)

    # CHUẨN HÓA ĐỊNH DANH (Dùng bản Ultra Clean)
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_ultra)
    df_ml['MATCH_ID'] = df_ml['LEAD ID'].apply(clean_id_ultra)
    
    # Chuẩn hóa Source Mapping
    def map_source(src):
        s = str(src).upper()
        if any(x in s for x in ['CC', 'COLD CALL']): return '1. Cold Call'
        if any(x in s for x in ['SF', 'FUNNEL']): return '2. Funnel'
        return '3. Khác'

    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(map_source)
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda v: float(re.sub(r'[^0-9.]', '', str(v))) if pd.notna(v) and re.sub(r'[^0-9.]', '', str(v)) != '' else 0.0)

    # --- TẦNG 3: HIỆU SUẤT & TRUY THU DOANH THU ---
    # Merge lấy Source từ CRM sang ML
    df_final = pd.merge(df_ml, df_crm[['MATCH_ID', 'SOURCE_STD', 'STATUS', 'STAGE']], on='MATCH_ID', how='left')
    df_final['SOURCE_STD'] = df_final['SOURCE_STD'].fillna('4. Ngoài CRM / Lỗi ID')

    # --- HIỂN THỊ ---
    st.title("🚀 TMC Strategic CRM & Marketing Portal")
    
    total_rev_ml = df_ml['REV'].sum()
    rev_matched = df_final[df_final['SOURCE_STD'] != '4. Ngoài CRM / Lỗi ID']['REV'].sum()
    rev_missing = total_rev_ml - rev_matched

    c1, c2, c3 = st.columns(3)
    c1.metric("💰 TỔNG DOANH THU (ML)", f"${total_rev_ml:,.0f}")
    c2.metric("✅ KHỚP CRM", f"${rev_matched:,.0f}", f"-${rev_missing:,.0f} Lệch")
    c3.metric("📋 HỒ SƠ CHỐT", f"{len(df_ml):,}")

    tab1, tab2, tab3 = st.tabs(["🎯 Tầng 1: MKT", "🏢 Tầng 2: CRM", "💰 Tầng 3: Efficiency"])

    with tab3:
        st.subheader("ARPL & Hiệu suất theo Nguồn")
        # Tính toán ARPL tách dòng
        arpl_df = df_final.groupby('SOURCE_STD')['REV'].agg(['sum', 'count'])
        arpl_df['ARPL'] = arpl_df['sum'] / arpl_df['count']
        st.dataframe(arpl_df.style.format("${:,.0f}"), use_container_width=True)

        if rev_missing > 0:
            with st.expander("🔍 Xem danh sách $371k bị lệch (Cần check ID hoặc dấu nháy)"):
                df_error = df_final[df_final['SOURCE_STD'] == '4. Ngoài CRM / Lỗi ID']
                st.dataframe(df_error[['LEAD ID', 'CONTACT NAME', 'REV']], use_container_width=True)

    with tab2:
        st.subheader("Nhóm Done (50%) cần Push số")
        df_50 = df_crm[df_crm['STATUS'] == 'Done (50%)']
        st.write(f"Đang có {len(df_50)} hồ sơ cần dứt điểm.")
        st.dataframe(df_50[['LEAD ID', 'CONTACT NAME', 'STAGE', 'SOURCE_STD']], use_container_width=True)

# --- SIDEBAR ---
st.sidebar.title("🛠️ Control Center")
f1 = st.sidebar.file_uploader("1. Marketing File", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM File", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife File", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
