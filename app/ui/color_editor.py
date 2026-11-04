"""结果页的毛线选色面板：整件、单份实体与一体件分段选色。

UI 只做收集与展示：所有配色语义都在 ``app/services/color_selection.py``（纯函数，
可离线单测），提交一律走既有 ``edit_history`` 的预览/应用/撤销。规格见
``docs/part-color-selection.md``。
"""
from __future__ import annotations

import streamlit as st

from app.models.colors import YARN_COLORS
from app.models.parts import _ONE_PIECE_NAME
from app.schemas import ResultData
from app.services.color_selection import (
    MAX_COLOR_NAME,
    MODE_INHERIT,
    MODE_KEEP_STRIPES,
    MODE_UNIFORM,
    apply_color_change,
    color_change_preview,
    color_origin_of,
    instance_labels,
    one_piece_neck_index,
    parts_of,
)
from app.ui.edit_history import preview_edit
from app.utils.color_labels import is_reserved_placeholder

_CUSTOM = "自定义颜色名…"
_YARN_NAMES = [name for _rgb, name in YARN_COLORS]
_ORIGIN_TEXT = {
    "instance": "当前：至少一份实体已单独选色；其余份沿用部件配色。",
    "manual": "当前：部件基础色由你手动选择（不是照片识别结果）。",
    "unrecorded": "当前：颜色来源未记录，可能来自照片、模板或先前的手工修改。",
}


def _color_input(label: str, key: str, current: str | None, *, help_text: str = "") -> str | None:
    """色表下拉或自定义名称；返回用户输入的颜色名（未填写时 None）。"""
    options = [*_YARN_NAMES, _CUSTOM]
    # 色表内沿用当前色；已有自定义名沿用并可在输入框里改；保留占位值（skin/body）
    # 或未指定时给首个色表颜色——绝不把内部占位值当成用户已选中的颜色。
    if isinstance(current, str) and current in _YARN_NAMES:
        default = current
    elif isinstance(current, str) and current and not is_reserved_placeholder(current):
        default = _CUSTOM
    else:
        default = _YARN_NAMES[0]
    selected = st.selectbox(label, options, index=options.index(default),
                            key=f"{key}_pick", help=help_text or None)
    if selected != _CUSTOM:
        return selected
    existing = (str(current) if isinstance(current, str) and current
                and current not in _YARN_NAMES and not is_reserved_placeholder(current) else "")
    typed = st.text_input(
        "自定义颜色名", value=existing, max_chars=MAX_COLOR_NAME, key=f"{key}_custom",
        help="自定义名称只用于图解与显示；不提供品牌色号或用量依据。")
    return typed.strip() or None


def _display(color: object) -> object:
    from app.utils.color_labels import display_color_name

    return display_color_name(color)


def _preview_detail(preview: dict) -> dict:
    """预览载荷 → 预览面板的表格与提示（edit_history 原样渲染）。"""
    captions = []
    if preview.get("scope") == "instance":
        captions.append(f"只改第 {int(preview['instance_index']) + 1} 份实体；"
                        "其余份的配色与材料用量不变。")
    if preview.get("scope") == "sections":
        captions.append(f"分段边界：第 {preview['neck_row']} 圈之后属于身体段"
                        "（来自图解中记录的「此处为颈部」标记）。")
    if preview.get("kept"):
        captions.append("已指定颜色的圈按「保留已有条纹」保留，不会被覆盖。")
    warnings = [
        "已钩出的旧颜色不会因为图解改色而改变；勾选记录不代表实物无需返工。",
    ]
    if preview.get("mode") == MODE_UNIFORM and preview.get("scope") == "part":
        warnings.append("统一换色会覆盖该部件的全部逐圈颜色（含条纹与手改颜色）；"
                        "也会覆盖逐份配色；被覆盖的颜色只能靠撤销回到修改前。")
    if preview.get("scope") == "sections":
        warnings.append("分段选色会覆盖两段的逐圈颜色与逐份配色，包括先前手工选择的颜色。")
    if preview.get("scope") == "instance":
        if preview.get("mode") == MODE_INHERIT:
            warnings.append("该份将恢复使用部件的逐圈颜色和换线步骤。")
        else:
            warnings.append("单独改色的份整份使用该颜色，不再按圈次说明里的换线步骤换色；"
                            "3D 预览也只按部件主色示意。")
    return {
        "captions": captions,
        "affected": [{**({"实体": row["实体"]} if "实体" in row else {}),
                      "圈号": row["圈号"], "旧色": _display(row["旧色"]),
                      "新色": _display(row["新色"])} for row in preview.get("affected", [])],
        "kept": [{**({"实体": row["实体"]} if "实体" in row else {}),
                  "圈号": row["圈号"], "颜色": _display(row["颜色"])}
                 for row in preview.get("kept", [])],
        "materials": preview.get("materials", []),
        "warnings": warnings,
    }


def _submit(result: ResultData, slot: str, **change) -> None:
    from app.ui.result_renderer import md_safe

    try:
        detail = _preview_detail(color_change_preview(result, **change))
        preview_edit(slot, result, apply_color_change(result, **change), detail=detail)
    except Exception as exc:
        st.error(f"选色失败：{md_safe(exc)}")


def render_color_editor(result: ResultData, slot: str) -> None:
    params = result["params"]
    parts = parts_of(params)
    if not parts:
        return
    rid = result.get("result_id") or slot
    with st.expander("毛线选色", expanded=False):
        st.caption("为整个部件选色，也可以只改某一份实体；一体头身可按头部段与身体段"
                   "分别选色。人工选择只写入图解颜色，不改写照片分析结果。")
        names = [part["name"] for part in parts]
        index = st.selectbox("选择部件", range(len(names)), format_func=lambda i: names[i],
                             key=f"edit_{rid}_color_part")
        part = parts[index]
        name = names[index]
        prefix = f"edit_{rid}_color{index}"
        st.caption(_ORIGIN_TEXT[color_origin_of(part)])

        quantity = max(1, min(20, int(part.get("quantity", 1) or 1)))
        is_one_piece = name == _ONE_PIECE_NAME
        neck = one_piece_neck_index(part) if is_one_piece else None
        scopes = ["整个部件"]
        from app.services.color_identity import has_stable_copy_ids

        if quantity > 1 and has_stable_copy_ids(result, part):
            scopes.append("仅所选实体（整份统一换色）")
            if part.get("instance_colors"):
                scopes.append("仅所选实体（恢复部件配色）")
        elif quantity > 1:
            st.caption("该部件缺少稳定的实体身份，只能对整个部件选色。")
        if is_one_piece and neck is not None:
            scopes.append("头部段与身体段分别选色")
        scope = st.radio("修改范围", scopes, key=f"{prefix}_scope", horizontal=False)

        if is_one_piece and neck is None and quantity == 1:
            st.info("该一体件没有唯一且非末圈的「此处为颈部」标记，无法确认头部段与"
                    "身体段的分界，因此只提供整件选色；不会凭文字猜测边界。")

        if scope.startswith("仅所选实体"):
            labels = instance_labels(result, name)
            chosen = st.selectbox("选择实体", range(len(labels)),
                                  format_func=lambda i: labels[i], key=f"{prefix}_instance")
            st.caption("实体顺序与逐圈进度记录一致；结构实例顺序变化后请重新核对。")

        if scope == "头部段与身体段分别选色":
            rounds = [rd for rd in part.get("rounds") or [] if isinstance(rd, dict)]
            # 该选项只在能确定颈部标记时提供，因此这里的兜底索引不会被用到。
            neck_index = neck if neck is not None else 0
            head_current = (rounds[neck_index].get("color")
                            if neck_index < len(rounds) else None)
            body_current = rounds[-1].get("color") if rounds else None
            head_color = _color_input("头部段颜色", f"{prefix}_head", head_current)
            body_color = _color_input("身体段颜色", f"{prefix}_body", body_current)
            st.caption(f"第 {rounds[neck_index]['row']} 圈为颈部（含）；之后为身体段。"
                       "分段依据是图解说明中的颈部标记，请先核对。此操作会覆盖两段所有逐圈颜色和逐份配色。")
        elif scope != "仅所选实体（恢复部件配色）":
            if scope == "整个部件":
                current = part.get("color")
            else:
                overrides = part.get("instance_colors") or []
                chosen_index = int(st.session_state.get(f"{prefix}_instance", 0) or 0)
                current = overrides[chosen_index] if chosen_index < len(overrides) else None
            color = _color_input("毛线颜色", prefix, current)
            if scope == "整个部件":
                mode = st.radio(
                    "操作", [MODE_KEEP_STRIPES, MODE_UNIFORM],
                    format_func=lambda value: {
                        MODE_KEEP_STRIPES: "设置基础色并保留已有条纹",
                        MODE_UNIFORM: "统一换色（覆盖逐圈颜色）",
                    }[value], key=f"{prefix}_mode")
                st.caption("「保留已有条纹」只改未单独指定颜色的圈；已指定的圈与逐份配色"
                           "保持不变并在预览中列出。「统一换色」会覆盖全部圈和逐份配色。")

        st.caption("纯颜色修改通常保留已完成圈次；涉及接合等情况仍可能清除，具体以预览为准。"
                   "已钩出的旧颜色不会因为图解改色而改变。3D 预览按部件主色示意，"
                   "不显示逐圈条纹或各份实体的颜色。")
        preview_clicked = st.button("预览选色影响", key=f"{prefix}_preview")
        if not preview_clicked:
            return
        if scope == "头部段与身体段分别选色":
            _submit(result, slot, part_name=name,
                    head_color=head_color, body_color=body_color)
        elif scope == "仅所选实体（整份统一换色）":
            _submit(result, slot, part_name=name,
                    color=color, mode=MODE_UNIFORM, instance_index=int(chosen))
        elif scope == "仅所选实体（恢复部件配色）":
            _submit(result, slot, part_name=name,
                    mode=MODE_INHERIT, instance_index=int(chosen))
        else:
            _submit(result, slot, part_name=name,
                    color=color, mode=mode)
