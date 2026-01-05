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
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #1E232D; border-radius: 5px; padding: 10px 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CÁC HÀM XỬ LÝ DỮ LIỆU THÔNG MINH ---
def clean_phone(phone):
    """Lấy 9 chữ số cuối của số điện thoại để so khớp"""
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

def clean_id(lead_id):
    """Chuẩn hóa ID: Xóa khoảng trắng, viết hoa, bù số 0 nếu cần (giả sử chuẩn 10 số)"""
    if pd.isna(lead_id): return ""
    s = str(lead_id).strip().upper()
    if s.replace('.0','').isdigit():
        s = s.replace('.0','')
        return s.zfill(7) # Giả định chuẩn Lead ID của anh là 7 hoặc 10 ký tự
    return s

def clean_name(name):
    """Làm sạch tên để so khớp dự phòng"""
    if pd.isna(name): return ""
    return re.sub(r'\s+', ' ', str(name).strip().upper())

# --- 3. ENGINE XỬ LÝ CHÍNH ---
def process_full_system(file_mkt, file_crm, file_ml):
    # Đọc dữ liệu
    df_mkt = pd.read_excel(file_mkt) if file_mkt.name.endswith('.xlsx') else pd.read_csv(file_mkt)
    df_crm = pd.read_excel(file_crm) if file_crm.name.endswith('.xlsx') else pd.read_csv(file_crm)
    
    # Masterlife dùng logic smart_load cũ để tìm header
    raw_ml = pd.read_excel(file_ml, header=None) if file_ml.name.endswith('.xlsx') else pd.read_csv(file_ml, header=None)
    header_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            header_row = i; break
    df_ml = pd.read_excel(file_ml, skiprows=header_row) if file_ml.name.endswith('.xlsx') else pd.read_csv(file_ml, skiprows=header_row)

    # --- CHUẨN HÓA CÁC CỘT ĐỊNH DANH ---
    # File Marketing
    df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id)
    df_mkt['MATCH_PHONE'] = df_mkt['CELLPHONE'].apply(clean_phone)
    
    # File CRM
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone)
    df_crm['MATCH_NAME'] = df_crm['CONTACT NAME'].apply(clean_name)
    
    # File Masterlife (Tử số)
    # Tìm cột dựa trên logic cũ
    def get_col(df, keywords):
        for c in df.columns:
            if all(k.upper() in str(c).upper() for k in keywords): return c
        return None
    
    ml_id_c = get_col(df_ml, ['LEAD', 'ID'])
    ml_name_c = get_col(df_ml, ['CONTACT', 'NAME'])
    ml_rev_c = get_col(df_ml, ['TARGET', 'PREMIUM'])
    ml_y_c = 'Năm' # Như anh xác nhận là cột F
    ml_m_c = 'Tháng nhận file'

    df_ml['MATCH_ID'] = df_ml[ml_id_c].apply(clean_id)
    df_ml['MATCH_NAME'] = df_ml[ml_name_c].apply(clean_name)
    df_ml['REV'] = df_ml[ml_rev_c].apply(lambda v: float(re.sub(r'[^0-9.]', '', str(v))) if pd.notna(v) and re.sub(r'[^0-9.]', '', str(v)) != '' else 0.0)

    # --- TẦNG 1: MARKETING EFFICIENCY ---
    total_raw = len(df_mkt)
    # Lead lên được CRM (khớp qua Phone 9 số hoặc ID)
    mkt_in_crm = df_mkt[df_mkt['MATCH_PHONE'].isin(df_crm['MATCH_PHONE']) | df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID'])]
    valid_leads = len(mkt_in_crm)
    junk_leads = total_raw - valid_leads

    # --- TẦNG 2: CRM PIPELINE ---
    # Phân loại trạng thái theo yêu cầu của anh
    status_map = {
        'Done (100%)': '✅ Won (100%)',
        'Done (50%)': '⏳ Won (50% - Need Push)',
        'Cold (5%)': 'Pipeline', 'Unidentified (10%)': 'Pipeline', 
        'Follow Up (50%)': 'Pipeline', 'Interest (75%)': 'Pipeline', 'Hot Interest (85%)': 'Pipeline',
        'Stop (0%)': '❌ Lost/Stop'
    }
    df_crm['GROUP_STATUS'] = df_crm['STATUS'].map(status_map).fillna('Khác')
    
    # --- TẦNG 3: ARPL & PERFORMANCE ---
    # Gộp CRM và Masterlife để lấy doanh thu
    df_final = pd.merge(df_crm, df_ml[['MATCH_ID', 'MATCH_NAME', 'REV', ml_y_c, ml_m_c]], 
                        left_on='MATCH_ID', right_on='MATCH_ID', how='left')
    crm_ids = set(df_crm['MATCH_ID'].unique())
    
    df_missing = df_ml[~df_ml['MATCH_ID'].isin(crm_ids)].copy()
    
    if not df_missing.empty:
        st.error(f"⚠️ Phát hiện ${df_missing['REV'].sum():,.0f} doanh thu không khớp với CRM!")
        st.subheader("Danh sách Lead ID có tiền nhưng không có trong CRM:")
        st.dataframe(df_missing[[ml_id_c, ml_name_c, 'REV']], use_container_width=True)
    else:
        st.success("✅ Tuyệt vời! 100% doanh thu đã khớp với CRM.")
    
    # --- HIỂN THỊ STREAMLIT ---
    st.title("📊 TMC Strategic CRM & Marketing Portal")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📥 TỔNG LEAD MKT", f"{total_raw:,}")
    m2.metric("✅ LEAD LÊN CRM", f"{valid_leads:,}", f"{(valid_leads/total_raw*100):.1f}%")
    m3.metric("💰 TỔNG DOANH THU", f"${df_final['REV'].sum():,.0f}")
    m4.metric("📈 ARPL (Doanh thu/Lead)", f"${(df_final['REV'].sum()/total_raw):,.1f}")

    tab1, tab2, tab3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Efficiency"])
    
    with tab1:
        st.subheader("Chất lượng Data đầu vào")
        col_l, col_r = st.columns(2)
        mkt_summary = pd.DataFrame({
            "Chỉ số": ["Tổng Lead thô", "Lead hợp lệ (Lên CRM)", "Lead rác/Sai số"],
            "Số lượng": [total_raw, valid_leads, junk_leads],
            "Tỷ lệ": ["100%", f"{(valid_leads/total_raw*100):.1f}%", f"{(junk_leads/total_raw*100):.1f}%"]
        })
        col_l.dataframe(mkt_summary, use_container_width=True)

    with tab2:
        st.subheader("Phân tích Phễu & Trạng thái")
        stage_filter = st.multiselect("Lọc theo Giai đoạn (STAGE):", options=df_crm['STAGE'].unique())
        df_filtered = df_crm if not stage_filter else df_crm[df_crm['STAGE'].isin(stage_filter)]
        
        status_pivot = df_filtered.groupby('GROUP_STATUS').size().reset_index(name='Số lượng')
        st.dataframe(status_pivot.style.background_gradient(cmap='Blues'), use_container_width=True)
        
        st.info(f"💡 Anh có {len(df_crm[df_crm['STATUS']=='Done (50%)'])} Lead đang ở trạng thái Done (50%). Hãy tập trung push nhóm này!")

    with tab3:
        st.subheader("ARPL & Hiệu suất thực tế")
        # ARPL theo nguồn
        arpl_source = df_final.groupby('SOURCE')['REV'].agg(['sum', 'count'])
        arpl_source['ARPL'] = arpl_source['sum'] / arpl_source['count']
        st.dataframe(arpl_source.style.format("${:,.1f}"), use_container_width=True)

    # --- EXPORT EXCEL ĐẸP ---
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        mkt_summary.to_excel(writer, sheet_name='1. Marketing_Report', index=False)
        status_pivot.to_excel(writer, sheet_name='2. CRM_Pipeline', index=False)
        arpl_source.to_excel(writer, sheet_name='3. Efficiency_ARPL')
        # Thêm format cho Excel ở đây nếu cần (cân lề, màu sắc...)
        
    st.sidebar.download_button("📥 Tải Báo Cáo Strategic (3 Tầng)", output.getvalue(), "TMC_Full_Report.xlsx")

# --- SIDEBAR UPLOAD ---
st.sidebar.title("🛠️ Nạp Dữ Liệu")
file_mkt = st.sidebar.file_uploader("1. File Marketing (Thô)", type=['xlsx', 'csv'])
file_crm = st.sidebar.file_uploader("2. File CRM (Chuẩn)", type=['xlsx', 'csv'])
file_ml = st.sidebar.file_uploader("3. File Masterlife (Doanh thu)", type=['xlsx', 'csv'])

if file_mkt and file_crm and file_ml:
    process_full_system(file_mkt, file_crm, file_ml)
else:

    st.warning("Vui lòng nạp đầy đủ 3 file để hệ thống bắt đầu phân tích.")
