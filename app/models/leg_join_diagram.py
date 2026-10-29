"""Count-only diagram for a manually specified chain bridge."""
from __future__ import annotations

import json

from app.models.leg_join import decode_leg_join_plan


def leg_join_svg(plan: dict) -> str:
    """Render a validated plan as a count diagram, not a stitch placement map."""
    checked = decode_leg_join_plan(json.dumps(plan, ensure_ascii=False).encode("utf-8"))
    left, right = checked["left"], checked["right"]
    chain, total = checked["chain_stitches"], checked["result_stitches"]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 820 288" role="img" '
        'aria-labelledby="leg-title leg-desc">'
        '<title id="leg-title">锁针并腿数量示意</title>'
        '<desc id="leg-desc">两个开口与连接锁针的两侧分别计数，不表示实际针位或方向。</desc>'
        '<rect width="820" height="288" rx="16" fill="#f6f7fb"/>'
        '<g font-family="sans-serif" fill="#24324b">'
        '<text x="24" y="32" font-size="19" font-weight="bold">锁针并腿 · 数量示意</text>'
        '<rect x="24" y="48" width="375" height="70" rx="9" fill="white" stroke="#b3bacd"/>'
        '<rect x="421" y="48" width="375" height="70" rx="9" fill="white" stroke="#b3bacd"/>'
        f'<text x="38" y="74" font-size="16">左腿：第 {left["row"]} 圈 · {left["stitches"]} 针</text>'
        f'<text x="38" y="100" font-size="14">填写的记号针：第 {left["marker"]} 针</text>'
        f'<text x="435" y="74" font-size="16">右腿：第 {right["row"]} 圈 · {right["stitches"]} 针</text>'
        f'<text x="435" y="100" font-size="14">填写的记号针：第 {right["marker"]} 针</text>'
        '<rect x="24" y="130" width="772" height="65" rx="9" fill="#e6eefb" stroke="#b3bacd"/>'
        f'<text x="38" y="157" font-size="16">连接锁针：{chain} 针</text>'
        f'<text x="38" y="181" font-size="14">锁针一侧钩 {chain} 针；另一侧钩 {chain} 针</text>'
        f'<text x="24" y="226" font-size="18" font-weight="bold">'
        f'连接圈：{left["stitches"]} + {right["stitches"]} + 2 × {chain} = {total} 针</text>'
        '<text x="24" y="258" font-size="13">仅为计数关系；不表示实物比例、起点、针位或钩织方向。</text>'
        '<text x="24" y="278" font-size="13">须核对开口、记号及连接方式；加减针或其他接法不适用。</text>'
        '</g></svg>'
    )
