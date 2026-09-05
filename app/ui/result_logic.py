"""结果页业务逻辑的纯函数层（fable5.1 审核 P2：UI 函数内嵌业务逻辑抽离）。

render_results 的三条本地重生成/导入流程此前写在按钮回调里，Streamlit
无法单测（照片 Tab 的生成按钮路径覆盖率为零即源于此）。这里抽成不依赖
Streamlit 的纯函数：输入 result dict 与用户输入，输出新的 result dict，
键集由 PatternResult 契约保证；render_results 只负责调用、错误展示与
st.rerun。
"""
from __future__ import annotations

from typing import Any

from app.models.crochet_params import CrochetParamsGenerator, refresh_derived
from app.models.gauge import Gauge, ShapingStyle
from app.models.geometry import normalize_structure
from app.models.sizing import sizing_meta_for_analysis
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis, PatternResult

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


def _result_gauge(result: dict) -> Gauge:
    # gauge 优先取 result 层（生成时写入）；导入的旧备份没有
    # result["gauge"]，回退 params 里随备份保存的 gauge
    raw = result.get("gauge") or (result.get("params") or {}).get("gauge") or {}
    return Gauge(float(raw.get("stitches_per_10cm", 13.0)),
                 float(raw.get("rows_per_10cm", 16.0)))


def _result_style(result: dict) -> ShapingStyle:
    return ShapingStyle(**{**STYLE_DEFAULTS, **(result.get("style") or {})})


def rebuild_params(corrected: dict) -> dict:
    """把用户 JSON 中的 parts 重建为 CrochetPart 并重算派生量（regen/导入共用）。

    CrochetPart 只作校验器：重建后立即 dump 回 dict——params["parts"]
    的内存形态与落盘/分享/历史形态一致（双态收敛，见 _build_result）。
    """
    from app.schemas import CrochetPart, CrochetStitch

    rebuilt_parts = []
    for p in corrected.get("parts", []):
        p = dict(p)  # 不原地改动用户输入
        raw_rounds = p.pop("rounds", [])
        # rows 由 len(rounds) 派生（schema 已无该字段），丢弃过期值防失同步。
        p.pop("rows", None)
        rounds = [CrochetStitch(**r) for r in raw_rounds]
        rebuilt_parts.append(CrochetPart(rounds=rounds, **p).model_dump())
    corrected["parts"] = rebuilt_parts
    # 时长/总针数/材料克数是 parts 的派生量，必须随编辑重算。
    refresh_derived(corrected)
    return corrected


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
    structure = StructureDesigner.design_3d_structure(analysis)
    params = CrochetParamsGenerator.generate_params(
        analysis, structure,
        color_bands=result.get("color_bands"),
        body_profile=result_profile(result),
        gauge=_result_gauge(result), style=_result_style(result),
        spans=result.get("spans"))
    old_sizing = result.get("sizing") or {}
    sizing = sizing_meta_for_analysis(
        analysis, "user_resize",
        photo_head_to_height_ratio=old_sizing.get("photo_head_to_height_ratio"))
    return PatternResult.from_result({
        **result,
        "analysis": analysis.model_dump(),
        "structure": structure,
        "params": params,
        "sizing": sizing,
    }).to_result_dict()


def regenerate_with_structure(result: dict, corrected_structure: dict) -> dict:
    """StructureGeometry 修正：严格校验后本地重生成，不重新调用 AI。"""
    structure = normalize_structure(corrected_structure)
    analysis = ImageAnalysis(**result["analysis"])
    params = CrochetParamsGenerator.generate_params(
        analysis, structure,
        color_bands=result.get("color_bands"),
        body_profile=result_profile(result),
        gauge=_result_gauge(result), style=_result_style(result),
        spans=result.get("spans"))
    return PatternResult.from_result({
        **result,
        "structure": structure,
        "params": params,
    }).to_result_dict()


def import_backup(data: dict, result_id: str) -> dict:
    """备份 JSON → 可渲染的会话 result dict（导入/历史载入共用入口）。

    F24/G1：非重建键按契约从备份数据回填——旧版 setdefault(k, None)
    把 style/gauge 等全写 None。键集由 PatternResult 定义（旧格式缺键
    → None 兜底）；analysis/structure/params 先经校验/重建。
    """
    analysis, structure = validate_backup(data)
    params = rebuild_params(dict(data["params"]))
    return PatternResult.from_result({
        **data,
        "analysis": analysis,
        "structure": structure,
        "params": params,
        "result_id": result_id,
    }).to_result_dict()
