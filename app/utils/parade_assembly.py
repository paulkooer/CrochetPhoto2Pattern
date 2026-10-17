"""CrochetPARADE 装配块：把 ``start_anew`` 出来的独立部件摆成成品姿态。

本模块只做**文本合成与布局估算**，不运行外部仿真。

为什么需要它（均在本机对 crochetparade.org 实测得到，勿凭记忆改动）：

- ``start_anew`` 产生的独立部件默认会被求解器的"斥力"推到场景各处，
  且每件的默认**朝向**由 CP 编译后的物理求解器决定。实测三个完全相同的
  圆柱得到三个不同朝向；同一部件在不同 ``DOT:`` 配置下朝向也不同。
  即：默认姿态**可复现但静态不可预测**。
- 加 ``DOT: separate=0`` 后所有独立部件会收回原点——这样**平移**就变成
  可预测的，本项目可以按解剖布局算出来。实测：本模块以\"针\"为单位算出的
  平移与 CP 场景坐标**1:1**（8/8 部件的落点比值都是 1.00），无需再乘系数。

因此装配块 = ``DOT: separate=0`` + 每个部件一行 ``TRANSFORM_OBJECT``
（平移按布局算出、旋转留 0）。要在 CP 里得到完整姿态，可在其 Object
Transform 面板中逐个摆正朝向；本项目自己的 3D 预览（preview3d）则直接
按布局出图，不依赖 CP。
"""
from __future__ import annotations

import math
from typing import Any

SEPARATE_LINE = "DOT: separate=0"

# 名称 → 角色。中文模板名与英文模板名都覆盖；先匹配到的先赢，
# 所以"耳"要排在"头"前面（"耳朵"里没有"头"，但保险起见保持从具体到宽泛）。
_ROLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ear", ("耳", "ear")),
    ("head", ("头", "head", "脸", "face")),
    ("body", ("身体", "躯干", "body", "torso")),
    ("arm", ("手臂", "胳膊", "arm")),
    ("leg", ("腿", "脚", "leg", "foot")),
    ("tail", ("尾巴", "尾", "tail")),
    ("hat", ("帽", "hat")),
    ("skirt", ("裙", "skirt")),
)

# 每圈在竖直方向占的针高系数：球体/圆筒实测在 0.6–0.8 之间，
# 统一取 0.7 用于布局估算（只影响部件间距，不影响图解本身）。
_ROW_STITCH = 0.7


def part_role(name: str) -> str:
    """部件名 → 解剖角色（head/body/ear/arm/leg/tail/other）。"""
    low = name.lower()
    for role, keys in _ROLE_KEYWORDS:
        if any(k in low or k in name for k in keys):
            return role
    return "other"


def part_extent(rounds: list[Any]) -> tuple[float, float]:
    """部件 → （半径, 高度），单位为"针"（1 针宽 = 1）。

    半径按周长 r = N_max/(2π)；高度按圈数 × 0.7 针高。
    无效圈返回 (0, 0)，调用方按"贴在一起"处理。
    """
    stitches = []
    for rd in rounds or []:
        if not isinstance(rd, dict):
            continue
        try:
            n = int(rd.get("stitches") or 0)
        except (TypeError, ValueError):
            continue
        if n > 0:
            stitches.append(n)
    if not stitches:
        return 0.0, 0.0
    radius = max(stitches) / (2 * math.pi)
    return radius, len(stitches) * _ROW_STITCH


def _copy_spread(index: int, count: int) -> float:
    """数量 >1 时的左右展开系数：均匀落在 [-1, +1]，第 1 份在左（-1）。"""
    if count <= 1:
        return 0.0
    return (index - (count - 1) / 2) * 2 / (count - 1)


def layout_from_extents(parts: list[dict[str, Any]],
                        extents: list[tuple[float, float]]
                        ) -> list[tuple[float, float, float]]:
    """核心布局（与单位无关）：extents 为每个部件的（半径, 高度）。

    +y 向上、原点在身体中心、x 为左右镜像轴；返回按导出顺序展开的每个
    实体中心。CP 导出用\"针\"为单位，项目 3D 预览用厘米，两者共用这一份。
    """
    roles = [part_role(str(p.get("name", ""))) for p in parts]

    def extent_for(role: str) -> tuple[float, float]:
        for role_of, (radius, height) in zip(roles, extents, strict=True):
            if role_of == role:
                return radius, height
        return 0.0, 0.0

    body_radius, body_height = extent_for("body")
    if body_height <= 0:  # 没识别出身体：用最高的部件当躯干
        heights = [h for _, h in extents]
        index = heights.index(max(heights)) if heights else -1
        if index >= 0:
            body_radius, body_height = extents[index]
    body_half = body_height / 2
    head_radius, head_height = extent_for("head")
    head_centre = body_half + head_height / 2 - 0.2 * min(body_height, head_height)

    positions: list[tuple[float, float, float]] = []
    for part, role, (radius, height) in zip(parts, roles, extents, strict=True):
        count = max(1, int(part.get("quantity") or 1))
        for index in range(count):
            spread = _copy_spread(index, count)
            if role == "body":
                positions.append((0.0, 0.0, 0.0))
            elif role == "head":
                positions.append((0.0, head_centre, 0.0))
            elif role == "ear":
                x = spread * 0.4 * max(head_radius, radius)
                y = (head_centre + head_height / 2 + height / 2
                     - 0.25 * min(head_height, height))
                positions.append((x, y, 0.0))
            elif role == "arm":
                x = spread * (body_radius + 0.5 * radius)
                positions.append((x, body_half - 0.45 * height, 0.0))
            elif role == "leg":
                x = spread * 0.45 * body_radius
                positions.append((x, -body_half - 0.55 * height, 0.0))
            elif role == "hat":
                # 戴在头顶（与耳同高，但居中）
                y = (head_centre + head_height / 2 + height / 2
                     - 0.25 * min(head_height, height))
                positions.append((0.0, y, 0.0))
            elif role == "skirt":
                # 围在身体下段
                positions.append((0.0, -0.15 * body_height, 0.0))
            else:
                # 帽子/尾巴/眼睛等：贴在身体上侧，多份时左右分开
                x = spread * 0.5 * body_radius
                if role == "tail":
                    positions.append((x, body_half * 0.4, 0.0))
                else:
                    positions.append(
                        (x, body_half + height / 2 - 0.2 * height, 0.0))
    return positions


def layout_positions(parts: list[dict[str, Any]]) -> list[tuple[float, float, float]]:
    """params.parts（按导出顺序、数量展开）→ 每个实体的目标中心（针坐标）。

    只依赖部件自身的圈数/针数，因此与图解严格一致。坐标约定见
    :func:`layout_from_extents`。
    """
    return layout_from_extents(
        parts, [part_extent(p.get("rounds") or []) for p in parts])


def assembly_lines(parts: list[dict[str, Any]]) -> list[str]:
    """params.parts → 装配块行（``DOT:`` + ``TRANSFORM_OBJECT``）。

    返回空列表表示没有可装配的实体。
    """
    if not parts:
        return []
    positions = layout_positions(parts)
    if not positions:
        return []
    lines = [
        "# ── 装配（预览用）──",
        "# separate=0 先把独立部件收回原点；下面的平移按解剖布局算出。",
        "# 注意：CP 给每个部件的默认朝向由物理求解器决定、静态无法预测，",
        "# 故旋转留 0——朝向可在 CP 的 Object Transform 面板逐个摆正，",
        "# 或直接参考本项目的 3D 预览图。",
        SEPARATE_LINE,
    ]
    for index, (x, y, z) in enumerate(positions):
        coords = ",".join(f"{value:.4f}" if value else "0" for value in (x, y, z))
        lines.append(f"TRANSFORM_OBJECT: {index},{coords},0,0,0")
    return lines
