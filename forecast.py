# -*- coding: utf-8 -*-
"""
forecast.py — 数据分析与预测增强模块（新增）

提供纯 numpy / pandas 实现的：
  * 多种时间序列预测模型：朴素 / 季节朴素 / 移动平均 / 线性回归 / 加性 Holt-Winters
  * 自动选型（按回测 MAPE 择优）
  * 回测指标：MAE / RMSE / MAPE
  * 预测置信区间（基于样本内残差标准差）
  * 异常检测：z-score / IQR / 滚动 z-score
  * 相关性矩阵、加性季节性分解

设计原则：不依赖 statsmodels / prophet，避免云端安装失败风险；算法透明、可审计。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================================
# 基础工具
# ============================================================================
def _as_array(series) -> np.ndarray:
    return np.asarray(series, dtype=float)


def _resid_stats(resid: np.ndarray):
    resid = resid[np.isfinite(resid)]
    if resid.size == 0:
        return 0.0
    return float(np.std(resid, ddof=1))


def backtest_metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    """计算 MAE / RMSE / MAPE（pred 为对 actual 的一步/多步预测）。"""
    actual = _as_array(actual)
    pred = _as_array(pred)
    n = min(len(actual), len(pred))
    a = actual[-n:]
    p = pred[-n:]
    err = a - p
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    denom = a[np.abs(a) > 1e-9]
    mape = float(np.mean(np.abs((a - p)[np.abs(a) > 1e-9] / denom))) if denom.size else float("nan")
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


# ============================================================================
# 模型拟合
# ============================================================================
def _fit_hw(y: np.ndarray, m: int, alpha=0.3, beta=0.1, gamma=0.3):
    """加性 Holt-Winters 拟合，返回参数与预测闭包。"""
    n = len(y)
    if n < 2 * m:
        raise ValueError("样本量不足以拟合季节性模型")
    l0 = y[:m].mean()
    b0 = (y[m:2 * m].mean() - y[:m].mean()) / m
    s = (y[:m] - l0).tolist() + [0.0] * (n - m)
    l = [l0] + [0.0] * (n - 1)
    b = [b0] + [0.0] * (n - 1)
    for t in range(1, n):
        s[t] = gamma * (y[t] - l[t - 1] - b[t - 1]) + (1 - gamma) * s[t - m]
        l[t] = alpha * (y[t] - s[t]) + (1 - alpha) * (l[t - 1] + b[t - 1])
        b[t] = beta * (l[t] - l[t - 1]) + (1 - beta) * b[t - 1]

    def predict(h: int) -> float:
        return l[-1] + h * b[-1] + s[(n - 1 + h) % m]

    fitted = np.array([y[0]] + [l[t - 1] + b[t - 1] + s[t - m] for t in range(1, n)])
    return {"l": l[-1], "b": b[-1], "s": s, "m": m, "fitted": fitted, "predict": predict}


def _forecast_naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.full(h, y[-1])


def _forecast_seasonal_naive(y: np.ndarray, h: int, m: int) -> np.ndarray:
    rep = ((np.arange(h) // m) + 1)
    out = np.empty(h)
    for i in range(h):
        out[i] = y[-m + (i % m)]
    return out


def _forecast_ma(y: np.ndarray, h: int, window: int = 7) -> np.ndarray:
    w = min(window, len(y))
    val = np.mean(y[-w:])
    return np.full(h, val)


def _forecast_linear(y: np.ndarray, h: int, deg: int = 1) -> np.ndarray:
    x = np.arange(len(y))
    coef = np.polyfit(x, y, deg)
    fx = np.arange(len(y), len(y) + h)
    return np.polyval(coef, fx)


# ============================================================================
# 统一预测入口
# ============================================================================
def forecast_series(
    y: np.ndarray,
    m: int = 1,
    model: str = "auto",
    horizon: int = 12,
    alpha=0.3, beta=0.1, gamma=0.3,
    window: int = 7,
    ci: float = 0.95,
) -> dict:
    """对单条序列做预测。

    返回 dict：fitted / forecast / lower / upper / resid_sd / model / metrics / backtest
    """
    y = _as_array(y)
    y = y[np.isfinite(y)]
    n = len(y)
    if n < 3:
        raise ValueError("序列过短，无法预测")

    m = max(1, int(m))
    if m > n // 3:
        m = max(1, n // 3)

    # 候选模型
    candidates = {}
    if n >= 2:
        candidates["naive"] = lambda h: _forecast_naive(y, h)
    if m > 1 and n >= m:
        candidates["seasonal_naive"] = lambda h: _forecast_seasonal_naive(y, h, m)
    if n >= 3:
        candidates["moving_average"] = lambda h: _forecast_ma(y, h, window)
    if n >= deg_needed(deg := 1):
        candidates["linear"] = lambda h: _forecast_linear(y, h, 1)
    if n >= 2 * m:
        candidates["holt_winters"] = lambda h: np.array([_fit_hw(y, m, alpha, beta, gamma)["predict"](i + 1) for i in range(h)])

    # 自动选型：按回测 MAPE 择优
    chosen = model
    backtest = {}
    if model == "auto":
        best_mape = float("inf")
        best = "linear" if "linear" in candidates else list(candidates)[0]
        test_k = min(max(m, 3), n // 3)
        for name, f in candidates.items():
            try:
                train = y[:-test_k]
                pred = _backtest_predict(train, m, name, test_k, alpha, beta, gamma, window)
                metr = backtest_metrics(y[-test_k:], pred)
                backtest[name] = metr
                if metr["MAPE"] < best_mape:
                    best_mape = metr["MAPE"]
                    best = name
            except Exception:
                continue
        chosen = best if best else "naive"

    # 最终拟合
    if chosen == "holt_winters":
        hw = _fit_hw(y, m, alpha, beta, gamma)
        fitted = hw["fitted"]
        fc = np.array([hw["predict"](i + 1) for i in range(horizon)])
    elif chosen == "seasonal_naive":
        fitted = _forecast_seasonal_naive(y, n, m)[:n]
        fc = _forecast_seasonal_naive(y, horizon, m)
    elif chosen == "moving_average":
        fitted = np.concatenate([np.full(n - window, np.nan), _forecast_ma(y, window, window)])
        fc = _forecast_ma(y, horizon, window)
    elif chosen == "linear":
        fitted = _forecast_linear(y, n, 1)
        fc = _forecast_linear(y, horizon, 1)
    else:  # naive
        fitted = np.concatenate([[np.nan], _forecast_naive(y[1:], n - 1)])
        fc = _forecast_naive(y, horizon)

    resid = y - fitted
    sd = _resid_stats(resid)
    z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(ci, 1.96)
    lower = fc - z * sd
    upper = fc + z * sd

    return {
        "fitted": fitted,
        "forecast": fc,
        "lower": lower,
        "upper": upper,
        "resid_sd": sd,
        "model": chosen,
        "backtest": backtest,
        "metrics": backtest_metrics(y, fitted) if np.all(np.isfinite(fitted)) else {},
    }


def deg_needed(deg):
    return deg + 1


def _backtest_predict(train, m, name, h, alpha, beta, gamma, window):
    """在训练集上拟合并对未来 h 步做预测（用于回测）。"""
    if name == "naive":
        return _forecast_naive(train, h)
    if name == "seasonal_naive":
        return _forecast_seasonal_naive(train, h, m)
    if name == "moving_average":
        return _forecast_ma(train, h, window)
    if name == "linear":
        return _forecast_linear(train, h, 1)
    if name == "holt_winters":
        hw = _fit_hw(train, m, alpha, beta, gamma)
        return np.array([hw["predict"](i + 1) for i in range(h)])
    return _forecast_naive(train, h)


# ============================================================================
# 异常检测
# ============================================================================
def detect_anomalies(values, method: str = "zscore", threshold: float = 3.0, window: int = 7):
    """返回 (bool 掩码, 分数)。method: zscore / iqr / rolling_z。"""
    arr = _as_array(values)
    n = len(arr)
    mask = np.zeros(n, dtype=bool)
    score = np.zeros(n)
    if method == "zscore":
        mu, sigma = np.nanmean(arr), np.nanstd(arr, ddof=1)
        sigma = sigma if sigma > 0 else 1.0
        score = (arr - mu) / sigma
        mask = np.abs(score) > threshold
    elif method == "iqr":
        q1, q3 = np.nanpercentile(arr, [25, 75])
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        score = np.where(arr < lo, (lo - arr), np.where(arr > hi, (arr - hi), 0.0))
        mask = (arr < lo) | (arr > hi)
    elif method == "rolling_z":
        w = min(window, n)
        roll_mean = pd.Series(arr).rolling(w, min_periods=max(2, w // 2), center=True).mean().to_numpy()
        roll_std = pd.Series(arr).rolling(w, min_periods=max(2, w // 2), center=True).std(ddof=1).to_numpy()
        roll_std = np.where(np.nan_to_num(roll_std) <= 0, np.nanstd(arr, ddof=1) or 1.0, roll_std)
        score = (arr - roll_mean) / roll_std
        mask = np.abs(score) > threshold
    return mask, score


# ============================================================================
# 相关性 & 季节性分解
# ============================================================================
def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    num = df.select_dtypes(include=[np.number])
    return num.corr()


def seasonal_decompose(values, period: int) -> dict:
    """加性季节性分解：返回 trend / seasonal / resid（均为与输入等长数组）。"""
    arr = _as_array(values)
    n = len(arr)
    if period < 2 or n < 2 * period:
        # 退化为仅趋势（移动平均）
        trend = pd.Series(arr).rolling(period if period >= 2 else 3, center=True).mean().to_numpy()
        return {"trend": trend, "seasonal": np.zeros(n), "resid": arr - trend}
    trend = pd.Series(arr).rolling(period, center=True, min_periods=2).mean().to_numpy()
    detr = arr - trend
    # 周期性均值
    seas = np.full(n, np.nan)
    for k in range(period):
        idx = np.arange(k, n, period)
        if len(idx):
            seas[idx] = np.nanmean(detr[idx])
    seas = np.where(np.isnan(seas), 0.0, seas)
    seas = seas - np.nanmean(seas)
    resid = arr - trend - seas
    return {"trend": trend, "seasonal": seas, "resid": resid}


# ============================================================================
# 进度推演（桩基 ETA）
# ============================================================================
def estimate_completion_eta(cum_series: np.ndarray, target: float, dates=None) -> dict:
    """根据累计完成量序列估算：剩余量、近 30 日平均日增量、预计完工剩余天数/日期。"""
    arr = _as_array(cum_series)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {}
    last = float(arr[-1])
    remaining = max(0.0, target - last)
    recent = arr[-min(30, len(arr)):]
    if len(recent) >= 2:
        daily_rate = (recent[-1] - recent[0]) / (len(recent) - 1)
    else:
        daily_rate = 0.0
    if daily_rate > 1e-9:
        days_left = remaining / daily_rate
    else:
        days_left = float("inf")
    eta_date = None
    if np.isfinite(days_left) and dates is not None and len(dates):
        try:
            start = pd.to_datetime(dates[-1])
            eta_date = (start + pd.Timedelta(days=float(days_left))).strftime("%Y-%m-%d")
        except Exception:
            eta_date = None
    return {
        "last": last,
        "target": target,
        "remaining": remaining,
        "daily_rate": daily_rate,
        "days_left": days_left,
        "eta_date": eta_date,
        "progress_pct": min(100.0, last / target * 100) if target else 0.0,
    }
