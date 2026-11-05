"""Form-based structure, stitch-table and measured-yarn editing."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict
from typing import Any

import streamlit as st

from app.models.crochet_params import refresh_derived
from app.models.gauge import gauge_from_result
from app.models.geometry import normalize_structure
from app.models.materials import YarnSpec
from app.schemas import ResultData, RoundData
from app.services.result_logic import rebuild_params, regenerate_with_size, regenerate_with_structure
from app.services.workspace import workspace
from app.ui.edit_history import commit_edit, preview_edit, render_history


def edit_structure_part(
    result: ResultData,
    index: int,
    *,
    count: int,
    dimensions: dict,
    position: dict | None = None,
    instance_index: int = 0,
    attachments: list[dict] | None = None,
) -> ResultData:
    # Form inputs may be invalid until regenerate_with_structure validates them.
    structure: dict[str, Any] = dict(deepcopy(normalize_structure(result["structure"])))
    part = structure["parts"][index]
    part.update(dimensions)
    part["count"] = count
    if structure.get("schema_version") == "2.0":
        if not 1 <= count <= 20:
            raise ValueError("部件数量必须为 1–20")
        instances = part["instances"][:count]
        while len(instances) < count:
            new = deepcopy(part["instances"][0])
            new["instance_id"] = f"{part['part_id']}_{uuid.uuid4().hex[:12]}"
            new.pop("mirror_of", None)
            instances.append(new)
        ids = {i["instance_id"] for i in instances}
        for instance in instances:
            if instance.get("mirror_of") not in ids:
                instance.pop("mirror_of", None)
        selected = instances[min(instance_index, count - 1)]
        if position is not None:
            selected["position"] = position
        if attachments is not None:
            selected["attachments"] = attachments
        part["instances"] = instances
    return regenerate_with_structure(result, structure)


def edit_rounds(result: ResultData, index: int, rounds: list[RoundData]) -> ResultData:
    if len(rounds) != len(result["params"]["parts"][index]["rounds"]):
        raise ValueError("逐圈表格只支持修改现有圈；增删圈请使用高级 JSON")
    updated = deepcopy(result)
    updated["params"]["parts"][index]["rounds"] = rounds
    updated["params"] = rebuild_params(updated["params"], check_notes=False, previous=result["params"])
    part = updated["params"]["parts"][index]
    original = result["params"]["parts"][index]["rounds"]
    from app.models.crochet_params import _change_note, _positioned_change_note

    for i, rd in enumerate(part["rounds"]):
        old = original[i]
        changed = any(rd.get(k, 0) != old.get(k, 0) for k in ("stitches", "increase", "decrease"))
        staggered = bool(i and rd["increase"] and part["rounds"][i - 1]["increase"]
                         and not rd["decrease"] and not part["rounds"][i - 1]["decrease"])
        was_staggered = bool(i and old.get("increase") and original[i - 1].get("increase")
                             and not old.get("decrease") and not original[i - 1].get("decrease"))
        if i:
            changed |= part["rounds"][i - 1]["stitches"] != original[i - 1]["stitches"]
        # Explicit user wording is retained; unchanged generated instructions must
        # not describe obsolete counts after a numeric edit.
        if (changed or staggered != was_staggered) and rounds[i].get("notes") == old.get("notes"):
            # Only replace a recognized numeric instruction. Semicolon-separated
            # finishing/assembly actions must survive; unfamiliar prose needs an
            # explicit user edit instead of being silently discarded.
            old_note = old.get("notes") or ""
            prefix, _, suffix = old_note.partition("；")
            old_before = original[i - 1]["stitches"] if i else None
            recognized = not prefix or (
                old_before is not None and prefix in {
                    _change_note(old_before, old["stitches"]),
                    _positioned_change_note(old_before, old["stitches"], staggered=was_staggered),
                }
            ) or (i == 0 and part.get("magic_ring") and re.fullmatch(
                r"魔法环起\s*\d+\s*针(?:（X×\d+）)?", prefix
            ))
            if not recognized:
                if changed:
                    raise ValueError(f"第 {rd['row']} 圈含自定义或特殊工艺说明，请同时修改说明后再应用")
                continue  # An unchanged custom instruction is not a generated hint.
            before = part["rounds"][i - 1]["stitches"] if i else None
            if before is None:
                method = "魔法环" if part.get("magic_ring") else "按原起针方式"
                rd["notes"] = f"{method}起 {rd['stitches']} 针"
            elif rd["increase"] and rd["decrease"]:
                plain = before - rd["increase"] - 2 * rd["decrease"]
                if plain >= 0:
                    rd["notes"] = (
                        f"{plain} 个短针、{rd['increase']} 个加针、{rd['decrease']} 个减针；"
                        f"共 {rd['stitches']} 针，加减针位置需人工安排"
                    )
                else:
                    rd["notes"] = f"本圈共 {rd['stitches']} 针；含复合加减针，请补充具体针法和位置"
            else:
                rd["notes"] = _positioned_change_note(before, rd["stitches"], staggered=staggered)
            # Staggering is generated from the new transitions; it is not a
            # finishing action and may no longer apply after a numeric edit.
            actions = [s for s in suffix.split("；") if s and s != "加针位置与上一圈错开半组"]
            if actions:
                rd["notes"] = f"{rd['notes']}；" + "；".join(actions)
    from app.models.validator import require_valid_pattern

    require_valid_pattern(updated["params"])
    refresh_derived(updated["params"])
    return updated


def edit_yarn(result: ResultData, spec: dict | None) -> ResultData:
    updated = deepcopy(result)
    if spec is None:
        updated["params"].pop("yarn_spec", None)
    else:
        validated = YarnSpec.model_validate(spec)
        payload = validated.model_dump()
        # An explicit recording action knows the swatch's origin; imports do not.
        if validated.swatch_weight_g is not None and validated.swatch_gauge is None:
            payload["swatch_gauge"] = asdict(gauge_from_result(result))
        updated["params"]["yarn_spec"] = payload
    refresh_derived(updated["params"])
    return updated


def _apply(slot, result, candidate):
    commit_edit(slot, result, candidate)
    st.rerun()


def apply_edit_with_notice(slot: str, result: ResultData, updated: ResultData, success: str) -> None:
    """Commit ``updated`` and show ``success`` on the next run.

    A no-op commit keeps the current result and its own "unchanged" notice, so the
    success message only appears when the pattern actually changed. The message is
    stored in the new result's workspace: ``st.success`` right before ``st.rerun``
    would be discarded with the run.
    """
    installed = commit_edit(slot, result, updated)
    if installed is not result:
        workspace(installed, slot, st.session_state)["success"] = success
    st.rerun()


def _render_quick_size(result: ResultData, slot: str) -> None:
    """Head diameter / height → structure and pattern recomputed locally.

    生成时的 style/gauge/色带随 result 透传，重生成与首次行为一致；纯本地计算，
    无 API 成本，比手改 JSON 快且不会改坏结构。
    """
    from app.ui.result_renderer import md_safe

    rid = result.get("result_id") or slot
    analysis = result["analysis"]
    structure = result["structure"]
    with st.expander("快速调整尺寸（不重新识别照片）", expanded=False):
        st.caption("保留已编辑的部件、数量、位姿、连接与颜色；头径使用指定值，其他尺寸按比例缩放。")
        current_head = next((p.get("diameter_cm") for p in structure.get("parts", [])
                             if p.get("name") == "头部" and p.get("diameter_cm")), None)
        current_head = float(current_head or analysis.get("head_diameter_cm") or 9.0)
        current_height = float(analysis.get("height_cm") or 18.0)
        if current_head != float(analysis.get("head_diameter_cm") or current_head):
            st.caption("当前结构头径与原分析不同；提交会同步头径，可能重算依赖尺寸的部件，建议先预览。")
        head_col, height_col = st.columns(2)
        with head_col:
            new_head = st.slider(
                "头部直径 (cm)", min(4.0, current_head), max(20.0, current_head),
                current_head, 0.5,
                key=f"sz_head_{rid}")
        with height_col:
            new_height = st.slider(
                "整体高度 (cm)", min(10.0, current_height), max(60.0, current_height),
                current_height, 0.5,
                key=f"sz_height_{rid}")
        with st.container(horizontal=True):
            preview_size = st.button("预览尺寸修改影响", key=f"edit_{rid}_size_preview")
            apply_size = st.button("按新尺寸重新生成", key=f"sz_go_{rid}")
        if apply_size or preview_size:
            try:
                # 业务逻辑在 result_logic（纯函数，可离线单测）
                candidate = regenerate_with_size(result, new_head, new_height)
                if preview_size:
                    preview_edit(slot, result, candidate)
                else:
                    apply_edit_with_notice(slot, result, candidate,
                                           "✅ 已按新尺寸重新生成图解（配色与塑形选项保持不变）！")
            except Exception as e:
                st.error(f"尺寸重生成失败: {md_safe(e)}")


def _render_stitch_calculator(key: str) -> None:
    from app.models.stitch_notation import NotationError, parse_stitch_notation

    expression = st.text_input(
        "针法计算器（可选）", placeholder="例如：(2X,V)×6", key=key,
        help="支持 BLO((2X,V)×6)、4sc-FLO 等明确写法；计算结果不会自动应用到图解。",
    )
    if not expression.strip():
        return
    try:
        counts = parse_stitch_notation(expression)
    except NotationError as exc:
        st.error(str(exc))
        return
    if counts is None:
        st.info("请输入完整操作式；此写法含尚未支持的针法或文字说明，请人工核对。")
        return
    st.info(
        f"消耗上一圈 {counts.consumed} 针 → 本圈 {counts.produced} 针；"
        f"加 {counts.increase} 针，减 {counts.decrease} 针。"
    )


def render_pattern_editor(result: ResultData, slot: str) -> None:
    from app.ui.result_renderer import md_safe

    rid = result.get("result_id") or slot
    render_history(slot, result)
    # Common corrections in order of use; raw JSON stays in the advanced panel below.
    st.caption("常用修正按使用频率排列：先调整尺寸，再修改部件、逐圈针法、材料与毛线颜色；"
               "之后是留口、独立密度、接裙、逐针连接与并腿等专项工具。"
               "直接编辑 JSON 收在下方「高级编辑」面板。修改前可先预览影响，应用后可撤销。")
    _render_quick_size(result, slot)
    from app.ui.color_editor import render_color_editor
    from app.ui.head_opening import render_head_opening
    from app.ui.leg_join import render_leg_join
    from app.ui.part_gauge import render_part_gauge
    from app.ui.skirt_editor import render_skirt_editor
    from app.ui.stitch_connections import render_stitch_connections

    with st.expander("可视化编辑部件", expanded=False):
        st.caption("尺寸、数量或连接变化会重算受影响部件；可确认构造未变的其他部件保留手改针法、配色和备注。"
                   "建议先预览影响；无法确认保留范围时按整份图解重算，可撤销恢复。")
        parts = result["structure"].get("parts", [])
        if parts:
            index = st.selectbox(
                "选择结构部件",
                range(len(parts)),
                format_func=lambda i: parts[i]["name"],
                key=f"edit_{rid}_part",
            )
            # Dynamic form keys and values are validated when the edit is applied.
            part: Mapping[str, Any] = parts[index]
            prefix = f"edit_{rid}_part{index}"
            inst_index = 0
            if result["structure"].get("schema_version") == "2.0" and part.get("instances"):
                inst_index = st.selectbox(
                    "选择实体（位置与连接单独设置）",
                    range(len(part["instances"])),
                    format_func=lambda i: f"第 {i + 1} 份",
                    key=f"{prefix}_instance",
                )
            with st.form(f"{prefix}_form_{inst_index}"):
                count = st.number_input("数量", 1, 20, int(part.get("count", 1)), key=f"{prefix}_count")
                dims = {}
                for field, label in (("diameter_cm", "直径"), ("height_cm", "高度"), ("length_cm", "长度")):
                    if part.get(field) is not None:
                        dims[field] = st.number_input(
                            f"{label}（cm）",
                            min(0.1, float(part[field])),
                            200.0,
                            float(part[field]),
                            0.1,
                            key=f"{prefix}_{field}",
                        )
                position: dict | None = None
                attachments: list[dict] | None = None
                if result["structure"].get("schema_version") == "2.0" and part.get("instances"):
                    instance = part["instances"][inst_index]
                    ip = f"{prefix}_i{inst_index}"
                    position = {}
                    for axis, label, lo in (("x", "左右", -1.0), ("y", "上下", 0.0), ("z", "前后", -1.0)):
                        position[axis] = st.slider(
                            f"位置 · {label}",
                            lo,
                            1.0,
                            float(instance["position"][axis]),
                            0.01,
                            key=f"{ip}_{axis}",
                        )
                    st.caption("位置为归一化示意坐标；前后深度未经照片测量，不改变针数。")
                    current = instance.get("attachments", [])
                    replace = st.checkbox("替换此实体的连接", key=f"{ip}_replace")
                    targets = [None] + [p["part_id"] for p in parts if p["part_id"] != part["part_id"]]
                    labels = {p["part_id"]: p["name"] for p in parts}
                    target = st.selectbox(
                        "连接到",
                        targets,
                        format_func=lambda v: labels.get(v, "无连接"),
                        index=targets.index(current[0]["target_part_id"])
                        if current and current[0]["target_part_id"] in targets
                        else 0,
                        key=f"{ip}_target",
                    )
                    anchor = st.text_input(
                        "对方连接点",
                        value=current[0]["target_anchor"] if current else "top",
                        key=f"{ip}_anchor",
                    )
                    self_anchor = st.text_input(
                        "本部件连接点",
                        value=current[0]["self_anchor"] if current else "bottom",
                        key=f"{ip}_self",
                    )
                    methods = ["sewn", "worn", "crocheted_or_sewn"]
                    method = st.selectbox(
                        "连接方式",
                        methods,
                        format_func=lambda v: {
                            "sewn": "缝合",
                            "worn": "穿戴",
                            "crocheted_or_sewn": "钩接或缝合",
                        }[v],
                        index=methods.index(current[0]["method"]) if current else 0,
                        key=f"{ip}_method",
                    )
                    if replace:
                        attachments = (
                            [
                                {
                                    "target_part_id": target,
                                    "target_anchor": anchor,
                                    "self_anchor": self_anchor,
                                    "method": method,
                                }
                            ]
                            if target
                            else []
                        )
                previewed = st.form_submit_button("预览部件修改影响")
                submitted = st.form_submit_button("应用部件修改")
            if submitted or previewed:
                try:
                    candidate = edit_structure_part(
                        result,
                        index,
                        count=count,
                        dimensions=dims,
                        instance_index=inst_index,
                        position=position,
                        attachments=attachments,
                    )
                    if previewed:
                        preview_edit(slot, result, candidate)
                    else:
                        _apply(slot, result, candidate)
                except Exception as exc:
                    st.error(f"部件修改失败：{md_safe(exc)}")
    with st.expander("逐圈表格编辑", expanded=False):
        pattern_parts = result["params"].get("parts", [])
        if pattern_parts:
            index = st.selectbox(
                "选择逐圈部件",
                range(len(pattern_parts)),
                format_func=lambda i: pattern_parts[i]["name"],
                key=f"edit_{rid}_roundpart",
            )
            rounds = pattern_parts[index]["rounds"]
            edited = st.data_editor(
                rounds,
                disabled=["row", "allow_wide_jump"],
                num_rows="fixed",
                key=f"edit_{rid}_rounds{index}",
                hide_index=True,
                column_config={
                    "row": "圈号",
                    "stitches": "针数",
                    "increase": "加针数",
                    "decrease": "减针数",
                    "color": "毛线颜色",
                    "notes": "说明",
                    "allow_wide_jump": None,
                },
            )
            st.caption("skin 和 body 分别表示待选肤色和主体色；可填写实际毛线色名。"
                       "圈次颜色留空时沿用部件颜色。")
            st.caption(
                "针数、加针和减针须满足相邻圈关系；不通过自检的修改不会覆盖当前图解。"
                "更改针数时，未手改的原针法说明会自动更新；自定义说明请同步核对。"
                "收口与留线说明会保留；无法识别的特殊工艺需同时修改说明。"
            )
            st.caption(
                "独立操作式会按整圈核对，例如 (2X,V)×6 或 (2 sc,inc)×6：消耗 18 针，"
                "产出 24 针，加 6 针。支持 X/V/A/W/M、美式短针缩写及重复组。"
                "FLO=只挑前半针，BLO=只挑后半针；可写 BLO((2X,V)×6) 或 4sc-FLO；"
                "跨层挑针、锁针连接等特殊工艺仍需人工核对。"
            )
            _render_stitch_calculator(f"edit_{rid}_notation{index}")
            previewed_rounds = st.button("预览逐圈修改影响", key=f"edit_{rid}_roundpreview")
            apply_rounds = st.button("应用逐圈修改", key=f"edit_{rid}_roundapply")
            if apply_rounds or previewed_rounds:
                try:
                    candidate = edit_rounds(result, index, edited)
                    if previewed_rounds:
                        preview_edit(slot, result, candidate)
                    else:
                        _apply(slot, result, candidate)
                except Exception as exc:
                    st.error(f"逐圈修改失败：{md_safe(exc)}")
    with st.expander("按实际毛线与试片估算用量", expanded=False):
        spec = result["params"].get("yarn_spec") or {}
        from app.models.gauge import Gauge

        origin = Gauge(**spec["swatch_gauge"]) if spec.get("swatch_gauge") else gauge_from_result(result)
        legacy = bool(spec.get("swatch_weight_g") and not spec.get("swatch_gauge"))
        st.caption("线标适用于所有颜色；实测克重只用于与试片密度相同的部件，其余密度使用经验估算。"
                   "试片请用相同毛线与针法，称重不含线尾；记录下方这块试片的实际密度。")
        if legacy:
            st.warning("旧试片未记录测量密度，称重数据已保留；请核对密度并确认后再使用实测用量。")
        with st.form(f"edit_{rid}_yarnform"):
            weight = st.number_input(
                "每团克重（g）",
                min(1.0, float(spec.get("ball_weight_g", 50))),
                2000.0,
                float(spec.get("ball_weight_g", 50)),
                key=f"edit_{rid}_weight",
            )
            length = st.number_input(
                "每团长度（m）",
                min(1.0, float(spec.get("ball_length_m", 125))),
                10000.0,
                float(spec.get("ball_length_m", 125)),
                key=f"edit_{rid}_length",
            )
            measured = st.checkbox(
                "使用实测短针试片克重", value=bool(spec.get("swatch_weight_g")), key=f"edit_{rid}_measured"
            )
            swatch_weight = st.number_input(
                "试片克重（g）",
                min(0.01, float(spec.get("swatch_weight_g") or 5)),
                2000.0,
                float(spec.get("swatch_weight_g") or 5),
                key=f"edit_{rid}_swatchweight",
            )
            stitches = st.number_input(
                "试片每行针数", 1, 1000, int(spec.get("swatch_stitches") or 20), key=f"edit_{rid}_swatchst"
            )
            rows = st.number_input(
                "试片行数", 1, 1000, int(spec.get("swatch_rows") or 20), key=f"edit_{rid}_swatchrows"
            )
            swatch_st = st.number_input("试片 10cm 针数", 6.0, 40.0,
                origin.stitches_per_10cm, .5, key=f"edit_{rid}_swatchgauge_stitches")
            swatch_rw = st.number_input("试片 10cm 行数", 8.0, 50.0,
                origin.rows_per_10cm, .5, key=f"edit_{rid}_swatchgauge_rows")
            confirmed = (st.checkbox("已核对旧试片的测量密度", key=f"edit_{rid}_swatch_confirm")
                         if legacy else True)
            waste = st.number_input(
                "预留线尾／损耗（%）",
                0.0,
                100.0,
                float(spec.get("waste_percent", 10)),
                key=f"edit_{rid}_waste",
            )
            preview_column, apply_column = st.columns(2)
            previewed = preview_column.form_submit_button("预览材料估算修改")
            submitted = apply_column.form_submit_button("更新材料估算")
        if submitted or previewed:
            try:
                payload: dict = {"ball_weight_g": weight, "ball_length_m": length, "waste_percent": waste}
                if measured:
                    if not confirmed:
                        raise ValueError("请先核对并确认旧试片的测量密度；原称重数据和图解已保留")
                    payload.update(swatch_weight_g=swatch_weight, swatch_stitches=stitches, swatch_rows=rows)
                    payload["swatch_gauge"] = asdict(Gauge(swatch_st, swatch_rw))
                candidate = edit_yarn(result, payload)
                if previewed:
                    preview_edit(slot, result, candidate)
                else:
                    _apply(slot, result, candidate)
            except Exception as exc:
                st.error(f"材料估算失败：{md_safe(exc)}")
        if spec and st.button("恢复默认用量估算", key=f"edit_{rid}_yarnreset"):
            _apply(slot, result, edit_yarn(result, None))
    # Special-purpose tools after the everyday editors: neck opening, independent
    # swatches, waist join, per-stitch connections and the leg-bridge calculator.
    render_color_editor(result, slot)
    render_head_opening(result, slot)
    render_part_gauge(result, slot)
    render_skirt_editor(result, slot)
    render_stitch_connections(result, slot)
    render_leg_join(f"{slot}_{rid}", result)
