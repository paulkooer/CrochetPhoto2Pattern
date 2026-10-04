"""结果页业务逻辑的纯函数层（fable5.1 审核 P2：UI 函数内嵌业务逻辑抽离）。

render_results 的三条本地重生成/导入流程此前写在按钮回调里，Streamlit
无法单测（照片 Tab 的生成按钮路径覆盖率为零即源于此）。这里抽成不依赖
Streamlit 的纯函数：输入 result dict 与用户输入，输出新的 result dict，
键集由 PatternResult 契约保证；render_results 只负责调用、错误展示与
st.rerun。
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from app import software_version
from app.models.crochet_params import CrochetParamsGenerator, refresh_derived
from app.models.gauge import ShapingStyle, gauge_from_result
from app.models.geometry import PROPORTIONS_HEAD_BODY_PREFIX, normalize_structure
from app.models.sizing import sizing_meta_for_analysis
from app.schemas import MAX_PATTERN_PARTS, ImageAnalysis, PatternResult

# 与侧栏"塑形选项（进阶）"的默认值同源；result["style"] 缺失时兜底
STYLE_DEFAULTS: dict[str, Any] = {
    "sphere_mode": "ladder", "one_piece": False,
    "skirt_style": "ring", "ruffle_hem": False,
}


def result_profile(result: dict) -> list[float] | None:
    """读取当前几何 IR 剖面；旧结果回退 vision_meta（legacy 备份）。"""
    geometry = result.get("geometry") or {}
    silhouette = geometry.get("silhouette") or {}
    profile = silhouette.get("profile")
    if isinstance(profile, list) and profile:
        return profile
    legacy = ((result.get("vision_meta") or {}).get("silhouette") or {})
    profile = legacy.get("profile")
    return profile if isinstance(profile, list) and profile else None


def _resize_structure(result: dict, analysis: ImageAnalysis) -> dict:
    """Scale physical dimensions while retaining the user's edited graph.

    Diameters and round accessories follow head size; other lengths follow
    the remaining body height, matching the template's two sizing anchors.
    Normalized positions, rotations, connections, counts and colors stay as edited.
    """
    previous = ImageAnalysis(**result["analysis"])
    structure = deepcopy(normalize_structure(result["structure"]))
    previous_head = next((part.get("diameter_cm") for part in structure["parts"]
                          if part["name"] == "头部" and part.get("diameter_cm")), None)
    previous_head = float(previous_head or previous.head_diameter_cm)
    head_scale = analysis.head_diameter_cm / previous_head
    body_scale = (max(analysis.height_cm - analysis.head_diameter_cm, 0.1)
                  / max(previous.height_cm - previous_head, 0.1))
    for part in structure["parts"]:
        round_accessory = part.get("shape") == "sphere" or part["name"] in ("头部", "帽子", "耳朵")
        for key in ("diameter_cm", "height_cm", "length_cm"):
            if part.get(key) is not None:
                scale = head_scale if key == "diameter_cm" or round_accessory else body_scale
                part[key] = float(part[key]) * scale
        # The resize control specifies an absolute head diameter, even when a
        # previous advanced edit changed it independently of analysis metadata.
        if part["name"] == "头部":
            part["diameter_cm"] = analysis.head_diameter_cm
    if str(structure.get("proportions", "")).startswith(PROPORTIONS_HEAD_BODY_PREFIX):
        by_name = {part["name"]: part for part in structure["parts"]}
        head = by_name.get("头部", {}).get("diameter_cm")
        body = by_name.get("身体", {}).get("height_cm")
        if head and body:
            structure["proportions"] = (
                f"{PROPORTIONS_HEAD_BODY_PREFIX}{head / body:.1f} 倍，Q 版卡通比例")
    return normalize_structure(structure)


def _result_style(result: dict) -> ShapingStyle:
    return ShapingStyle(**{**STYLE_DEFAULTS, **(result.get("style") or {})})


def rebuild_params(corrected: dict) -> dict:
    """把用户 JSON 中的 parts 重建为 CrochetPart 并重算派生量（regen/导入共用）。

    CrochetPart 只作校验器：重建后立即 dump 回 dict——params["parts"]
    的内存形态与落盘/分享/历史形态一致（双态收敛，见 _build_result）。
    """
    from app.schemas import CrochetPart

    if (not isinstance(corrected, dict) or not isinstance(corrected.get("parts"), list)
            or not corrected["parts"]):
        raise ValueError("图解必须包含非空 parts 部件列表")
    if len(corrected["parts"]) > MAX_PATTERN_PARTS:
        raise ValueError(f"部件数量超过上限 {MAX_PATTERN_PARTS}")
    rebuilt_parts = []
    names: set[str] = set()
    for p in corrected["parts"]:
        if not isinstance(p, dict):
            raise ValueError("每个部件必须是对象")
        p = dict(p)  # 不原地改动用户输入
        # rows 由 len(rounds) 派生（schema 已无该字段），丢弃过期值防失同步。
        p.pop("rows", None)
        part = CrochetPart(**p)
        if part.name in names:
            raise ValueError(f"部件名称不能重复: {part.name}")
        names.add(part.name)
        rebuilt_parts.append(part.model_dump())
    rebuilt = {**corrected, "parts": rebuilt_parts}
    from app.models.validator import require_valid_pattern

    require_valid_pattern(rebuilt)
    # 时长/总针数/材料克数是 parts 的派生量，必须随编辑重算。
    refresh_derived(rebuilt)
    return rebuilt


def validate_backup(data: dict) -> tuple[dict, dict]:
    """备份 JSON → (analysis, structure)，与 params 同等待遇的入参校验。

    旧版只重建 params，analysis/structure 原样入库——手改坏的结构要到
    下一次 rerun 的渲染层才崩（import 的 try 管不到那里），表现为
    Streamlit 异常页。在这里拦住，错误以 st.error 呈现。
    """
    analysis = ImageAnalysis(**data["analysis"]).model_dump()
    # V2 is a real graph contract: reject dangling attachment/mirror IDs,
    # invalid coordinates and count/instance mismatches at the import edge.
    # Legacy backups retain their historical minimal contract.
    structure = normalize_structure(data["structure"])
    return analysis, structure


def regenerate_with_size(result: dict, new_head: float, new_height: float) -> dict:
    """快速调整尺寸：改头径/身高 → 结构+参数层重算（不重新调用 AI）。

    生成时的 style/gauge/色带随 result 透传，重生成与首次行为一致；
    纯本地计算，无 API 成本。
    """
    analysis = ImageAnalysis(**{
        **result["analysis"],
        "head_diameter_cm": new_head, "height_cm": new_height,
    })
    structure = _resize_structure(result, analysis)
    gauge = gauge_from_result(result)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure,
        color_bands=result.get("color_bands"),
        body_profile=result_profile(result),
        gauge=gauge, style=_result_style(result),
        spans=result.get("spans"))
    _preserve_yarn_spec(result, params)
    old_sizing = result.get("sizing") or {}
    sizing = sizing_meta_for_analysis(
        analysis, "user_resize",
        photo_head_to_height_ratio=old_sizing.get("photo_head_to_height_ratio"))
    return PatternResult.from_result({
        **result,
        "generator_version": software_version(),
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "gauge": asdict(gauge),
        "sizing": sizing,
    }).to_result_dict()


def regenerate_with_structure(result: dict, corrected_structure: dict) -> dict:
    """StructureGeometry 修正：严格校验后本地重生成，不重新调用 AI。"""
    structure = normalize_structure(corrected_structure)
    analysis = ImageAnalysis(**result["analysis"])
    gauge = gauge_from_result(result)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure,
        color_bands=result.get("color_bands"),
        body_profile=result_profile(result),
        gauge=gauge, style=_result_style(result),
        spans=result.get("spans"))
    _preserve_yarn_spec(result, params)
    return PatternResult.from_result({
        **result,
        "generator_version": software_version(),
        "structure": structure,
        "params": params,
        "gauge": asdict(gauge),
    }).to_result_dict()


def import_backup(data: dict, result_id: str) -> dict:
    """备份 JSON → 可渲染的会话 result dict（导入/历史载入共用入口）。

    F24/G1：非重建键按契约从备份数据回填——旧版 setdefault(k, None)
    把 style/gauge 等全写 None。键集由 PatternResult 定义（旧格式缺键
    → None 兜底）；analysis/structure/params 先经校验/重建。
    """
    from app.models.result_metadata import validate_result_metadata

    data = PatternResult.from_result(data).to_backup() | {
        "title": data.get("title"),
    }
    validate_result_metadata(data)
    analysis, structure = validate_backup(data)
    raw_params = dict(data["params"])
    gauge = None
    if raw_params.get("gauge") or data.get("gauge"):
        gauge = asdict(gauge_from_result(data))
        raw_params["gauge"] = gauge
    params = rebuild_params(raw_params)
    return PatternResult.from_result({
        **data,
        "analysis": analysis,
        "structure": structure,
        "params": params,
        "gauge": gauge,
        "result_id": result_id,
    }).to_result_dict()


def _preserve_yarn_spec(result: dict, params: dict) -> None:
    if result.get("params", {}).get("yarn_spec") is not None:
        params["yarn_spec"] = deepcopy(result["params"]["yarn_spec"])
        refresh_derived(params)
