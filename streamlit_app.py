# -*- coding: utf-8 -*-
"""
streamlit_app.py — FCC 项目展示系统（统一入口）

重构说明（相对原 FCC交互_t1.py）：
  * 原单体文件拆分为模块化结构：data_io（缓存加载）、viz_style（字体样式）、
    analysis（业务分析）、forecast（预测引擎）、prediction_ui（预测页）、
    github_sync（GitHub 集成页）；
  * 所有取数经 @st.cache_data 缓存，避免重复 IO；
  * 新增“预测分析”与“GitHub 数据同步”两大功能；
  * 保留原有 14 个业务页面（inout / fund / pile / currency / hr / 供应商 / 甘特 / 合同 等）。

部署：Streamlit Community Cloud 默认入口即 streamlit_app.py（devcontainer 已对齐）。
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

import data_io
import viz_style
import analysis
import prediction_ui
import github_sync
import gantt_module
import wison
import xiang
import balance
import DailyPile1

BASE_DIR = Path(__file__).parent


def system_check():
    try:
        st.set_page_config(
            page_title="FCC项目展示系统",
            layout="wide",
            page_icon="📊",
            initial_sidebar_state="expanded",
        )
        viz_style.setup_fonts()
    except Exception as e:
        st.error(f"系统初始化失败：{e}")
        st.stop()


def _auth_ok() -> bool:
    """动态口令校验；CI/部署可经 secrets 配置 bypass_auth 跳过。"""
    try:
        if st.secrets.get("bypass_auth", False):
            return True
    except Exception:
        pass
    current_date = datetime.now().strftime("%Y%m%d")
    code = st.session_state.get("access_code", "")
    return code == f"fcc{current_date}"


def main_interface():
    with st.sidebar:
        st.title("📊 FCC项目展示系统")
        logo = BASE_DIR / "cncec.png"
        if logo.exists():
            st.image(str(logo), use_container_width=True)
        st.markdown("---")
        st.markdown("## 系统功能导航")

        if "current_page" not in st.session_state:
            st.session_state.current_page = "inout"

        nav_options = [
            ("月度收支图表", "inout"),
            ("银行账户余额", "balance"),
            ("资金全景展示", "fund"),
            ("惠生合同数据", "wison"),
            ("供应商信息表", "suppliers"),
            ("卢布汇率走势", "currency"),
            ("付款单统计表", "payments"),
            ("收支明细台账", "detail"),
            ("人力资源分布", "hr"),
            ("桩基进度看板", "pile"),
            ("每日桩基进度", "dailypile"),
            ("资金结构展示", "structure"),
            ("付款紧急程度", "xiang"),
            ("任务管理模块", "gantt"),
            ("📈 预测分析", "predict"),
            ("🔗 GitHub 数据同步", "github"),
        ]
        for display_name, page_id in nav_options:
            is_active = st.session_state.current_page == page_id
            if st.button(display_name, key=f"nav_{page_id}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state.current_page = page_id
                st.rerun()

    # 动态口令
    # 注意：不要写成 st.session_state.access_code = st.text_input(...)，
    # 因为 key="access_code" 已自动把值同步进 session_state，
    # 再手动赋值会触发 StreamlitAPIException。
    st.text_input(
        "请输入动态访问口令", key="access_code",
        help="口令格式：fcc + 当日日期(YYYYMMDD)", type="password",
    )
    if not _auth_ok():
        st.warning("⚠️ 口令验证失败！请检查输入格式（示例：fcc20260929）")
        return

    page = st.session_state.current_page

    # ---- 月度收支 ----
    if page == "inout":
        st.subheader("月度资金收支统计表（截至最新数据）")
        with st.spinner("正在加载分析数据..."):
            df = data_io.load_inout_long()
        if df.empty:
            st.error("数据加载失败，请检查 inout.xlsx 格式和路径！")
            return
        income_total = df[df["类型"] == "收入"]["金额"].sum()
        expense_total = df[df["类型"] == "支出"]["金额"].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("总收款", f"¥{income_total/10000:.2f} 万")
        c2.metric("总支出", f"¥{expense_total/10000:.2f} 万")
        c3.metric("收支净额", f"¥{(income_total-expense_total)/10000:.2f} 万",
                  delta=f"{(income_total-expense_total)/income_total:.1%}" if income_total > 0 else None)
        st.subheader("核心分析图表")
        st.plotly_chart(analysis.create_main_charts(df), use_container_width=True)
        with st.expander("📁 原始数据预览"):
            st.dataframe(df.pivot_table(index="月份", columns="类型", values="金额", aggfunc="sum"),
                         use_container_width=True)

    # ---- 银行余额 ----
    elif page == "balance":
        balance.main()

    # ---- 资金全景 ----
    elif page == "fund":
        st.subheader("资金支出全景展示")
        with st.spinner("生成中..."):
            expense_data = analysis.generate_expense_analysis()
        if expense_data:
            st.image(expense_data["buffer"], use_container_width=True, caption="资金分布全景图")
            st.download_button("下载图表", data=expense_data["buffer"], file_name="fund_analysis.png", mime="image/png")
            with st.expander("🔍 点击查看明细"):
                col1, col2 = st.columns([2, 3])
                with col1:
                    selected = st.selectbox("选择支出项查看明细", options=expense_data["expense_items"],
                                            index=None, key="main_expense_select")
                with col2:
                    if selected:
                        try:
                            df_detail = data_io.load_data_sheet(selected)
                            df_detail = df_detail.dropna(subset=["金额"])
                            df_detail["金额"] = df_detail["金额"].abs()
                            if "日期" in df_detail.columns:
                                df_detail["日期"] = pd.to_datetime(df_detail["日期"], errors="coerce")
                                df_detail["月份"] = df_detail["日期"].dt.strftime("%Y-%m")
                            t1, t2, t3 = st.tabs(["趋势分析", "构成分析", "原始数据"])
                            with t1:
                                if "月份" in df_detail.columns:
                                    monthly = df_detail.groupby("月份")["金额"].sum().reset_index()
                                    st.plotly_chart(px.line(monthly, x="月份", y="金额", markers=True,
                                                           title=f"{selected}月度趋势"), use_container_width=True)
                            with t2:
                                if "子类" in df_detail.columns:
                                    sub = df_detail.groupby("子类")["金额"].sum().reset_index()
                                    st.plotly_chart(px.pie(sub, names="子类", values="金额", hole=0.3,
                                                         title=f"{selected}构成分析"), use_container_width=True)
                                else:
                                    st.warning("当前支出项无子类分类数据")
                            with t3:
                                st.dataframe(df_detail, height=300)
                                csv = df_detail.to_csv(index=False).encode("utf-8-sig")
                                st.download_button(f"下载{selected}明细", data=csv,
                                                  file_name=f"{selected}_明细.csv", mime="text/csv")
                        except Exception as e:
                            st.error(f"数据加载失败：{e}")

    # ---- 惠生合同 ----
    elif page == "wison":
        wison.main()

    # ---- 供应商 ----
    elif page == "suppliers":
        analysis.show_suppliers()

    # ---- 汇率 ----
    elif page == "currency":
        st.subheader("卢布汇率走势分析")
        with st.spinner("正在生成汇率分析图表..."):
            fig = analysis.generate_currency_analysis()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("📈 数据明细"):
                rub = data_io.load_rub()
                if rub is not None:
                    st.dataframe(rub, height=300)
                    csv = rub.to_csv(index=False).encode("utf-8-sig")
                    st.download_button("下载完整数据", data=csv, file_name="rub_exchange_rate.csv", mime="text/csv")

    # ---- 付款单 ----
    elif page == "payments":
        st.subheader("财务付款单统计表")
        df = data_io.load_payments()
        if df is not None:
            st.dataframe(df)
        else:
            st.error("未找到 fcc_payments.xlsx")

    # ---- 收支明细台账 ----
    elif page == "detail":
        st.subheader("月度收支统计表")
        df = data_io.load_monthly()
        if df is not None:
            st.dataframe(df)
        else:
            st.error("未找到 月度收支.xlsx")

    # ---- 人力资源 ----
    elif page == "hr":
        st.subheader("人力资源智能分析")
        with st.spinner("生成人员构成分析..."):
            fig, cleaned = analysis.generate_staff_analysis()
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            if cleaned is not None:
                csv = cleaned.to_csv(index=False).encode("utf-8-sig")
                st.download_button("下载清洗后数据", data=csv, file_name="staff_cleaned.csv", mime="text/csv")
                with st.expander("🔍 数据质量报告"):
                    st.write(f"总人数: {len(cleaned)}")
                    st.write("国籍分布:", cleaned["国籍"].value_counts().to_dict())
                    st.write("性别比例:", cleaned["性别"].value_counts().to_dict())

    # ---- 桩基看板 ----
    elif page == "pile":
        st.subheader("桩基进度看板")
        with st.spinner("生成中..."):
            fig = analysis.generate_pile_analysis()
        if fig:
            st.pyplot(fig)
            import io
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
            buf.seek(0)
            st.download_button("下载图表", data=buf, file_name="pile_analysis.png", mime="image/png")

    # ---- 每日桩基 ----
    elif page == "dailypile":
        DailyPile1.main()

    # ---- 资金结构 ----
    elif page == "structure":
        st.subheader("资金结构展示")
        with st.spinner("生成中..."):
            try:
                df = data_io.load_main_table()
                if df is not None:
                    cleaned = analysis.clean_amount_data(df)
                    fig = analysis.create_treemap(cleaned)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                        with st.expander("📊 数据明细"):
                            st.dataframe(cleaned[["二级", "三级", "amount_万元"]]
                                         .sort_values("amount_万元", ascending=False))
                        st.download_button("下载数据", data=cleaned.to_csv(index=False).encode("utf-8-sig"),
                                          file_name="资金结构.csv", mime="text/csv")
                else:
                    st.error("未找到 主表.xlsx")
            except Exception as e:
                st.error(f"分析失败：{e}")

    # ---- 付款紧急程度 ----
    elif page == "xiang":
        xiang.main()

    # ---- 任务管理 ----
    elif page == "gantt":
        gantt_module.gantt_main()

    # ---- 预测分析（新增） ----
    elif page == "predict":
        prediction_ui.run_prediction_page()

    # ---- GitHub 数据同步（新增） ----
    elif page == "github":
        github_sync.run_github_page()


if __name__ == "__main__":
    system_check()
    main_interface()
