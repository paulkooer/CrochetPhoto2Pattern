"""Chapter 2 of the result page: the structure table and schematic preview."""
from __future__ import annotations

import streamlit as st

from app.models.colors import resolve_display_color, screen_swatch_suffix
from app.schemas import ResultData
from app.ui.design_system import section_heading
from app.ui.result_analysis import _silhouette_verifications, md_safe
from app.utils.color_labels import display_color_name

# 内部形状枚举 → 用户可读名称（结构表与部件圈序共用；未知值原样显示）
_SHAPE_LABELS: dict[str | None, str | None] = {
    "sphere": "球形", "cylinder": "圆柱", "cup": "开口杯形",
    "profile": "照片轮廓", "onepiece": "头身一体",
}


def structure_table_rows(result: ResultData) -> list[dict[str, object]]:
    """结构表行。当前基础色读图解，原始结构色保留照片或模板记录。"""
    structure = result.get("structure") or {}
    params = result.get("params") or {}
    displays = params.get("display_colors")
    displays = displays if isinstance(displays, dict) else None
    params_by_name = {
        part.get("name"): part
        for part in params.get("parts") or []
        if isinstance(part, dict) and isinstance(part.get("name"), str)
    }
    id_to_name = {
        part_id: part.get("name", "?")
        for part in structure.get("parts", [])
        if isinstance(part, dict) and isinstance(part_id := part.get("part_id"), str) and part_id
    }
    rows: list[dict[str, object]] = []
    for structure_part in structure.get("parts", []):
        if not isinstance(structure_part, dict):
            continue
        dims = []
        if structure_part.get("diameter_cm"):
            dims.append(f"直径 {structure_part['diameter_cm']}cm")
        if structure_part.get("height_cm"):
            dims.append(f"高 {structure_part['height_cm']}cm")
        if structure_part.get("length_cm"):
            dims.append(f"长 {structure_part['length_cm']}cm")
        connections = []
        for instance in structure_part.get("instances", []) or []:
            if not isinstance(instance, dict):
                continue
            for attachment in instance.get("attachments", []) or []:
                if not isinstance(attachment, dict):
                    continue
                target_id = attachment.get("target_part_id", "?")
                target = id_to_name.get(target_id, target_id)
                connections.append(
                    f"{instance.get('instance_id', '?')} → "
                    f"{target}.{attachment.get('target_anchor', '?')}"
                    f"（{attachment.get('method', 'sewn')}）"
                )
        shape = structure_part.get("shape", "—")
        name = structure_part.get("name")
        pattern_part = params_by_name.get(name) if isinstance(name, str) else None
        current = pattern_part.get("color") if isinstance(pattern_part, dict) else None
        current_label = display_color_name(current if isinstance(current, str) and current else "—")
        if isinstance(current, str) and current:
            current_label = f"{current_label}{screen_swatch_suffix(current, displays)}"
        rows.append({
            "部件": structure_part.get("name", "?"),
            "数量": structure_part.get("count", 1),
            # shape 正常是字符串；非标量（旧备份注入的 dict/list）会让 dict.get
            # 抛 unhashable TypeError，这里降级为「—」而非崩溃。
            "形状": _SHAPE_LABELS.get(shape, shape) if isinstance(shape, (str, type(None))) else "—",
            "尺寸": "，".join(dims) or "—",
            "连接": "；".join(connections) or "独立部件 / 未记录",
            "当前基础色": current_label,
            "原始结构色": display_color_name(structure_part.get("color", "—")),
        })
    return rows


def _unresolved_copy_colors(result: ResultData) -> list[str]:
    """部件主色或逐份颜色里，没有显示色、因此不能画成旧色的名称。"""
    params = result.get("params") or {}
    displays = params.get("display_colors")
    displays = displays if isinstance(displays, dict) else None
    missing: list[str] = []
    for part in params.get("parts") or []:
        if not isinstance(part, dict):
            continue
        candidates = [part.get("color"), *(part.get("instance_colors") or [])]
        for color in candidates:
            if (isinstance(color, str) and color
                    and resolve_display_color(color, displays) is None
                    and color not in missing):
                missing.append(color)
    return missing


def render_structure(result: ResultData) -> None:
    """部件结构表、轮廓对照和结构 JSON。"""
    structure = result["structure"]
    # Section 2: Structure
    section_heading(2, "部件结构设计（基础形状）")
    try:
        _verifications = _silhouette_verifications(result)
    except Exception as e:  # 可视化失败不影响主流程
        _verifications = None
        st.caption(f"轮廓可视化不可用：{md_safe(e)}")
    if _verifications:
        with st.expander("轮廓对应验证（生成侧影 vs 照片剖面）", expanded=False):
            from app.ui.design_system import html_box

            for _name, _svg in _verifications:
                st.markdown(html_box(_svg, 320), unsafe_allow_html=True)
                st.caption(f"{md_safe(_name)}：逐圈针数反渲染的侧影（蓝）"
                           "与照片剖面（橙虚线）")
    rows = structure_table_rows(result)
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("当前基础色是图解正在使用的颜色。原始结构色是照片或模板最初记录的颜色，"
                   "手工改色不会改写它。连接来自结构模板推断，并非单张照片的三维测量；"
                   "坐标、位置和旋转细节见「查看结构 JSON」。")
        with st.expander("3D 结构预览（示意）", expanded=False):
            from app.ui.preview3d import structure_preview_html

            _pv = structure_preview_html(result)
            if _pv:
                from app.ui.design_system import html_box

                # 静态等距 SVG——st.html 的净化器剥 <svg>/<script>，交互
                # canvas 无可用脚本通道，与其他图形同走 markdown
                st.markdown(html_box(_pv, 420), unsafe_allow_html=True)
                if any(part.get("color") in ("skin", "body")
                       for part in (result.get("params") or {}).get("parts", [])):
                    st.caption("待选色使用示意颜色，请根据实际毛线选色。")
                from app.models.parts import _part_instance_colors

                _params_parts = (result.get("params") or {}).get("parts", [])
                _striped = any(
                    any((rd.get("color") or part.get("color")) != part.get("color")
                        for rd in (part.get("rounds") or []))
                    for part in _params_parts)
                _per_copy = any(_part_instance_colors(part) is not None
                                for part in _params_parts)
                _missing = _unresolved_copy_colors(result)
                if _missing:
                    st.caption("这些颜色没有显示色，3D 使用中性灰，没有沿用部件原来的颜色："
                               + "、".join(md_safe(color) for color in _missing) + "。")
                if _per_copy:
                    st.caption("3D 预览按各份实体的颜色示意；未单独选色的份沿用部件主色。"
                               "不显示逐圈条纹，请以逐圈图解为准。")
                elif _striped:
                    st.caption("3D 预览按部件主色示意：不显示逐圈条纹；"
                               "请以逐圈图解与材料清单为准。")
            else:
                st.caption("当前结构无可预览的实体部件。")
        with st.expander("查看结构 JSON"):
            if structure.get("schema_version") == "2.0":
                st.caption(
                    "结构 v2 坐标：x 左−右+，y 底部0→顶部1，z 后−前+；"
                    "位置、旋转和连接来自模板推断，并非单张照片的三维测量。")
            for structure_part in structure.get("parts", []):
                st.json(structure_part)
