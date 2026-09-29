# -*- coding: utf-8 -*-
"""
github_sync.py — 系统与 GitHub 集成应用（新增页面）

能力：
  * 通过 GitHub REST API 从指定仓库拉取最新数据文件（如 rub.xlsx / inout.xlsx）到本地；
  * 自动备份被覆盖的旧文件（backup/ 目录，带时间戳）；
  * 查看仓库最近提交记录（SHA / 作者 / 时间 / 说明）；
  * 支持私有库：Token 来自 .streamlit/secrets.toml 的 [github] token，或在页面临时输入；
  * 全程异常捕获，无网络/无 Token 时给出清晰指引，不中断应用。

影响范围：新增 GitHub 数据同步入口，使“系统数据来源”可由 GitHub 仓库统一托管与版本化。
"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import requests
from pathlib import Path
import base64
import json
from datetime import datetime

BASE_DIR = Path(__file__).parent
BACKUP_DIR = BASE_DIR / "backup"
API = "https://api.github.com"

# 默认需要同步的数据文件（与系统其余模块一致）
DEFAULT_FILES = [
    "rub.xlsx", "inout.xlsx", "perm.xlsx", "pile_副本.xlsx",
    "主表.xlsx", "data.xlsx", "月度收支.xlsx", "供应商.xlsx",
    "staff.xlsx", "balance.xlsx", "DailyPile.xlsx",
]


def _get_token() -> str:
    try:
        return st.secrets.get("github", {}).get("token", "")
    except Exception:
        return ""


def _headers(token: str) -> dict:
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _backup(local: Path):
    if not local.exists():
        return
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    local.with_name(f"{local.stem}_{ts}{local.suffix}").write_bytes(local.read_bytes())


def _fetch_contents(owner, repo, branch, path, token):
    url = f"{API}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    r = requests.get(url, headers=_headers(token), timeout=20)
    r.raise_for_status()
    return r.json()


def _fetch_commits(owner, repo, branch, token, n=10):
    url = f"{API}/repos/{owner}/{repo}/commits?sha={branch}&per_page={n}"
    r = requests.get(url, headers=_headers(token), timeout=20)
    r.raise_for_status()
    return r.json()


def run_github_page():
    st.subheader("🔗 数据同步（GitHub 集成）")

    token = _get_token()
    with st.expander("仓库配置", expanded=True):
        c1, c2 = st.columns(2)
        owner = st.text_input("仓库所有者(owner)", value=st.session_state.get("gh_owner", ""))
        repo = st.text_input("仓库名(repo)", value=st.session_state.get("gh_repo", ""))
        c2_1, c2_2 = st.columns(2)
        branch = c2_1.text_input("分支", value=st.session_state.get("gh_branch", "main"))
        use_token = c2_2.text_input("Token（可选，私有库/提高限额）", value=token,
                                    type="password", help="也可配置于 .streamlit/secrets.toml 的 [github] token")
        files = st.multiselect("需要同步的数据文件", DEFAULT_FILES,
                               default=DEFAULT_FILES, key="gh_files")
        if st.button("保存配置到会话"):
            st.session_state.update(gh_owner=owner, gh_repo=repo, gh_branch=branch)
            st.success("配置已保存到会话状态")

    if not (owner and repo):
        st.info("请先填写 owner / repo 以启用 GitHub 同步。示例：owner=`your-name`，repo=`FCC-app`。")
        st.markdown(
            "说明：本页面通过 GitHub REST API 拉取仓库内最新数据文件覆盖本地同名文件，"
            "被覆盖文件会自动备份至 `backup/`。也可将本仓库直接托管到 Streamlit Community Cloud 实现自动部署。"
        )
        return

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("⬇️ 从 GitHub 拉取最新数据", use_container_width=True):
            if not files:
                st.warning("请选择至少一个文件")
            else:
                done, failed = [], []
                for f in files:
                    try:
                        meta = _fetch_contents(owner, repo, branch, f, use_token)
                        content = base64.b64decode(meta["content"])
                        local = BASE_DIR / f
                        _backup(local)
                        local.write_bytes(content)
                        done.append(f)
                    except Exception as e:
                        failed.append((f, str(e)[:120]))
                if done:
                    st.success(f"已更新 {len(done)} 个文件：{', '.join(done)}")
                if failed:
                    st.error("以下文件同步失败：")
                    for f, e in failed:
                        st.write(f"- {f}: {e}")
    with col_b:
        if st.button("🔄 查看最近提交", use_container_width=True):
            try:
                commits = _fetch_commits(owner, repo, branch, use_token, n=10)
                rows = []
                for c in commits:
                    rows.append({
                        "SHA": c["sha"][:7],
                        "作者": c["commit"]["author"]["name"],
                        "时间": c["commit"]["author"]["date"][:10],
                        "说明": c["commit"]["message"].split("\n")[0][:40],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            except Exception as e:
                st.error(f"获取提交失败：{e}")
                if "403" in str(e) or "401" in str(e):
                    st.info("若为私有库或触发限流，请在配置中填写 Token。")

    st.markdown("---")
    st.caption(
        "提示：在 Streamlit Community Cloud 部署时，可在 App 设置的 Secrets 中配置 "
        "`[github] token = \"ghp_xxx\"`；公开仓库可留空（受 60 次/小时 匿名限额）。"
    )
