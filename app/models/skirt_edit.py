"""Move an existing generated skirt join without guessing custom instructions."""
from __future__ import annotations

from copy import deepcopy

from app.models.crochet_params import _change_note, refresh_derived
from app.models.instruction_checks import round_expression
from app.models.parts import _ONE_PIECE_NAME
from app.models.profile_shaping import strip_dome
from app.models.stitch_attachments import (
    WAIST_POSITION_KEY,
    LoopAttachmentPlan,
    prepare_attached_skirt,
    validate_waist_position,
)
from app.models.validator import require_valid_pattern

_RESERVATION = "为裙子保留接合位，见装配说明"


def skirt_connection(params: dict) -> dict:
    require_valid_pattern(params)
    plan = LoopAttachmentPlan.model_validate(params.get("stitch_attachments", {}))
    for connection in plan.connections:
        if connection.source_part == "裙子":
            return connection.model_dump()
    raise ValueError("当前图解没有精确接裙记录，请先生成挑针接裙图解")


def waist_rows(params: dict) -> list[dict]:
    """Actual adjacent rows, restricted to the known body region in one-piece work."""
    connection = skirt_connection(params)
    if connection["target_part"] not in ("身体", _ONE_PIECE_NAME):
        raise ValueError("腰位调整仅支持身体或头身一体的接裙记录")
    body = next(p for p in params["parts"] if p["name"] == connection["target_part"])
    rows = body["rounds"]
    start = len(rows) - len(strip_dome([r["stitches"] for r in rows]))
    if body["name"] == _ONE_PIECE_NAME:
        neck = [i for i, r in enumerate(rows) if "此处为颈部" in (r.get("notes") or "")]
        if len(neck) != 1:
            raise ValueError("头身一体缺少唯一颈部标记，无法安全选择身体段腰位")
        start = neck[0]
    return rows[start:-1]


def move_skirt_join(result: dict, target_row: int) -> dict:
    """Keep equal-waist skirts intact; only rebuild recognized generated skirts."""
    if type(target_row) is not int:
        raise ValueError("基底圈号须为整数")
    connection = skirt_connection(result["params"])
    choices = [r["row"] for r in waist_rows(result["params"])]
    if target_row not in choices:
        raise ValueError("请选择身体段内有下一圈的实际基底圈号")
    position = choices.index(target_row) / (len(choices) - 1) if len(choices) > 1 else 0.5
    if target_row == connection["target_row"]:
        updated = deepcopy(result)
        updated["params"][WAIST_POSITION_KEY] = position
        return updated
    updated = deepcopy(result)
    params = updated["params"]
    body = next(p for p in params["parts"] if p["name"] == connection["target_part"])
    skirt = next(p for p in params["parts"] if p["name"] == "裙子")
    rows = body["rounds"]
    old_reserve = next(r for r in rows if r["row"] == connection["reservation_row"])
    prefix, _, suffix = (old_reserve.get("notes") or "").partition("；")
    actions = suffix.split("；")
    if not (prefix.startswith("FLO(") and prefix.endswith(")") and actions[0] == _RESERVATION):
        raise ValueError("原预留圈含手工说明或缺少可还原标记，请先人工核对原圈针法")
    old_reserve["notes"] = prefix[4:-1] + ("；" + "；".join(actions[1:]) if actions[1:] else "")
    index = next(i for i, r in enumerate(rows) if r["row"] == target_row)
    base, reserve = rows[index:index + 2]
    # Do not consume a reservation already used by another component.
    if any(c["source_part"] != "裙子" and c["target_part"] == body["name"]
           and c["target_row"] == target_row for c in params["stitch_attachments"]["connections"]):
        raise ValueError("该圈预留针目已用于其他部件")
    expression = round_expression(reserve.get("notes"))
    if expression is None or expression.has_loop_technique:
        raise ValueError("新预留圈已有特殊挑针或无法识别的说明，请选择普通针法圈")
    changed_waist = base["stitches"] != connection["end_stitch"]
    original_skirt = deepcopy(skirt)
    if changed_waist:
        for i, rd in enumerate(skirt["rounds"]):
            expected = (f"BLO({connection['end_stitch']}X)；接入预留针目，具体圈号见装配说明"
                        if i == 0 else _change_note(skirt["rounds"][i - 1]["stitches"], rd["stitches"]))
            if i and rd.get("allow_wide_jump"):
                expected = f"V×{skirt['rounds'][i - 1]['stitches']}；波浪裙摆"
            if rd.get("notes") != expected:
                raise ValueError("裙子含手工针法或说明；请选择相同针数的腰位，或先人工调整裙子")
    # Use the same generation path and validation as freshly generated joins.
    generated = prepare_attached_skirt(params["parts"], target_row=target_row,
                                       assembly_plan=params.get("assembly_plan"))
    if not changed_waist:
        skirt.clear()
        skirt.update(original_skirt)
    else:
        from app.models.gauge import gauge_from_result

        skirt["height_cm"] = round(len(skirt["rounds"]) * gauge_from_result(result).row_h_cm, 1)
    params["stitch_attachments"]["connections"] = [
        generated["connections"][0] if c["source_part"] == "裙子" else c
        for c in params["stitch_attachments"]["connections"]]
    params[WAIST_POSITION_KEY] = position
    require_valid_pattern(params)
    refresh_derived(params)
    return updated


def unpin_skirt_waist(result: dict) -> dict:
    """Change the next regeneration's policy without altering current stitches."""
    updated = deepcopy(result)
    updated["params"].pop(WAIST_POSITION_KEY, None)
    require_valid_pattern(updated["params"])
    return updated


def preserve_skirt_waist(current: dict, generated: dict) -> dict:
    """Reapply the saved relative candidate position after a full regeneration.

    Preserve the original fraction, not the rounded output row, so repeated
    resizes do not accumulate quantization drift. Explicit skirt removal drops
    the preference with the absent part; ordinary automatic patterns stay automatic.
    """
    if WAIST_POSITION_KEY not in current["params"]:
        return generated
    require_valid_pattern(current["params"])
    if (generated["params"].get("skirt_style") != "attached"
            or not any(p["name"] == "裙子" for p in generated["params"]["parts"])):
        return generated
    position = validate_waist_position(current["params"][WAIST_POSITION_KEY])
    choices = waist_rows(generated["params"])
    if not choices:
        raise ValueError("新身体没有可用腰位，无法保留固定位置；请增加身体高度或取消固定")
    row = choices[round(position * (len(choices) - 1))]["row"]
    updated = move_skirt_join(generated, row)
    updated["params"][WAIST_POSITION_KEY] = position
    return updated
