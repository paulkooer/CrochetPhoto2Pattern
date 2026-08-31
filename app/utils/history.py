"""图解历史持久化（S4）——SQLite 单文件，跨会话恢复。

刷新即丢是单页 Streamlit 应用的固有局限（此前只有手动备份 JSON）。
这里把完整结果存进本地 SQLite（用户目录，不进仓库），侧栏可列出/
恢复/删除。经 CROCHET_HISTORY_DB 环境变量可重定向（测试用）。

设计约束：
- 结果以完整 JSON blob 存储（含 analysis/structure/params/result_id），
  恢复即"导入备份"路径的自动化——复用 render_results 的导入校验。
- 所有操作在调用时打开连接（短连接），Streamlit 多会话安全。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns (
    rid        TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    summary    TEXT NOT NULL,
    blob       TEXT NOT NULL,
    preview    TEXT,
    title      TEXT
)
"""


def _db_path() -> Path:
    env = os.getenv("CROCHET_HISTORY_DB")
    if env:
        return Path(env)
    return Path.home() / ".crochet_photo2pattern" / "history.db"


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(_SCHEMA)
    try:  # 旧库迁移（K2/U26）：已有表缺列逐一补齐（幂等）
        conn.execute("ALTER TABLE patterns ADD COLUMN preview TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE patterns ADD COLUMN title TEXT")
    except sqlite3.OperationalError:
        pass
    return conn


def _summary(result: Dict[str, Any]) -> str:
    analysis = result.get("analysis") or {}
    params = result.get("params") or {}
    parts = params.get("parts") or []
    return (f"{analysis.get('body_type', '?')} · "
            f"头{analysis.get('head_diameter_cm', '?')}cm · "
            f"高{analysis.get('height_cm', '?')}cm · "
            f"{len(parts)} 部件")


def save_result(result: Dict[str, Any], title: Optional[str] = None) -> str:
    """保存完整结果（含 result_id），返回 rid。重复 rid 覆盖。

    title（U26）：用户可命名的标题（None 时侧栏回退摘要）。
    V5：入库前最小结构校验——缺 analysis/params.parts 的数据会让
    侧栏/载入路径渲染崩溃，在入口拦截。
    """
    rid = result.get("result_id")
    if not rid:
        raise ValueError("result 缺少 result_id")
    analysis = result.get("analysis")
    params = result.get("params")
    if (not isinstance(analysis, dict)
            or not isinstance(params, dict)
            or not isinstance(params.get("parts"), list)):
        raise ValueError("result 缺少有效的 analysis / params.parts")
    # pydantic 对象必须 model_dump（default=str 会把部件存成字符串，
    # 恢复后渲染层崩溃）
    blob = json.dumps(
        result, ensure_ascii=False,
        default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o))
    preview = result.get("preview")
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO patterns "
            "(rid, created_at, summary, blob, preview, title) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (rid, time.time(), _summary(result), blob, preview,
             title.strip() if title and title.strip() else None))
    return rid


def list_results(limit: int = 30, query: Optional[str] = None,
                 color: Optional[str] = None) -> List[Dict[str, Any]]:
    """最近保存的结果元信息（新→旧）。

    query（U26）：匹配摘要或完整 blob 的子串（LIKE）；color：匹配任一
    圈配色色名。preview 直接随行返回（K2：消除侧栏逐条 load_result 的
    N+1 全量读取）。
    """
    sql = ("SELECT rid, created_at, summary, preview, title FROM patterns")

    # F30：LIKE 元字符按字面匹配。转义符用 "!"（不用反斜杠——反斜杠
    # 在 Python/SQL 双层转义下极易写错，Opus 5 审查与本轮实施均踩过）。
    # query 只搜 summary+title（blob 是 JSON 序列化文本，键名必含 "_"，
    # 搜它会让 "_" 命中全部记录）；按色筛选仍走 blob（U26 结构化筛选）
    esc_ch = "!"
    escape_clause = "ESCAPE '" + esc_ch + "'"

    def _like_escape(text: str) -> str:
        return (text.replace(esc_ch, esc_ch * 2)
                    .replace("%", esc_ch + "%")
                    .replace("_", esc_ch + "_"))

    conds, params = [], []
    if query:
        e = _like_escape(query)
        conds.append("(summary LIKE ? " + escape_clause
                     + " OR title LIKE ? " + escape_clause + ")")
        like = "%" + e + "%"
        params += [like, like]
    if color:
        conds.append("blob LIKE ? " + escape_clause)
        params.append('%"' + _like_escape(color) + '"%')
    if conds:
        sql += " WHERE " + " AND ".join(conds)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{"rid": r, "created_at": t, "summary": s, "preview": pv,
             "title": ti}
            for r, t, s, pv, ti in rows]


def load_result(rid: str) -> Optional[Dict[str, Any]]:
    """按 rid 取完整结果；不存在/损坏返回 None（F31）。

    F25：title 存在独立列（不在 blob 内），取回后写入 result["title"]，
    使"载入 → 再存入"往返保留用户命名。blob 手改/截断为非法 JSON 时
    吞掉解码错误返回 None——与"不存在"同一出口，调用方统一提示。
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT blob, title FROM patterns WHERE rid = ?", (rid,)).fetchone()
    if row is None:
        return None
    try:
        data = json.loads(row[0])
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        import logging
        logging.getLogger(__name__).warning("历史记录 %s 损坏: %s", rid, e)
        return None
    if row[1]:
        data["title"] = row[1]
    return data


def delete_result(rid: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM patterns WHERE rid = ?", (rid,))


def format_time(created_at: float) -> str:
    return time.strftime("%m-%d %H:%M", time.localtime(created_at))
