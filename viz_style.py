# -*- coding: utf-8 -*-
"""
viz_style.py — 统一的中文字体 / 图表样式管理

解决原来在多个模块里重复设置 matplotlib 字体、且一旦 SimHei.ttf 缺失就报错的问题。
现在集中注册字体并提供安全回退，新增页面无需再各自配置。
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # 无界面后端，适配 Streamlit 云端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from pathlib import Path

BASE_DIR = Path(__file__).parent
_FONTS_READY = False

PREFERRED_FONTS = ["SimHei", "Songti SC", "Arial Unicode MS", "DejaVu Sans"]


def setup_fonts() -> None:
    """注册项目内置字体并向 matplotlib 注入可用中文字体（带回退）。"""
    global _FONTS_READY
    if _FONTS_READY:
        return
    candidates = ["SimHei.ttf", "NISC18030.ttf"]
    for fname in candidates:
        fp = BASE_DIR / fname
        if fp.exists():
            try:
                fm.fontManager.addfont(str(fp))
            except Exception:
                pass
    # 选择系统中实际可用的中文字体
    available = {f.name for f in fm.fontManager.ttflist}
    chosen = [f for f in PREFERRED_FONTS if f in available] or ["DejaVu Sans"]
    plt.rcParams["font.sans-serif"] = chosen + ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.family"] = "sans-serif"
    _FONTS_READY = True


def font_prop(size: int = 14):
    """返回一个安全的 FontProperties（用于 matplotlib 标注）。"""
    setup_fonts()
    for f in plt.rcParams["font.sans-serif"]:
        try:
            return fm.FontProperties(family=f, size=size)
        except Exception:
            continue
    return fm.FontProperties(size=size)
