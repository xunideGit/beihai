# -*- coding: utf-8 -*-
"""
prediction_ui.py — 数据分析与预测增强（新增页面）

功能：
  1. 时序预测：汇率 / 月度收支 / 每日桩基完成量，支持多模型与自动选型；
     输出预测值 + 置信区间 + 回测指标（MAE/RMSE/MAPE）+ 历史拟合对比。
  2. 异常检测：z-score / IQR / 滚动 z-score，图表高亮并列出异常点。
  3. 相关性分析：多序列相关系数热力图。
  4. 季节性分解：加性 trend / seasonal / resid。
  5. 一键导出预测结果为 CSV。
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

import data_io
import forecast as fc


MODELS = {
    "auto": "自动（按回测 MAPE 择优）",
    "naive": "朴素（沿用末值）",
    "seasonal_naive": "季节朴素",
    "moving_average": "移动平均",
    "linear": "线性回归",
    "holt_winters": "加性 Holt-Winters",
}


def _build_series(dataset: str):
    """根据所选数据集返回 (dates_labels, values, freq, note)。"""
    if dataset == "汇率-CBR":
        df = data_io.load_rub()
        s = df.dropna(subset=["CBR"]).sort_values("日期")
        return s["日期"].dt.strftime("%Y-%m-%d").tolist(), s["CBR"].to_numpy(), "D", "CBR 央行卢布汇率"
    if dataset == "汇率-AVE":
        df = data_io.load_rub()
        s = df.dropna(subset=["AVE"]).sort_values("日期")
        return s["日期"].dt.strftime("%Y-%m-%d").tolist(), s["AVE"].to_numpy(), "D", "AVE 平均汇率"
    if dataset == "汇率-PBC":
        df = data_io.load_rub()
        s = df.dropna(subset=["PBC"]).sort_values("日期")
        return s["日期"].dt.strftime("%Y-%m-%d").tolist(), s["PBC"].to_numpy(), "D", "PBC 人民币中间价"
    if dataset.startswith("收支"):
        kind = "收入" if "收入" in dataset else "支出"
        long = data_io.load_inout_long()
        if long.empty:
            return [], np.array([]), "M", ""
        sub = long[long["类型"] == kind].groupby("月份")["金额"].sum().reset_index()
        sub = sub.sort_values("月份")
        return sub["月份"].tolist(), sub["金额"].to_numpy(), "M", f"月度{kind}"
    if dataset == "每日桩基完成量":
        dp = data_io.load_daily_pile()
        if dp.empty:
            return [], np.array([]), "D", ""
        dp = dp.sort_values("日期")
        return dp["日期"].dt.strftime("%Y-%m-%d").tolist(), dp["完成量"].to_numpy(), "D", "每日桩基完成量"
    return [], np.array([]), "D", ""


def _future_labels(last_label: str, horizon: int, freq: str):
    if freq == "M":
        try:
            p = pd.Period(last_label.replace("/", "-"), freq="M")
            return [(p + i).strftime("%Y/%m") for i in range(1, horizon + 1)]
        except Exception:
            return [f"T+{i}" for i in range(1, horizon + 1)]
    else:
        try:
            d = pd.to_datetime(last_label)
            return [(d + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, horizon + 1)]
        except Exception:
            return [f"T+{i}" for i in range(1, horizon + 1)]


def run_prediction_page():
    st.subheader("📈 数据分析与预测增强")

    dataset = st.selectbox(
        "选择分析对象",
        ["汇率-CBR", "汇率-AVE", "汇率-PBC", "收支-收入", "收支-支出", "每日桩基完成量"],
        index=0,
    )
    labels, values, freq, note = _build_series(dataset)
    if len(values) < 5:
        st.warning("该数据集样本不足，无法进行可靠预测。")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        model = st.selectbox("预测模型", list(MODELS.keys()), format_func=lambda k: MODELS[k])
    with col2:
        default_m = 7 if freq == "D" else 12
        m = st.number_input("季节周期", min_value=1, max_value=60, value=default_m)
    with col3:
        horizon = st.slider("预测步长", 3, 90, 30 if freq == "D" else 12)
    with col4:
        ci = st.selectbox("置信水平", [0.90, 0.95, 0.99], index=1)

    with st.spinner("预测计算中…"):
        try:
            res = fc.forecast_series(values, m=m, model=model, horizon=horizon, ci=ci)
        except Exception as e:
            st.error(f"预测失败：{e}")
            return

    # ---- 图表 ----
    fut = _future_labels(labels[-1], horizon, freq)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=labels, y=values, mode="lines+markers", name="历史",
                             line=dict(color="#1f77b4")))
    fig.add_trace(go.Scatter(x=fut, y=res["forecast"], mode="lines+markers", name="预测",
                             line=dict(color="#e67e22", dash="dot")))
    fig.add_trace(go.Scatter(x=fut + fut[::-1], y=np.concatenate([res["upper"], res["lower"][::-1]]),
                             fill="toself", fillcolor="rgba(230,126,34,0.15)",
                             line=dict(color="rgba(0,0,0,0)"), name=f"{int(ci*100)}% 区间", hoverinfo="skip"))
    fig.update_layout(title=f"{note} 预测（模型：{MODELS[res['model']]}）",
                      xaxis_title="时间", yaxis_title="数值", template="plotly_white", height=520)
    st.plotly_chart(fig, use_container_width=True)

    # ---- 指标 ----
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("选用模型", MODELS[res["model"]].split("（")[0])
    bt = res["metrics"]
    m2.metric("拟合 MAE", f"{bt.get('MAE', float('nan')):.2f}" if bt else "—")
    m3.metric("拟合 RMSE", f"{bt.get('RMSE', float('nan')):.2f}" if bt else "—")
    m4.metric("拟合 MAPE", f"{bt.get('MAPE', float('nan'))*100:.2f}%" if bt and bt.get("MAPE") == bt.get("MAPE") else "—")

    # 回测对比表
    if res["backtest"]:
        st.markdown("**多模型回测对比（按近期留出验证）**")
        bt_df = pd.DataFrame(res["backtest"]).T.reset_index().rename(columns={"index": "模型"})
        bt_df["模型"] = bt_df["模型"].map(MODELS)
        bt_df[["MAE", "RMSE", "MAPE"]] = bt_df[["MAE", "RMSE", "MAPE"]].round(4)
        st.dataframe(bt_df, use_container_width=True)

    # 预测结果表 + 导出
    out = pd.DataFrame({"预测期": fut, "预测值": res["forecast"],
                        f"下限({int(ci*100)}%)": res["lower"], f"上限({int(ci*100)}%)": res["upper"]})
    with st.expander("📋 预测明细 / 导出"):
        st.dataframe(out, use_container_width=True)
        csv = out.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下载预测结果 CSV", data=csv, file_name=f"forecast_{dataset}.csv", mime="text/csv")

    # ---- 桩基进度推演 ----
    if dataset == "每日桩基完成量":
        st.markdown("---")
        st.markdown("**桩基进度推演**")
        target = st.number_input("完工目标（按所选序列单位）", min_value=0.0, value=float(data_io.PILE_TARGET_METERS))
        eta = fc.estimate_completion_eta(values, target=target, dates=labels)
        if eta:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("当前累计", f"{eta['last']:.0f}")
            c2.metric("剩余", f"{eta['remaining']:.0f}")
            c3.metric("近30日日均增量", f"{eta['daily_rate']:.2f}")
            c4.metric("预计剩余天数", f"{eta['days_left']:.0f}" if eta["days_left"] != float("inf") else "∞")
            if eta.get("eta_date"):
                st.info(f"按当前节奏，预计完工日期约为：**{eta['eta_date']}**（请确认序列单位与目标一致）")

    # ---- 异常检测 ----
    st.markdown("---")
    st.markdown("**异常检测**")
    am, ath = st.columns(2)
    with am:
        amethod = st.selectbox("方法", ["zscore", "iqr", "rolling_z"], index=0)
    with ath:
        athr = st.slider("阈值", 1.5, 5.0, 3.0, 0.1)
    mask, score = fc.detect_anomalies(values, method=amethod, threshold=athr, window=7)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=labels, y=values, mode="lines", name="序列"))
    if mask.any():
        fig2.add_trace(go.Scatter(x=np.array(labels)[mask].tolist(), y=values[mask],
                                  mode="markers", marker=dict(color="red", size=9), name="异常点"))
    fig2.update_layout(title=f"异常检测（{amethod}, 阈值={athr}）", template="plotly_white", height=420)
    st.plotly_chart(fig2, use_container_width=True)
    if mask.sum():
        adf = pd.DataFrame({"时间": np.array(labels)[mask], "数值": values[mask], "分数": score[mask].round(3)})
        st.dataframe(adf, use_container_width=True)

    # ---- 相关性 & 分解（仅汇率数据集展示相关矩阵） ----
    if dataset.startswith("汇率"):
        st.markdown("---")
        st.markdown("**多源汇率相关性**")
        rub = data_io.load_rub()
        corr = fc.correlation_matrix(rub[["CBR", "AVE", "PBC"]].dropna())
        figc = px.imshow(corr, text_auto=True, color_continuous_scale="Blues", title="相关系数矩阵")
        st.plotly_chart(figc, use_container_width=True)

    st.markdown("---")
    st.markdown("**季节性分解（加性）**")
    per = st.number_input("分解周期", min_value=2, max_value=min(60, len(values) // 2), value=m, key="dec_per")
    dec = fc.seasonal_decompose(values, period=per)
    figd = go.Figure()
    figd.add_trace(go.Scatter(x=labels, y=values, name="原始", line=dict(color="#1f77b4")))
    figd.add_trace(go.Scatter(x=labels, y=dec["trend"], name="趋势", line=dict(color="#2ca02c")))
    figd.add_trace(go.Scatter(x=labels, y=dec["seasonal"], name="季节", line=dict(color="#ff7f0e")))
    figd.add_trace(go.Scatter(x=labels, y=dec["resid"], name="残差", line=dict(color="#7f7f7f", width=1)))
    figd.update_layout(title="加性分解：原始 / 趋势 / 季节 / 残差", template="plotly_white", height=480)
    st.plotly_chart(figd, use_container_width=True)
