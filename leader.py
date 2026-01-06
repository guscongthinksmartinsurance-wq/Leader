import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px
import io

# --- 1. HÀM LÀM SẠCH (BASELINE) ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_phone_9(phone):
    if pd.isna(phone): return ""
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 2. ENGINE XỬ LÝ CHÍNH ---
def process_data(f_mkt, f_crm, f_ml):
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # --- LOGIC ĐỐI SOÁT CHI TIẾT ---
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_crm['MATCH_PHONE'] = df_crm['CELLPHONE'].apply(clean_phone_9)
    
    df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
    df_mkt['MATCH_PHONE'] = df_mkt['CELLPHONE'].apply(clean_phone_9)

    # Kiểm tra từng điều kiện để đưa ra lý do rác
    has_id_crm = df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID'])
    has_phone_crm = df_mkt['MATCH_PHONE'].isin(df_crm['MATCH_PHONE'])
    
    # Lead hợp lệ là có ID HOẶC Phone trong CRM
    is_valid = has_id_crm | has_phone_crm
    
    df_hop_le = df_mkt[is_valid].copy()
    df_rac = df_mkt[~is_valid].copy()

    # THÊM CỘT LÝ DO RÁC ĐỂ ANH CHỨNG MINH THỰC TẾ
    def suggest_reason(row):
        reasons = []
        if not row['MATCH_ID'] in df_crm['MATCH_ID'].values:
            reasons.append("ID không khớp CRM")
        if not row['MATCH_PHONE'] in df_crm['MATCH_PHONE'].values:
            reasons.append("SĐT không khớp CRM")
        return " & ".join(reasons) if reasons else "Không xác định"

    if not df_rac.empty:
        df_rac['Gợi ý lý do rác'] = df_rac.apply(suggest_reason, axis=1)

    # --- TÍNH TOÁN TẦNG 3 & TẦNG 2 (GIỮ NGUYÊN BASELINE) ---
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    df_ml['SOURCE_REPORT'] = df_ml['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else ('2. Funnel' if 'SF' in str(x).upper() else '3. Khác'))
    summary_ml = df_ml.groupby('SOURCE_REPORT')['REV'].agg(['sum', 'count']).reset_index()
    
    df_crm['SOURCE_STD'] = df_crm['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else '2. Funnel')
    pivot_crm = df_crm.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)

    # --- GIAO DIỆN HIỂN THỊ ---
    st.title("📊 TMC Strategic Dashboard")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Báo cáo chất lượng Lead thô")
        c1, c2 = st.columns(2)
        with c1: st.table(pd.DataFrame({"Hạng mục": ["Tổng Lead thô", "Lead hợp lệ", "Lead rác"], "Số lượng": [len(df_mkt), len(df_hop_le), len(df_rac)]}))
        with c2: st.plotly_chart(px.pie(values=[len(df_hop_le), len(df_rac)], names=['Hợp lệ', 'Rác'], color_discrete_sequence=['#00CC96', '#EF553B'], title="Tỷ lệ Lead MKT"), use_container_width=True)

        st.markdown("### 📂 Đối soát danh sách Lead từ MKT")
        col_dl1, col_dl2 = st.columns(2)
        
        buf_hl = io.BytesIO()
        df_hop_le.to_excel(buf_hl, index=False)
        col_dl1.download_button("✅ Tải Lead Hợp Lệ", data=buf_hl.getvalue(), file_name="Danh_Sach_Lead_Hop_Le.xlsx")
        
        buf_rac = io.BytesIO()
        df_rac.to_excel(buf_rac, index=False)
        col_dl2.download_button("❌ Tải Lead Rác (Có kèm Lý do)", data=buf_rac.getvalue(), file_name="Danh_Sach_Lead_Rac.xlsx")

    with t2:
        st.subheader("Ma trận Trạng thái Chi tiết (CRM)")
        try: st.dataframe(pivot_crm.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)
        except: st.dataframe(pivot_crm, use_container_width=True)
        
    with t3:
        st.subheader("Hiệu suất Doanh thu (Gốc Masterlife)")
        c31, c32 = st.columns(2)
        with c31:
            st.dataframe(summary_ml.style.format({"sum": "${:,.0f}"}), use_container_width=True)
            st.metric("TỔNG HỒ SƠ", f"{len(df_ml):,}")
        with c32:
            st.plotly_chart(px.pie(summary_ml, values='sum', names='SOURCE_REPORT', title="Cơ cấu Doanh số", hole=0.4), use_container_width=True)

    # NÚT EXPORT 3 SHEETS
    st.sidebar.markdown("---")
    if st.sidebar.button("📥 Export Report (3 Sheets)"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            pd.DataFrame({"Hạng mục": ["Tổng Lead thô", "Lead hợp lệ", "Lead rác"], "Số lượng": [len(df_mkt), len(df_hop_le), len(df_rac)]}).to_excel(writer, sheet_name='Marketing', index=False)
            pivot_crm.to_excel(writer, sheet_name='CRM_Pipeline')
            summary_ml.to_excel(writer, sheet_name='Sales_Performance', index=False)
        st.sidebar.download_button(label="💾 Tải file Excel Tổng hợp", data=buffer.getvalue(), file_name="Bao_Cao_TMC_3_Tang.xlsx")

# SIDEBAR
f1 = st.sidebar.file_uploader("1. MKT", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife", type=['xlsx', 'csv'])
if f1 and f2 and f3:
    process_data(f1, f2, f3)
