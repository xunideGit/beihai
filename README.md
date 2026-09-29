# FCC 项目展示系统（Streamlit）

面向海外（俄罗斯彼尔姆）工程项目的经营数据可视化与预测分析平台，基于 Streamlit 构建。
涵盖资金收支、卢布汇率、桩基进度、人力构成、供应商、合同与任务管理，并新增 **时间序列预测** 与 **GitHub 数据同步** 能力。

## 功能导航

| 页面 | 说明 |
| --- | --- |
| 月度收支图表 | 收入/支出月度对比、累计与支出占比 |
| 银行账户余额 | 各币种账户余额快照 |
| 资金全景展示 | 各项支出柱状+占比、按支出项下钻明细 |
| 惠生合同数据 | 合同/开票/兑换记录图片轮播与明细 |
| 供应商信息表 | 按供应商名称搜索各工作表 |
| 卢布汇率走势 | CBR/AVE/PBC 多源汇率走势（已修复逗号小数解析） |
| 付款单统计表 | 付款单明细 |
| 收支明细台账 | 月度收支台账 |
| 人力资源分布 | 国籍/性别/职务多维构成 |
| 桩基进度看板 | 各桩基完成数量与完成比例 |
| 每日桩基进度 | 每日完成量柱状图 |
| 资金结构展示 | 一/二/三级成本树状图 |
| 付款紧急程度 | 四象限用款计划 |
| 任务管理模块 | 甘特图与任务增删改 |
| 📈 预测分析 | **新增**：汇率/收支/桩基预测、异常检测、相关性、季节分解 |
| 🔗 GitHub 数据同步 | **新增**：从 GitHub 仓库拉取最新数据、查看提交 |

## 目录结构（重构后）

```
FCC-app-main/
├── streamlit_app.py        # 统一入口（原 FCC交互_t1.py 模块化重构）
├── data_io.py              # 集中式、带缓存的数据加载层
├── viz_style.py            # 中文字体/样式统一管理
├── analysis.py             # 业务分析函数集
├── forecast.py             # 预测引擎（Holt-Winters/Linear/MA/异常/相关性/分解）
├── prediction_ui.py        # 预测分析页面
├── github_sync.py          # GitHub 数据同步页面
├── gantt_module.py         # 任务甘特模块
├── wison.py / xiang.py / balance.py / DailyPile1.py  # 业务子模块
├── .github/workflows/ci.yml# 自动化测试与 lint
├── .streamlit/config.toml  # 主题与服务器配置
├── tests/                  # pytest 单元测试
└── *.xlsx / *.png / *.ttf  # 数据与字体资源
```

## 本地运行

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

> 访问需输入动态口令：`fcc` + 当日日期（格式 `YYYYMMDD`，如 `fcc20260929`）。

## 预测功能说明

预测引擎（`forecast.py`）为纯 `numpy/pandas` 实现，无需 `statsmodels`/`prophet`，云端安装零风险：

- **模型**：朴素、季节朴素、移动平均、线性回归、加性 Holt-Winters；`auto` 按近期回测 MAPE 自动择优。
- **指标**：MAE / RMSE / MAPE 回测对比。
- **区间**：基于样本内残差标准差的置信区间。
- **增强**：z-score / IQR / 滚动 z-score 异常检测；相关性热力图；加性季节性分解；桩基完工 ETA 推演。

## GitHub 集成

1. **代码托管**：本仓库即项目源码，已配置 `.github/workflows/ci.yml`，推送/PR 自动执行 lint + pytest。
2. **应用内数据同步**：在「🔗 GitHub 数据同步」页填写 `owner/repo/branch`，即可通过 GitHub REST API 拉取仓库内最新 `xlsx` 覆盖本地（旧文件自动备份至 `backup/`），或查看最近提交。私有库可在 `.streamlit/secrets.toml` 配置：
   ```toml
   [github]
   token = "ghp_xxx"
   ```
3. **一键部署**：在 [Streamlit Community Cloud](https://streamlit.io/cloud) 关联本仓库，入口设为 `streamlit_app.py` 即可自动部署；Secret 中配置上述 token 与 `bypass_auth = true` 可跳过口令。

## 测试

```bash
pip install -r requirements-dev.txt
pytest -q
```
