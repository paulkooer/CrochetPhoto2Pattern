"""Form-based structure, stitch-table and measured-yarn editing."""

from __future__ import annotations

import re
import uuid
from copy import deepcopy

import streamlit as st

from app.models.crochet_params import refresh_derived
from app.models.geometry import normalize_structure
from app.models.materials import YarnSpec
from app.ui.edit_history import commit_edit, preview_edit, render_history
from app.ui.result_logic import rebuild_params, regenerate_with_structure


def edit_structure_part(
    result: dict,
    index: int,
    *,
    count: int,
    dimensions: dict,
    position: dict | None = None,
    instance_index: int = 0,
    attachments: list[dict] | None = None,
) -> dict:
    structure = deepcopy(normalize_structure(result["structure"]))
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


def edit_rounds(result: dict, index: int, rounds: list[dict]) -> dict:
    if len(rounds) != len(result["params"]["parts"][index]["rounds"]):
        raise ValueError("逐圈表格只支持修改现有圈；增删圈请使用高级 JSON")
    updated = deepcopy(result)
    updated["params"]["parts"][index]["rounds"] = rounds
    updated["params"] = rebuild_params(updated["params"], check_notes=False)
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
                rd["notes"] += "；" + "；".join(actions)
    from app.models.validator import require_valid_pattern

    require_valid_pattern(updated["params"])
    refresh_derived(updated["params"])
    return updated


def edit_yarn(result: dict, spec: dict | None) -> dict:
    updated = deepcopy(result)
    if spec is None:
        updated["params"].pop("yarn_spec", None)
    else:
        updated["params"]["yarn_spec"] = YarnSpec.model_validate(spec).model_dump()
    refresh_derived(updated["params"])
    return updated


def _apply(slot, result, candidate):
    commit_edit(slot, result, candidate)
    st.rerun()


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


def render_pattern_editor(result: dict, slot: str) -> None:
    from app.ui.result_renderer import md_safe

    rid = result.get("result_id") or slot
    render_history(slot, result)
    from app.ui.head_opening import render_head_opening
    from app.ui.leg_join import render_leg_join
    from app.ui.part_gauge import render_part_gauge
    from app.ui.skirt_editor import render_skirt_editor
    from app.ui.stitch_connections import render_stitch_connections

    render_head_opening(result, slot)
    render_part_gauge(result, slot)
    render_skirt_editor(result, slot)
    render_leg_join(f"{slot}_{rid}", result)
    render_stitch_connections(result, slot)
    with st.expander("🧩 可视化编辑部件", expanded=False):
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
            part = parts[index]
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
    with st.expander("🧵 逐圈表格编辑", expanded=False):
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
    with st.expander("🧶 按实际毛线与试片估算用量", expanded=False):
        spec = result["params"].get("yarn_spec") or {}
        from app.models.gauge import has_independent_gauge

        if has_independent_gauge(result["params"]):
            st.caption("线标适用于所有颜色；试片克重仅用于默认密度部件，独立密度部件按各自密度经验估算。"
                       "试片请用相同毛线与针法，称重不含线尾。")
        else:
            st.caption("以下线标与试片适用于所有颜色。试片请用相同毛线与针法，称重不含线尾。")
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
            waste = st.number_input(
                "预留线尾／损耗（%）",
                0.0,
                100.0,
                float(spec.get("waste_percent", 10)),
                key=f"edit_{rid}_waste",
            )
            submitted = st.form_submit_button("更新材料估算")
        if submitted:
            try:
                payload = {"ball_weight_g": weight, "ball_length_m": length, "waste_percent": waste}
                if measured:
                    payload.update(swatch_weight_g=swatch_weight, swatch_stitches=stitches, swatch_rows=rows)
                _apply(slot, result, edit_yarn(result, payload))
            except Exception as exc:
                st.error(f"材料估算失败：{md_safe(exc)}")
        if spec and st.button("恢复默认用量估算", key=f"edit_{rid}_yarnreset"):
            _apply(slot, result, edit_yarn(result, None))
