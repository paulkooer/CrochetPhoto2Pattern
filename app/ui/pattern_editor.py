"""Form-based structure, stitch-table and measured-yarn editing."""

from __future__ import annotations

import uuid
from copy import deepcopy

import streamlit as st

from app.models.crochet_params import refresh_derived
from app.models.geometry import normalize_structure
from app.models.materials import YarnSpec
from app.ui.edit_history import commit_edit, render_history
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
    updated["params"] = rebuild_params(updated["params"])
    part = updated["params"]["parts"][index]
    original = result["params"]["parts"][index]["rounds"]
    from app.models.crochet_params import _change_note

    for i, rd in enumerate(part["rounds"]):
        old = original[i]
        changed = any(rd.get(k, 0) != old.get(k, 0) for k in ("stitches", "increase", "decrease"))
        if i:
            changed |= part["rounds"][i - 1]["stitches"] != original[i - 1]["stitches"]
        # Explicit user wording is retained; unchanged generated instructions must
        # not describe obsolete counts after a numeric edit.
        if changed and rd.get("notes") == old.get("notes"):
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
                rd["notes"] = _change_note(before, rd["stitches"])
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


def render_pattern_editor(result: dict, slot: str) -> None:
    from app.ui.result_renderer import md_safe

    rid = result.get("result_id") or slot
    render_history(slot, result)
    with st.expander("🧩 可视化编辑部件", expanded=False):
        st.caption("调整尺寸与数量会重新计算逐圈针法；之前手改的逐圈针数会被替换，可撤销恢复。")
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
            if part.get("instances"):
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
                if part.get("instances"):
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
                submitted = st.form_submit_button("应用部件修改")
            if submitted:
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
            )
            if st.button("应用逐圈修改", key=f"edit_{rid}_roundapply"):
                try:
                    _apply(slot, result, edit_rounds(result, index, edited))
                except Exception as exc:
                    st.error(f"逐圈修改失败：{md_safe(exc)}")
    with st.expander("🧶 按实际毛线与试片估算用量", expanded=False):
        spec = result["params"].get("yarn_spec") or {}
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
