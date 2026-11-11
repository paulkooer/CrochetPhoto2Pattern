"""部件级、实体级与一体件分段的毛线选色（V1）。

纯函数层：输入 result dict 与用户选择，输出新的 result dict，不依赖 Streamlit，
便于离线单测。配色规格、数据流、兼容方案与验收清单见
``docs/part-color-selection.md``。

三条不变量（与规格 §3/§4 对应）：

1. 人工选色只写颜色、来源及实体/分段关联字段；照片证据（``color_bands``、
   ``vision_meta.color_observation``、``analysis.recommended_colors``）保持原值。
2. ``MODE_KEEP_STRIPES`` 只改未单独指定的圈；已有圈色来源不明时一律保留。
   ``MODE_UNIFORM`` 由用户明确选择覆盖全部圈与逐份覆盖。
3. 一体件分段边界只取生成器写下的 ``ONE_PIECE_NECK_MARKER``；标记缺失或不唯一时
   拒绝操作，不凭文本猜测边界。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, Literal, cast

from app.models.color_design import refresh_color_instructions
from app.models.colors import normalize_hex_color, resolve_display_color
from app.models.gauge import gauge_from_result
from app.models.materials import yarn_requirements
from app.models.parts import (
    _ONE_PIECE_NAME,
    ONE_PIECE_NECK_MARKER,
    _part_instance_colors,
    _part_quantity,
)
from app.schemas import PartData, ResultData

# 「设置基础色并保留已有条纹」/「统一换色」——两种操作必须由用户明确选择。
MODE_KEEP_STRIPES = "keep_stripes"
MODE_UNIFORM = "uniform"
MODE_INHERIT = "inherit"
ColorMode = Literal["keep_stripes", "uniform", "inherit"]
_MODES = (MODE_KEEP_STRIPES, MODE_UNIFORM, MODE_INHERIT)

MAX_COLOR_NAME = 40  # 与 ColorCoverage.color 同一上限


def _checked_color(color: object) -> str:
    if not isinstance(color, str):
        raise ValueError("请选择颜色名称")
    name = color.strip()
    if not name:
        raise ValueError("颜色名称不能为空")
    if len(name) > MAX_COLOR_NAME:
        raise ValueError(f"颜色名称不能超过 {MAX_COLOR_NAME} 个字符")
    if name in ("skin", "body"):
        raise ValueError("skin 和 body 是待选占位值，请填写实际毛线颜色名称")
    return name


def _checked_mode(mode: object) -> str:
    if mode not in _MODES:
        raise ValueError("请选择操作：设置基础色并保留已有条纹，或统一换色")
    return str(mode)


def parts_of(params: Mapping[str, Any]) -> list[dict[str, Any]]:
    parts = params.get("parts")
    return list(parts) if isinstance(parts, list) else []


def part_index(params: Mapping[str, Any], name: str) -> int:
    for index, part in enumerate(parts_of(params)):
        if isinstance(part, Mapping) and part.get("name") == name:
            return index
    raise ValueError(f"图解中没有部件「{name}」")


def one_piece_neck_index(part: Mapping[str, Any]) -> int | None:
    """一体件的颈部圈序号，来自生成器写下的唯一标记；无法确定时返回 None。

    边界不可靠时返回 None（而不是猜一个位置）：``MODE_*`` 分段选色随后拒绝操作。
    """
    if part.get("name") != _ONE_PIECE_NAME:
        return None
    rounds = part.get("rounds") or []
    marks = [index for index, rd in enumerate(rounds)
             if isinstance(rd, Mapping) and ONE_PIECE_NECK_MARKER in str(rd.get("notes") or "")]
    if len(marks) != 1:
        return None
    neck = marks[0]
    # 颈部必须是头部段的末端：后面还有身体段才谈得上分段选色。
    return neck if neck < len(rounds) - 1 else None


def instance_labels(result: ResultData, name: str) -> list[str]:
    """该部件每份实体的界面标签，顺序与进度记录一致（结构图 ID 或份序数）。"""
    from app.services.color_identity import color_copy_ids

    part = parts_of(result.get("params") or {})[part_index(result["params"], name)]
    identities = color_copy_ids(result, part)
    return [f"第 {index + 1} 份（{identity}）" for index, identity in enumerate(identities)]


def plan_round_colors(part: Mapping[str, Any], color: str, mode: str) -> list[tuple[int, str | None, str]]:
    """``(圈号, 旧色, 新色)``：每个实际发生变化的圈，按图解圈序排列。

    ``MODE_KEEP_STRIPES`` 保留所有已指定颜色的圈，因旧数据无法可靠区分
    自动颜色和人工修改（即使颜色恰好等于原基础色）。
    """
    base = part.get("color")
    changes: list[tuple[int, str | None, str]] = []
    for rd in part.get("rounds") or []:
        if not isinstance(rd, Mapping):
            continue
        explicit = rd.get("color")
        old = explicit or base
        if mode == MODE_KEEP_STRIPES and explicit:
            continue
        if old != color:
            changes.append((int(rd.get("row", 0)), old, color))
    return changes


def kept_rounds(part: Mapping[str, Any], color: str) -> list[tuple[int, str]]:
    """``MODE_KEEP_STRIPES`` 下已指定颜色、不会被覆盖的圈。"""
    kept = []
    for rd in part.get("rounds") or []:
        if not isinstance(rd, Mapping):
            continue
        old = rd.get("color")
        if old and old != color:
            kept.append((int(rd.get("row", 0)), old))
    return kept


def _recolored_part(part: Mapping[str, Any], color: str, mode: str,
                    instance_index: int | None) -> PartData:
    updated = deepcopy(dict(part))
    rounds = updated.get("rounds") or []
    if instance_index is None:
        for rd in rounds:
            if not isinstance(rd, dict):
                continue
            old = rd.get("color")
            if mode == MODE_KEEP_STRIPES and old:
                continue
            if mode == MODE_UNIFORM:
                rd["color"] = color
        updated["color"] = color
        # 用户显式选择了部件基础色：记录来源，绝不伪装成照片识别结果。
        updated["color_origin"] = "manual"
        if mode == MODE_UNIFORM:
            updated.pop("instance_colors", None)
            updated.pop("instance_color_ids", None)
            updated.pop("color_section_mode", None)
        return cast("PartData", updated)
    quantity = _part_quantity(part)
    if type(instance_index) is not int or not 0 <= instance_index < quantity:
        raise ValueError(f"实体序号超出该部件的数量（{quantity}）；请重新选择")
    raw = part.get("instance_colors")
    if isinstance(raw, list) and raw and len(raw) != quantity:
        raise ValueError("逐份颜色数量与部件数量不一致，请先修正该部件的图解数据")
    overrides: list[str | None] = list(raw) if isinstance(raw, list) and raw else [None] * quantity
    overrides = (overrides + [None] * quantity)[:quantity]
    overrides[instance_index] = None if mode == MODE_INHERIT else color
    updated["instance_colors"] = overrides
    return cast("PartData", updated)


def _store_display_colors(params: dict[str, Any], chosen: list[str],
                          provided: Mapping[str, str] | None) -> None:
    """把本次选中的自定义名称登记到 ``params.display_colors``。

    色表名和十六进制本身已能解析，不写入这张表。没提供显示色时保留原名，
    3D 用中性灰而不是部件旧色。同一名称给出两个不同显示色时拒绝。
    """
    if not provided:
        return
    current = params.get("display_colors")
    merged = dict(current) if isinstance(current, dict) else {}
    for name in chosen:
        if resolve_display_color(name) is not None or name not in provided:
            continue
        raw = provided[name]
        normalized = normalize_hex_color(raw)
        if normalized is None:
            raise ValueError(
                f"自定义颜色「{name}」的显示色必须是 #RGB 或 #RRGGBB。"
                "显示色只用于界面和导出，不是毛线品牌色号")
        merged[name] = normalized
    if merged:
        params["display_colors"] = merged


def _recolored_result(result: ResultData, *, part_name: str, color: str, mode: str,
                      instance_index: int | None, head_color: str | None = None,
                      body_color: str | None = None,
                      display_colors: Mapping[str, str] | None = None) -> ResultData:
    from app.services.color_identity import (
        align_copy_colors,
        color_copy_ids,
        has_stable_copy_ids,
        require_aligned_copy_colors,
    )
    from app.services.result_logic import rebuild_params

    require_aligned_copy_colors(result)
    candidate = deepcopy(result)
    params = candidate["params"]
    index = part_index(params, part_name)
    part = align_copy_colors(params["parts"][index], color_copy_ids(candidate, params["parts"][index]))
    if instance_index is not None and not has_stable_copy_ids(candidate, part):
        raise ValueError("该部件缺少稳定的实体身份，暂不支持单份选色；请使用整个部件选色")
    if head_color is not None and body_color is not None:
        updated = _split_one_piece_part(part, head_color, body_color)
    else:
        updated = _recolored_part(part, color, mode, instance_index)
        if instance_index is not None:
            updated["instance_color_ids"] = color_copy_ids(candidate, part)
    refresh_color_instructions(updated, previous=part)
    params["parts"][index] = updated
    chosen = [head_color, body_color] if head_color is not None and body_color is not None else (
        [] if mode == MODE_INHERIT else [color])
    _store_display_colors(cast("dict[str, Any]", params),
                          [name for name in chosen if name], display_colors)
    candidate["params"] = rebuild_params(params, structure=candidate["structure"])
    return candidate


def _require_neck(part: Mapping[str, Any]) -> int:
    """已记录且唯一的颈部圈序号；无法确定时拒绝操作，不凭文字猜测边界。"""
    neck = one_piece_neck_index(part)
    if neck is None:
        raise ValueError(
            f"无法确认一体件「{_ONE_PIECE_NAME}」的颈部位置（需要唯一且非末圈的"
            "「此处为颈部」标记），因此不能按头部段/身体段分别选色；"
            "请改用整件选色，或先修正该部件的圈次说明")
    return neck


def _split_one_piece_part(part: Mapping[str, Any], head_color: str,
                          body_color: str) -> PartData:
    from app.models.onepiece import ONE_PIECE_MONO_NOTE

    neck = _require_neck(part)
    updated = deepcopy(dict(part))
    rounds = updated.get("rounds") or []
    for index, rd in enumerate(rounds):
        if isinstance(rd, dict):
            rd["color"] = head_color if index <= neck else body_color
    if isinstance(updated.get("notes"), str):
        updated["notes"] = updated["notes"].replace(ONE_PIECE_MONO_NOTE, "") or None
    updated["color"] = head_color
    updated["color_origin"] = "manual"
    updated["color_section_mode"] = "head_body"
    updated.pop("instance_colors", None)
    updated.pop("instance_color_ids", None)
    return cast("PartData", updated)


def _materials_delta(result: ResultData, candidate: ResultData) -> list[dict[str, Any]]:
    """逐色用量前后对比（克/米/团）；无线标时团数为 None。"""
    def rows(source: ResultData) -> dict[str, dict[str, Any]]:
        params = source["params"]
        rows, _summary = yarn_requirements(parts_of(params), gauge_from_result(source),
                                           params.get("yarn_spec"))
        return {row["color"]: row for row in rows}

    before, after = rows(result), rows(candidate)
    delta = []
    for color in dict.fromkeys([*before, *after]):
        old, new = before.get(color), after.get(color)
        old_balls = old.get("balls") if old is not None else 0
        new_balls = new.get("balls") if new is not None else 0
        balls = (f"{old_balls} → {new_balls}"
                 if old_balls is not None and new_balls is not None else "未提供线标")
        delta.append({"颜色": color,
                      "修改前": "-" if old is None else f"{old['grams']:.1f}g / {old['meters']:.1f}m",
                      "修改后": "-" if new is None else f"{new['grams']:.1f}g / {new['meters']:.1f}m",
                      "团数": balls})
    return delta


def _split_preview(result: ResultData, *, part_name: str, head_color: str,
                   body_color: str) -> dict[str, Any]:
    part = parts_of(result["params"])[part_index(result["params"], part_name)]
    # 与应用路径共用同一判定：边界不可靠时给出同一条错误，预览不会提出一个
    # 应用必然拒绝的方案。
    neck = _require_neck(part)
    rounds = [rd for rd in part.get("rounds") or [] if isinstance(rd, Mapping)]
    affected = [{"圈号": int(rd.get("row", 0)), "旧色": rd.get("color"),
                 "新色": head_color if index <= neck else body_color}
                for index, rd in enumerate(rounds)
                if rd.get("color") != (head_color if index <= neck else body_color)]
    return {
        "part": part_name, "scope": "sections", "mode": MODE_UNIFORM,
        "color": None, "head_color": head_color, "body_color": body_color,
        "instance_index": None,
        "neck_row": int(rounds[neck].get("row", neck + 1)),
        "affected": affected,
        "kept": [],
        "changed": bool(affected),
    }


def color_change_preview(result: ResultData, *, part_name: str, color: str | None = None,
                         mode: str = MODE_KEEP_STRIPES, instance_index: int | None = None,
                         head_color: str | None = None, body_color: str | None = None,
                         display_colors: Mapping[str, str] | None = None,
                         progress: Mapping[str, bool] | None = None,
                         slot: str = "") -> dict[str, Any]:
    """修改前的预览载荷；绝不改动 ``result``。

    返回部件/实体/受影响圈次（圈号、旧色、新色）/保留的圈/逐色材料用量前后对比；
    传入 ``progress`` 时另附进度影响（沿用 ``progress_state.progress_impact``）。
    """
    candidate_result = apply_color_change(
        result, part_name=part_name, color=color, mode=mode,
        instance_index=instance_index, head_color=head_color, body_color=body_color,
        display_colors=display_colors)
    if head_color is not None and body_color is not None:
        preview = _split_preview(result, part_name=part_name,
                                 head_color=_checked_color(head_color),
                                 body_color=_checked_color(body_color))
    else:
        checked_mode = _checked_mode(mode)
        checked_color = "" if checked_mode == MODE_INHERIT else _checked_color(color)
        part = parts_of(result["params"])[part_index(result["params"], part_name)]
        if instance_index is not None:
            quantity = _part_quantity(part)
            if type(instance_index) is not int or not 0 <= instance_index < quantity:
                raise ValueError(f"实体序号超出该部件的数量（{quantity}）；请重新选择")
        preview = {
            "part": part_name,
            "scope": "instance" if instance_index is not None else "part",
            "mode": checked_mode,
            "color": checked_color,
            "head_color": None, "body_color": None,
            "instance_index": instance_index,
            "affected": [], "kept": [], "changed": False,
        }
    from app.services.color_identity import align_copy_colors, color_copy_ids

    original_part = parts_of(result["params"])[part_index(result["params"], part_name)]
    original = align_copy_colors(original_part, color_copy_ids(result, original_part))
    proposed = parts_of(candidate_result["params"])[part_index(candidate_result["params"], part_name)]
    before_overrides = _part_instance_colors(original)
    after_overrides = _part_instance_colors(proposed)
    quantity = _part_quantity(original)
    selected = range(quantity) if instance_index is None else (instance_index,)
    affected: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for copy in selected:
        before_override = before_overrides[copy] if before_overrides else None
        after_override = after_overrides[copy] if after_overrides else None
        for old_row, new_row in zip(original["rounds"], proposed["rounds"], strict=True):
            old_color = before_override or old_row.get("color") or original.get("color")
            new_color = after_override or new_row.get("color") or proposed.get("color")
            identity = {"实体": copy + 1} if quantity > 1 else {}
            if old_color != new_color:
                affected.append({**identity, "圈号": old_row["row"], "旧色": old_color, "新色": new_color})
            elif (preview["scope"] == "part" and preview["mode"] == MODE_KEEP_STRIPES
                  and (before_override or old_row.get("color"))):
                kept.append({**identity, "圈号": old_row["row"], "颜色": old_color})
    preview["affected"] = affected
    preview["kept"] = kept
    before_value = result["params"].get("display_colors")
    after_value = candidate_result["params"].get("display_colors")
    before_displays = before_value if isinstance(before_value, dict) else {}
    after_displays = after_value if isinstance(after_value, dict) else {}
    display_changes = []
    for name, raw in after_displays.items():
        old = normalize_hex_color(before_displays.get(name))
        new = normalize_hex_color(raw)
        if old != new:
            display_changes.append({"颜色": name, "旧显示色": old or "未设置", "新显示色": new})
    preview["display_changes"] = display_changes
    preview["changed"] = original != proposed or before_displays != after_displays
    preview["materials"] = _materials_delta(result, candidate_result)
    if progress is not None:
        from app.services.progress_state import progress_impact

        preview["progress"] = progress_impact(result, candidate_result, slot, dict(progress))
    return preview


def apply_color_change(result: ResultData, *, part_name: str, color: str | None = None,
                       mode: str = MODE_KEEP_STRIPES, instance_index: int | None = None,
                       head_color: str | None = None, body_color: str | None = None,
                       display_colors: Mapping[str, str] | None = None) -> ResultData:
    """按用户选择返回新的 result；``result`` 本身不被修改。

    ``color``/``mode`` 用于整件或单份选色；同时给出 ``head_color`` 与
    ``body_color`` 时对一体件按已记录的颈部边界分段选色。
    """
    if head_color is not None and body_color is not None:
        return _recolored_result(result, part_name=part_name, color="",
                                 mode=MODE_UNIFORM, instance_index=None,
                                 head_color=_checked_color(head_color),
                                 body_color=_checked_color(body_color),
                                 display_colors=display_colors)
    checked_mode = _checked_mode(mode)
    if instance_index is not None and checked_mode not in (MODE_UNIFORM, MODE_INHERIT):
        raise ValueError("单份选色只支持明确的整份统一换色或恢复部件配色")
    if instance_index is None and checked_mode == MODE_INHERIT:
        raise ValueError("恢复部件配色需要指定一份实体")
    return _recolored_result(result, part_name=part_name,
                             color="" if checked_mode == MODE_INHERIT else _checked_color(color),
                             mode=checked_mode,
                             instance_index=instance_index,
                             display_colors=display_colors)


def color_origin_of(part: Mapping[str, Any]) -> str:
    """``"instance"``／``"manual"``／``"generated"``／``"unrecorded"``。

    旧数据缺少 ``color_origin`` 时无法区分自动颜色与先前手工修改，
    一律报告「未记录」，绝不猜测来源。
    """
    if _part_instance_colors(part) is not None:
        return "instance"
    origin = part.get("color_origin")
    if origin == "manual":
        return "manual"
    return "unrecorded"


def instance_color_rows(part: Mapping[str, Any]) -> Sequence[tuple[int, str]]:
    """``(份序号 1 起, 颜色)``：只列单独改色的份，用于导出与界面说明。"""
    overrides = _part_instance_colors(part)
    if overrides is None:
        return []
    return [(index + 1, color) for index, color in enumerate(overrides) if color]
