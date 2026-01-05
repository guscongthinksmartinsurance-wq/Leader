import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px
import io

# --- 1. HÀM LÀM SẠCH DỮ LIỆU ---
def clean_id_final(lead_id):
    if pd.isna(lead_id) or str(lead_id).strip().upper() == 'NONE': return ""
    s = str(lead_id).strip().upper()
    s = re.sub(r'^[^A-Z0-9]+|[^A-Z0-9]+$', '', s)
    if s.endswith('.0'): s = s[:-2]
    return s

def clean_phone_9(phone):
    s = re.sub(r'\D', '', str(phone))
    return s[-9:] if len(s) >= 9 else s

# --- 2. ENGINE XỬ LÝ CHÍNH ---
def process_data(f_mkt, f_crm, f_ml):
    # Đọc dữ liệu thô
    df_mkt = pd.read_excel(f_mkt) if f_mkt.name.endswith('.xlsx') else pd.read_csv(f_mkt)
    df_crm = pd.read_excel(f_crm) if f_crm.name.endswith('.xlsx') else pd.read_csv(f_crm)
    
    # Load Masterlife - Đảm bảo giữ đúng số dòng gốc (1625 hồ sơ)
    raw_ml = pd.read_excel(f_ml, header=None)
    h_row = 0
    for i, row in raw_ml.head(20).iterrows():
        if 'TARGET PREMIUM' in " ".join(str(val).upper() for val in row):
            h_row = i; break
    df_ml = pd.read_excel(f_ml, skiprows=h_row).copy()

    # --- XỬ LÝ TẦNG 3: DOANH SỐ (CHỈ DÙNG FILE MASTERLIFE) ---
    df_ml['REV'] = df_ml['TARGET PREMIUM'].apply(lambda x: float(re.sub(r'[^0-9.]', '', str(x))) if pd.notna(x) and re.sub(r'[^0-9.]', '', str(x)) != '' else 0.0)
    
    def classify_ml_source(src):
        s = str(src).upper().strip()
        if 'CC' in s: return '1. Cold Call'
        if 'SF' in s: return '2. Funnel'
        return '3. Khác/Trống'
    
    df_ml['SOURCE_REPORT'] = df_ml['SOURCE'].apply(classify_ml_source)
    summary_ml = df_ml.groupby('SOURCE_REPORT')['REV'].agg(['sum', 'count']).reset_index()
    summary_ml.columns = ['Nguồn', 'Tổng Doanh Thu', 'Số hồ sơ chốt']

    # --- XỬ LÝ TẦNG 1: MARKETING ---
    df_crm['MATCH_ID'] = df_crm['LEAD ID'].apply(clean_id_final)
    df_mkt['MATCH_ID'] = df_mkt['LEAD ID'].apply(clean_id_final)
    matched_mkt = df_mkt[df_mkt['MATCH_ID'].isin(df_crm['MATCH_ID'])]
    
    mkt_summary_df = pd.DataFrame({
        "Hạng mục": ["Tổng Lead thô", "Lead hợp lệ", "Lead rác"],
        "Số lượng": [len(df_mkt), len(matched_mkt), len(df_mkt) - len(matched_mkt)]
    })

    # --- XỬ LÝ TẦNG 2: CRM ---
    # Nút lọc Stage đặt ở đây để dùng chung cho bảng và biểu đồ
    all_stages = sorted(df_crm['STAGE'].dropna().unique())
    sel_stage = st.sidebar.multiselect("🔍 Lọc Stage (Tầng 2):", options=all_stages, default=all_stages)
    df_c_f = df_crm[df_crm['STAGE'].isin(sel_stage)] if sel_stage else df_crm
    
    df_c_f['SOURCE_STD'] = df_c_f['SOURCE'].apply(lambda x: '1. Cold Call' if 'CC' in str(x).upper() else '2. Funnel')
    pivot_crm = df_c_f.groupby(['SOURCE_STD', 'STATUS']).size().unstack(fill_value=0)

    # --- GIAO DIỆN HIỂN THỊ ---
    st.title("📊 TMC Strategic Dashboard - Final Baseline")
    t1, t2, t3 = st.tabs(["🎯 Tầng 1: Marketing", "🏢 Tầng 2: CRM Pipeline", "💰 Tầng 3: Sales Performance"])

    with t1:
        st.subheader("Chất lượng Lead Marketing")
        c11, c12 = st.columns([1, 1])
        with c11: st.table(mkt_summary_df)
        with c12:
            fig1 = px.pie(mkt_summary_df, values='Số lượng', names='Hạng mục', 
                          color='Hạng mục', color_discrete_map={'Tổng Lead thô':'#636EFA', 'Lead hợp lệ':'#00CC96', 'Lead rác':'#EF553B'},
                          title="Tỷ lệ Lead Marketing")
            st.plotly_chart(fig1, use_container_width=True)

    with t2:
        st.subheader("Ma trận Trạng thái Chi tiết (CRM)")
        st.dataframe(pivot_crm.style.background_gradient(cmap='Blues', axis=1), use_container_width=True)
        
        status_counts = df_c_f['STATUS'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Số lượng']
        fig2 = px.bar(status_counts, x='Status', y='Số lượng', title="Số lượng Lead theo Status", text_auto=True)
        st.plotly_chart(fig2, use_container_width=True)

    with t3:
        st.subheader("Hiệu suất Doanh thu (Gốc Masterlife)")
        c31, c32 = st.columns([1, 1])
        with c31:
            st.dataframe(summary_ml.style.format({"Tổng Doanh Thu": "${:,.0f}"}), use_container_width=True)
            st.metric("TỔNG DOANH THU", f"${df_ml['REV'].sum():,.0f}")
            st.metric("TỔNG HỒ SƠ", f"{len(df_ml):,}")
        with c32:
            fig3 = px.pie(summary_ml, values='Tổng Doanh Thu', names='Nguồn', title="Cơ cấu Doanh số", hole=0.4)
            st.plotly_chart(fig3, use_container_width=True)

    # --- NÚT EXPORT 3 SHEETS ---
    st.sidebar.markdown("---")
    if st.sidebar.button("📥 Export Report (3 Sheets)"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            mkt_summary_df.to_excel(writer, sheet_name='1_Marketing', index=False)
            pivot_crm.to_excel(writer, sheet_name='2_CRM_Pipeline')
            summary_ml.to_excel(writer, sheet_name='3_Sales_Performance', index=False)
        st.sidebar.download_button(
            label="💾 Click để tải Excel",
            data=output.getvalue(),
            file_name="Bao_Cao_TMC_3_Tang.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- SIDEBAR UPLOAD ---
st.sidebar.header("Nạp dữ liệu nguồn")
f1 = st.sidebar.file_uploader("1. Marketing File", type=['xlsx', 'csv'])
f2 = st.sidebar.file_uploader("2. CRM File", type=['xlsx', 'csv'])
f3 = st.sidebar.file_uploader("3. Masterlife File", type=['xlsx', 'csv'])

if f1 and f2 and f3:
    process_data(f1, f2, f3)
