# -*- coding: utf-8 -*-
"""
data_io.py — FCC 项目展示系统 · 集中式数据加载层

职责：
  * 统一管理所有 Excel / CSV 数据源的读取路径；
  * 通过 @st.cache_data 缓存解析结果，避免每次交互重复读取大文件；
  * 提供“宽表 -> 长表”的清洗函数，供分析与预测模块复用。

影响范围：替代原 FCC交互_t1.py 中散落的 pd.read_excel 调用，所有页面统一从此处取数。
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent


# ----------------------------------------------------------------------------
# 通用读取（带缓存）
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="正在读取数据文件…", ttl=3600)
def load_excel(name: str, sheet=None, header: int = 0):
    """带缓存的 Excel 读取；文件不存在时返回 None。"""
    path = BASE_DIR / name
    if not path.exists():
        return None
    if sheet is not None:
        return pd.read_excel(path, sheet_name=sheet, engine="openpyxl", header=header)
    return pd.read_excel(path, engine="openpyxl", header=header)


@st.cache_data(show_spinner=False, ttl=3600)
def load_csv(name: str):
    path = BASE_DIR / name
    if not path.exists():
        return None
    return pd.read_csv(path)


# ----------------------------------------------------------------------------
# 业务表专用加载器
# ----------------------------------------------------------------------------
def _coerce_numeric(series: pd.Series) -> pd.Series:
    """将可能的俄式逗号小数文本（如 12,3853）安全转为 float。"""
    if pd.api.types.is_numeric_dtype(series):
        return series
    return (
        series.astype(str)
        .str.replace(",", ".", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.strip()
        .replace({"": np.nan, "nan": np.nan, "—": np.nan, "—": np.nan})
        .pipe(pd.to_numeric, errors="coerce")
    )


def load_rub() -> pd.DataFrame:
    """卢布汇率日序列：日期 / CBR / AVE / PBC（数值化清洗逗号小数）。"""
    df = load_excel("rub.xlsx", sheet="Sheet1")
    if df is None:
        return None
    df.columns = [str(c).replace("\n", " ").strip() for c in df.columns]
    for col in ["CBR", "AVE", "PBC", "Russia CBR", "China PBC"]:
        if col in df.columns:
            df[col] = _coerce_numeric(df[col])
    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce", dayfirst=True)
    return df.dropna(subset=["日期"]) if "日期" in df.columns else df


def load_main_table():
    """主表（成本结构树）：content / amount / 一级 / 二级 / 三级。"""
    return load_excel("主表.xlsx", sheet="Sheet1")


def load_perm():
    return load_excel("perm.xlsx", sheet="Sheet1")


def load_staff():
    return load_excel("staff.xlsx", sheet="Sheet1")


def load_suppliers_excel():
    return load_excel("供应商.xlsx")


def load_payments():
    return load_excel("fcc_payments.xlsx", sheet="Sheet1")


def load_monthly():
    return load_excel("月度收支.xlsx", sheet="Sheet1")


def load_balance():
    return load_excel("balance.xlsx", sheet="Sheet1")


def load_wison():
    return load_excel("wison.xlsx")


def load_xiang():
    return load_excel("xiang.xlsx")


def load_data_sheet(sheet_name: str):
    return load_excel("data.xlsx", sheet=sheet_name)


# ----------------------------------------------------------------------------
# 复杂结构解析（宽表 -> 长表）
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def load_inout_long() -> pd.DataFrame:
    """解析 inout.xlsx 宽表为长表：月份 / 排序月份 / 类型 / 金额。"""
    path = BASE_DIR / "inout.xlsx"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_excel(path, header=None, engine="openpyxl")
    months = raw.iloc[0, 1:].dropna().tolist()

    clean = []
    for _, row in raw.iterrows():
        if pd.isna(row[0]) or row[0] is None:
            continue
        category = str(row[0]).strip()
        values = row[1:1 + len(months)].tolist()
        if any(k in category for k in ["收入", "收款", "应收"]):
            data_type = "收入"
        elif any(k in category for k in ["支出", "费用", "付款", "应付"]):
            data_type = "支出"
        else:
            continue
        for month, val in zip(months, values):
            try:
                num = float(str(val).replace(",", "")) if pd.notna(val) else 0.0
                if num > 0:
                    clean.append({
                        "月份": str(month).strip(),
                        "排序月份": _to_month(str(month).strip()),
                        "类型": data_type,
                        "金额": num,
                    })
            except Exception:
                continue
    if not clean:
        return pd.DataFrame()
    df = pd.DataFrame(clean).sort_values("排序月份").drop(columns="排序月份")
    df["月份"] = df["月份"].astype(str)
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def load_daily_pile() -> pd.DataFrame:
    """解析 DailyPile.xlsx（首行为表头的脏数据）为干净的 日期/完成量 序列。"""
    path = BASE_DIR / "DailyPile.xlsx"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_excel(path, sheet_name="Sheet1", header=None, engine="openpyxl")
    dates, vals = [], []
    for _, r in raw.iterrows():
        d, v = r[0], r[1]
        if pd.isna(d):
            continue
        dates.append(pd.to_datetime(d, errors="coerce"))
        try:
            vals.append(float(v))
        except Exception:
            vals.append(np.nan)
    df = pd.DataFrame({"日期": dates, "完成量": vals}).dropna()
    df = df.sort_values("日期").reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def load_pile_progress() -> dict:
    """解析 pile_副本.xlsx 的“桩基付款”表，返回桩基总数/已完成字典与汇总。"""
    path = BASE_DIR / "pile_副本.xlsx"
    if not path.exists():
        return {}
    df = pd.read_excel(path, sheet_name="桩基付款", engine="openpyxl")
    df = df.set_index("阶段").transpose()
    total = df["桩基总数"].astype(float)
    done = df["截至0425完成"].astype(float)
    return {
        "pile_ids": total.index.tolist(),
        "total": total,
        "done": done,
        "total_sum": float(total.sum()),
        "done_sum": float(done.sum()),
    }


def _to_month(month_str: str) -> datetime:
    try:
        return datetime.strptime(month_str, "%Y/%m")
    except Exception:
        try:
            return datetime.strptime(month_str, "%Y-%m")
        except Exception:
            return datetime.max


# 桩基总目标（米），来自原始注释“桩基总数111555米”
PILE_TARGET_METERS = 111555
