from typing import List, Dict, Any

from ..schemas import CrochetPart, CrochetStitch, ImageAnalysis


def _sphere_rounds(max_stitches: int = 36) -> List[Dict[str, Any]]:
    """Generate increase -> constant -> decrease rounds for an Amigurumi sphere.
    max_stitches must be a positive multiple of 6.
    """
    step = 6
    n_up = max_stitches // step

    increase = [
        {
            "row": r,
            "stitches": step * r,
            "increase": step if r > 1 else 0,
            "notes": "魔法环起6针" if r == 1 else f"每{r - 1}针加1针",
        }
        for r in range(1, n_up + 1)
    ]
    constant = [
        {"row": n_up + i, "stitches": max_stitches, "notes": "不加不减"}
        for i in range(1, n_up + 1)
    ]
    decrease = []
    for i in range(1, n_up):
        remaining = max_stitches - step * i
        if remaining <= 0:
            break
        decrease.append({
            "row": n_up * 2 + i,
            "stitches": remaining,
            "decrease": step,
            "notes": f"每{remaining // step}针减1针",
        })

    return increase + constant + decrease


def _cylinder_rounds(max_stitches: int = 24, body_rounds: int = 15) -> List[Dict[str, Any]]:
    """Generate cylinder: increase to max_stitches, hold, then 2 taper rounds."""
    step = 6
    n_up = max_stitches // step

    increase = [
        {
            "row": r,
            "stitches": step * r,
            "increase": step if r > 1 else 0,
            "notes": "魔法环起6针" if r == 1 else f"每{r - 1}针加1针",
        }
        for r in range(1, n_up + 1)
    ]
    constant = [
        {"row": n_up + i, "stitches": max_stitches, "notes": "不加不减"}
        for i in range(1, body_rounds + 1)
    ]
    decrease = []
    for i in range(1, 3):
        remaining = max_stitches - step * i
        if remaining > 0:
            decrease.append({
                "row": n_up + body_rounds + i,
                "stitches": remaining,
                "decrease": step,
                "notes": "收针",
            })

    return increase + constant + decrease


class CrochetParamsGenerator:
    """Generate crochet parameters for each part."""

    @staticmethod
    def generate_params(analysis: ImageAnalysis, structure: Dict) -> Dict:
        """Generate crochet parameters using structure data for dimensions.

        rows is always computed from len(rounds) for data consistency.
        """
        struct_parts: Dict[str, Dict] = {
            p["name"]: p for p in structure.get("parts", [])
        }

        crochet_parts: List[CrochetPart] = []

        for part_name in analysis.parts:
            sp = struct_parts.get(part_name, {})
            is_head = part_name == "头部"
            shape = sp.get("shape", "sphere" if is_head else "cylinder")

            if is_head or shape == "sphere":
                # Head, ears, hats and other roundish parts — sized by diameter
                fallback_d = (
                    analysis.head_diameter_cm if is_head
                    else round(analysis.head_diameter_cm * 0.4, 1)
                )
                diameter = sp.get("diameter_cm", fallback_d)
                max_st = max(6, round(diameter / 9.0 * 36 / 6) * 6)
                rounds_raw = _sphere_rounds(max_stitches=max_st)
                if is_head:
                    color = sp.get("color", "skin")
                    notes = (
                        f"标准球形，最大 {max_st} 针。"
                        "第2/3高度处安装安全眼。建议先钩小样测试张力。"
                    )
                else:
                    color = sp.get("color", "body")
                    notes = f"小球形部件（直径 {diameter}cm），完成后缝合到主体。"
                part = CrochetPart(
                    name=part_name,
                    type="sphere",
                    diameter_cm=diameter,
                    rows=len(rounds_raw),
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=color,
                    magic_ring=True,
                    notes=notes,
                )

            elif part_name == "身体":
                height = sp.get("height_cm", 9.0)
                body_r = max(4, round(height * 1.6))
                rounds_raw = _cylinder_rounds(max_stitches=24, body_rounds=body_r)
                part = CrochetPart(
                    name=part_name,
                    type="cylinder",
                    height_cm=height,
                    rows=len(rounds_raw),
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "body"),
                    notes=f"圆柱身体（高 {height}cm）。收针前填充棉花。",
                )

            else:
                # Limbs, tails, skirts and any other slim cylinder: 12 stitches,
                # so accessories never come out body-sized.
                length = sp.get("length_cm") or sp.get("height_cm") or 5.0
                limb_r = max(2, round(length * 1.2))
                rounds_raw = _cylinder_rounds(max_stitches=12, body_rounds=limb_r)
                part = CrochetPart(
                    name=part_name,
                    type="cylinder",
                    height_cm=length,
                    rows=len(rounds_raw),
                    rounds=[CrochetStitch(**r) for r in rounds_raw],
                    color=sp.get("color", "skin" if part_name in ("手臂", "腿部") else "body"),
                    notes=f"{part_name}（长 {length}cm），两端留线头便于缝合。",
                )

            crochet_parts.append(part)

        return {
            "materials": [
                {"item": "皮肤色毛线", "quantity": "约 60g"},
                {"item": "身体色毛线", "quantity": "约 30g"},
                {"item": "安全眼", "quantity": "一对 (8mm)"},
                {"item": "填充棉", "quantity": "适量"},
                {"item": "2.5mm 毛线钩针", "quantity": "1 把"},
                {"item": "缝合针", "quantity": "1 根"},
            ],
            "parts": crochet_parts,
            "assembly_instructions": (
                "1. 各部件分别完成并填充棉花\n"
                "2. 头部安装安全眼（第2/3高度处）\n"
                "3. 用隐形缝合法将头部接合到身体顶部\n"
                "4. 用黑色毛线绣鼻子和嘴巴\n"
                "5. 手臂和腿部对称缝合到身体两侧"
            ),
            "difficulty": analysis.difficulty,
            "estimated_time_minutes": 180,
            "notes": "基于单图 AI 推理生成，部分比例可能需要试钩调整。",
        }
