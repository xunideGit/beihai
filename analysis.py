# -*- coding: utf-8 -*-
"""
analysis.py — FCC 项目展示系统 · 业务分析函数集（重构自原 FCC交互_t1.py）

改动：
  * 所有取数统一走 data_io（带 @st.cache_data 缓存）；
  * 字体/样式统一走 viz_style，移除分散的 plt.rcParams 设置；
  * 修正 rub 汇率数据的逗号小数问题（data_io.load_rub 已清洗）；
  * 函数保持原语义，便于逐步替换、复用与测试。
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import data_io
import viz_style


# ============================================================================
# 月度收支
# ============================================================================
def clean_amount_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"金额": "amount", "二级分类": "二级", "三级分类": "三级"})
    df["amount"] = df["amount"].apply(
        lambda x: float(str(x).replace(",", "")) if pd.notnull(x) else 0.0
    )
    df["amount_万元"] = (df["amount"] / 10000).round(2)
    df["label"] = df.apply(lambda r: f"{r['三级']}\n{r['amount_万元']}万元", axis=1)
    return df


def create_main_charts(df: pd.DataFrame) -> go.Figure:
    monthly_summary = pd.DataFrame()
    try:
        monthly_summary = (
            df.groupby(["月份", "类型"])["金额"].sum().unstack(fill_value=0).reset_index()
        )
        monthly_summary["排序日期"] = monthly_summary["月份"].apply(
            lambda x: pd.to_datetime(x, format="%Y/%m", errors="coerce")
        )
        monthly_summary = monthly_summary.sort_values("排序日期").drop(columns="排序日期")
        monthly_summary["累计收入"] = monthly_summary["收入"].cumsum()
        monthly_summary["累计支出"] = monthly_summary["支出"].cumsum()
        monthly_summary["支出占比"] = monthly_summary.apply(
            lambda r: 0.0 if r["累计收入"] == 0 else (r["累计支出"] / r["累计收入"] * 100),
            axis=1,
        ).round(1)
    except Exception as e:
        import streamlit as st
        st.error(f"数据处理失败: {e}")
        return go.Figure()

    melted = monthly_summary.melt(
        id_vars="月份", value_vars=["收入", "支出"],
        var_name="类型", value_name="金额",
    )
    melted["金额（万）"] = melted["金额"] / 10000

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    bar = px.bar(
        melted, x="月份", y="金额（万）", color="类型", barmode="group",
        color_discrete_map={"收入": "#2ecc71", "支出": "#e74c3c"},
    )
    for t in bar.data:
        fig.add_trace(t, secondary_y=False)
    line = px.line(
        monthly_summary, x="月份", y="支出占比", markers=True, text="支出占比",
        color_discrete_sequence=["#3498db"],
    )
    for t in line.data:
        fig.add_trace(t, secondary_y=True)
    fig.update_layout(title="月度收支对比与支出占比", showlegend=False)
    fig.update_yaxes(title_text="金额（万）", secondary_y=False, range=[0, 25000])
    fig.update_yaxes(title_text="支出占比 (%)", secondary_y=True, range=[0, 110])
    fig.update_traces(
        texttemplate="%{y:.1f} 万", textposition="outside", selector=dict(type="bar")
    )
    fig.update_traces(
        texttemplate="%{text}%", textposition="top center", line=dict(width=2),
        marker=dict(size=6), hovertemplate="%{x}<br>支出占比: %{y}%",
        selector=dict(type="scatter"),
    )
    return fig


# ============================================================================
# 资金全景（perm.xlsx + data.xlsx 明细）
# ============================================================================
def generate_expense_analysis():
    try:
        df = data_io.load_perm().rename(columns={"Expense": "支出项", "Amount": "金额"})
        df = df[~df["金额"].isna()]
        material_mask = df["支出项"].str.contains("材料", na=False)
        material_total = df[material_mask]["金额"].sum()
        combined = pd.concat([
            df[~material_mask],
            pd.DataFrame([["材料类支出", material_total]], columns=["支出项", "金额"]),
        ]).sort_values("金额", ascending=False)

        viz_style.setup_fonts()
        font = viz_style.font_prop(14)
        fig, ax = plt.subplots(figsize=(22, 11), facecolor="white")
        bars = ax.bar(range(len(combined)), combined["金额"] / 10000, width=0.6,
                      color="#1f77b4", edgecolor="black")
        for idx, bar in enumerate(bars):
            h = bar.get_height()
            if np.isfinite(h):
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1, f"{h:.1f}万",
                        ha="center", va="bottom", fontsize=9, fontproperties=font)
        ax2 = ax.twinx()
        pct = (combined["金额"] / combined["金额"].sum() * 100).round(1)
        ax2.plot(range(len(combined)), pct, color="red", marker=".", markersize=6, linewidth=1)
        for x_pos, y_val in zip(range(len(combined)), pct):
            if np.isfinite(y_val):
                ax2.text(x_pos + 0.2, y_val + 0.2, f"{y_val}%", color="red", ha="center", fontsize=10)
        ax.set_xticks(range(len(combined)))
        ax.set_xticklabels(combined["支出项"], rotation=45, ha="right", fontproperties=font)
        ax.set_ylabel("金额（万元）", fontsize=12, fontproperties=font)
        ax2.set_ylabel("占比 (%)", fontsize=12, fontproperties=font)
        plt.title("彼尔姆FCC项目各项支出（含占比）", fontsize=16, pad=20, fontproperties=font)
        plt.tight_layout()

        import io
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return {"buffer": buf, "combined_df": combined, "expense_items": combined["支出项"].tolist()}
    except Exception as e:
        import streamlit as st, traceback
        st.error(f"可视化生成失败：{e}")
        traceback.print_exc()
        return None


def create_treemap(df: pd.DataFrame) -> go.Figure:
    required = ["二级", "三级", "amount"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"数据中缺少必要列：'{col}'")
    df = df.copy()
    df["amount"] = df["amount"].replace(r"[\$,]", "", regex=True).astype(float)
    df = df[df["二级"].notna() & df["三级"].notna()]
    df["amount_万元"] = (df["amount"] / 10000).round().astype(int)
    df["一级"] = "合同价款"
    df["label"] = df.apply(lambda x: f"{x['三级']}\n{x['amount_万元']}万元", axis=1)
    fig = px.treemap(
        df, path=["一级", "二级", "三级"], values="amount_万元",
        title="资金结构展示（含三级明细，单位：万元）", hover_data=["label"],
        color="amount_万元", color_continuous_scale="Blues",
    )
    fig.update_traces(
        textinfo="label+value",
        texttemplate="<b>%{label}</b><br>%{value}万元",
        hovertemplate="<b>%{label}</b><br>%{value}万元<br>占比：%{percentParent:.2%}",
        marker=dict(cornerradius=5), maxdepth=3,
    )
    fig.update_layout(margin=dict(t=50, l=20, r=20, b=20),
                      uniformtext=dict(minsize=12, mode="hide"))
    return fig


# ============================================================================
# 桩基进度
# ============================================================================
def generate_pile_analysis():
    try:
        df = data_io.load_excel("pile_副本.xlsx", sheet="桩基付款", header=0)
        df.set_index("阶段", inplace=True)
        df = df.transpose()

        viz_style.setup_fonts()
        font = viz_style.font_prop(14)
        fig, ax1 = plt.subplots(figsize=(24, 16), dpi=100, facecolor="white")
        num_groups = 2
        bar_width = 0.35
        x = np.arange(len(df.index))
        for j in range(num_groups):
            off = (j - num_groups / 2) * bar_width
            ax1.bar(x + off, df.iloc[:, j], width=bar_width, label=df.columns[j])
        ax1.set_title("桩基完成情况", fontsize=16, fontproperties=font)
        ax1.set_xlabel("桩基编号", fontsize=16, fontproperties=font)
        ax1.set_ylabel("桩基数量", fontsize=12, fontproperties=font)
        ax1.set_xticks(x)
        ax1.set_xticklabels(df.index, rotation=45, fontproperties=font)
        ax1.set_ylim(0, 12000)
        ax1.legend(bbox_to_anchor=(0.8, 1.0), fontsize=16, prop=font)
        for j in range(num_groups):
            for xi, yv in enumerate(df.iloc[:, j]):
                if not np.isnan(yv):
                    off = (j - num_groups / 2) * bar_width
                    ax1.text(x[xi] + off + bar_width / 2, yv + 100, int(yv),
                             ha="center", fontsize=9, rotation=45, fontproperties=font)
        ax2 = ax1.twinx()
        proportion = df["截至0425完成"] / df["桩基总数"] * 100
        ax2.plot(x, proportion, marker="o", color="green", label="完成比例")
        ax2.set_ylabel("完成比例（%）", fontsize=12, fontproperties=font)
        ax2.set_ylim(0, 200)
        for xi, yv in enumerate(proportion):
            if not np.isnan(yv):
                ax2.text(x[xi], yv + 2, f"{yv:.1f}%", ha="center", fontsize=9, fontproperties=font)
        legend = ax2.legend()
        for t in legend.get_texts():
            t.set_fontproperties(font)
        plt.figtext(0.9, 0.05,
                    "注：桩基总数111555米；截至2025年04月25日：累计完成桩基71113米，累计完成比例63.75%。",
                    ha="right", fontsize=10, color="blue", fontproperties=font)
        plt.tight_layout()
        return fig
    except Exception as e:
        import streamlit as st
        st.error(f"桩基分析失败：{e}")
        return None


# ============================================================================
# 卢布汇率
# ============================================================================
def generate_currency_analysis():
    try:
        df = data_io.load_rub()
        if df is None or df.empty:
            return None
        df_long = df.melt(id_vars=["日期"], value_vars=["CBR", "AVE", "PBC"],
                          var_name="机构", value_name="汇率").dropna()
        fig = px.line(
            df_long, x="日期", y="汇率", color="机构",
            title="卢布汇率走势分析（2024-2026）",
            color_discrete_map={"CBR": "#1f77b4", "AVE": "#ff7f0e", "PBC": "#2ca02c"},
        )
        fig.update_layout(
            hovermode="x unified",
            legend=dict(title_text="数据来源", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(
                rangeselector=dict(buttons=list([
                    dict(count=7, label="1周", step="day"),
                    dict(count=1, label="1月", step="month"),
                    dict(count=3, label="3月", step="month"),
                    dict(step="all"),
                ])),
                rangeslider=dict(visible=True), type="date",
            ),
            yaxis=dict(range=[9, 16]), height=800, template="plotly_white",
        )
        return fig
    except Exception as e:
        import streamlit as st, traceback
        st.error(f"汇率分析失败：{e}")
        traceback.print_exc()
        return None


# ============================================================================
# 人力资源
# ============================================================================
def generate_staff_analysis():
    try:
        df = data_io.load_staff()
        if df is None:
            return None, None
        df.columns = df.columns.str.strip().str.replace(r"\s+", "", regex=True)

        def std_nat(x):
            x = str(x).strip()
            if "中国" in x or x == "华人":
                return "中国"
            if "俄" in x:
                return "俄罗斯"
            if "中亚" in x:
                return "中亚国家"
            return x

        df["国籍"] = df["国籍"].apply(std_nat)

        def corr_gender(row):
            if row["国籍"] == "俄罗斯" and row["姓名"].strip().endswith(("а", "я", "娜", "莎")):
                return "女"
            return row["性别"]

        df["性别"] = df.apply(corr_gender, axis=1)
        if df.empty:
            import streamlit as st
            st.error("数据加载为空，请检查文件内容！")
            return None, None

        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{"type": "pie"}, {"type": "pie"}],
                   [{"type": "sunburst"}, {"type": "bar"}]],
            subplot_titles=("国籍分布", "性别比例", "职务层级分析", "岗位人数TOP10"),
        )
        nat = df["国籍"].value_counts().reset_index()
        fig.add_trace(go.Pie(labels=nat["国籍"], values=nat["count"], hole=0.3,
                             marker_colors=px.colors.qualitative.Pastel, name="国籍分布"), 1, 1)
        gen = df["性别"].value_counts().reset_index()
        fig.add_trace(go.Pie(labels=gen["性别"], values=gen["count"], hole=0.6,
                             marker_colors=["#FFD700", "#FF69B4"], textinfo="percent+label",
                             name="性别比例"), 1, 2)
        sun = df.groupby(["国籍", "职务"]).size().reset_index(name="人数")
        fig.add_trace(px.sunburst(sun, path=["国籍", "职务"], values="人数", color="国籍",
                                  color_discrete_map={"中国": "#8ECFC9", "俄罗斯": "#FFBE7A",
                                                      "中亚国家": "#FA7F6F"}).data[0], 2, 1)
        top = df["职务"].value_counts().head(10).reset_index()
        fig.add_trace(go.Bar(x=top["count"], y=top["职务"], orientation="h",
                             marker_color="#1f77b4", name="岗位TOP10"), 2, 2)
        fig.update_layout(title_text="FCC项目部人员构成分析", height=800, template="plotly_white",
                          hoverlabel=dict(bgcolor="white", font_size=12, font_family="Microsoft YaHei"),
                          uniformtext=dict(minsize=10, mode="show"), margin=dict(l=20, r=20, t=80, b=80))
        return fig, df
    except Exception as e:
        import streamlit as st
        st.error(f"人员分析失败：{e}")
        return None, None


# ============================================================================
# 供应商
# ============================================================================
def show_suppliers():
    import streamlit as st
    st.subheader("供应商信息展示")
    xl = data_io.load_suppliers_excel()
    if xl is None:
        st.error("未找到供应商数据文件")
        return
    sheet_names = xl.sheet_names
    search = st.text_input("请输入要搜索的供应商名称", "")
    matched = [n for n in sheet_names if search.lower() in n.lower()] if search else sheet_names
    for name in matched:
        st.subheader(f"供应商名称: {name}")
        st.dataframe(xl.parse(name))
