"""针法速查表（STITCH_GLOSSARY）——全系统针法词表的单一来源。

覆盖五套语言体系的对照：中文图解字母记号（X/T/F/E/V/A/W/M/B）、
US 官方缩写（Craft Yarn Council 缩写规范逐字核对）、UK 传统记号
（美英"错位一级"：US sc = UK dc，Shelley Husband / KnitPro 对照表）、
日语名称（toruyuri / Hamanaka 系教程：細編み・長編み・増し目），
以及每针的**针数语义**（进出针目比——校验器代数的词汇基础）。

针数语义枚举（count 字段取值）：
- "1→1" 普通针：进 1 目出 1 目，针数不变；
- "1→2"/"1→3" 加针族（V/W）：进 1 目出多目；
- "2→1"/"3→1"/"4→1" 减针族（A/M/sc4tog）；
- "中性（进出各1）"：簇生针族（枣形/泡芙/爆米花）——多针卷入同一
  针目成形后并 1 引出，进出各 1，不改变圈针数（软糖枣形、53stitches
  爆米花逐字印证）；
- "装饰（不入针数）"：狗牙针等边缘花饰——钩在边缘，不占底部针位。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stitch:
    """一条针法词条：中文名 + 五体系记号 + 针数语义 + 分族 + 注。"""

    zh: str          # 中文名（中文图解口径）
    symbol: str      # 中文图解字母记号（无专记者用 US 缩写）
    us: str          # US 缩写（CYC 官方口径）
    uk: str          # UK 缩写（错位一级）
    jp: str          # 日语名称
    count: str       # 针数语义（见模块 docstring 枚举）
    family: str      # 基础针 / 加减针 / 簇生针 / 边缘针 / 挑针与钩位
    note: str        # 一句话说明（含来源锚点）


STITCH_GLOSSARY: tuple[Stitch, ...] = (
    # ── 基础针（针高阶梯：锁针供起立/连接，其余越高越占行高）────────
    Stitch("锁针", "CH", "ch", "ch", "鎖編み", "0→1（新基底）",
           "基础针", "起立与连接；除图解注明（如 Tiny Curl 的 ch-3 计为"
           " 1 针）外不计入圈针数（Motley 口径 ch-1 不计针，两约定并存）"),
    Stitch("引拔针", "SL", "sl st", "sl st", "引き抜き編み", "—（连接）",
           "基础针", "合圈收尾 / 部件连接；合圈每圈末尾 SL 引拔、"
           "起立锁针开启下圈"),
    Stitch("短针", "X", "sc", "dc", "細編み", "1→1",
           "基础针", "amigurumi 主力针；本系统球体/筒体行高按短针估算"),
    Stitch("中长针", "T", "hdc", "htr", "中長編み", "1→1",
           "基础针", "介于短长之间；Tiny Curl 翻面耳为语料首个 hdc 部件"),
    Stitch("长针", "F", "dc", "tr", "長編み", "1→1",
           "基础针", "平面花片主力（长针圆起 12 针，Melonchillo 法则）"),
    Stitch("长长针", "E", "tr", "dtr", "長々編み", "1→1",
           "基础针", "三卷长针，大花片与蕾丝常用"),
    # ── 加减针族（校验器代数的直接对象）────────────────────────────
    Stitch("加针", "V", "inc", "inc", "増し目", "1→2",
           "加减针", "一针目钩 2 短针；错位放置成圆、同点放置成六角形"
           "（toruyuri 法则）"),
    Stitch("减针", "A", "dec / sc2tog", "dec", "減らし目", "2→1",
           "加减针", "隐形减针=只挑两针目前半针并钩；BLO 减针时图解常"
           "指定普通减针（Minion 原文注）"),
    Stitch("三并一", "M", "sc3tog", "dc3tog", "3目一度編み", "3→1",
           "加减针", "三短针并一（面部塑形/快速收窄）"),
    Stitch("四并一", "sc4tog", "sc4tog", "dc4tog", "4目一度編み", "4→1",
           "加减针", "指尖/星角收尖（Minion 腿 R3 与 sc2tog 同圈混用）"),
    Stitch("跳针收口", "sk", "sk", "miss", "飛び目", "跳过（不钩）",
           "加减针", "(1X, 跳过 1 针)×6 与 sc2tog 同数不同法——留洞由"
           "后续收口处理（Motley R62）"),
    # ── 簇生针族（进出各 1——不改变圈针数）────────────────────────
    Stitch("枣形针", "B", "bo / CL", "bobble", "玉編み", "中性（进出各1）",
           "簇生针", "5 未完成长针并 1 针引出，进出各 1（软糖系列逐字）"),
    Stitch("泡芙针", "ps", "ps / puff", "puff", "パフ編み", "中性（进出各1）",
           "簇生针", "同针目多次入线成蓬起后束紧；CYC 缩写 ps/puff"),
    Stitch("爆米花针", "pc", "pc", "popcorn", "ポップコーン編み", "中性（进出各1）",
           "簇生针", "5 长针同针目翻开并 1（53stitches 低缝兔四肢逐字）"),
    # ── 边缘针 / 装饰 ──────────────────────────────────────────────
    Stitch("狗牙针", "picot", "picot", "picot", "ピコット編み", "装饰（不入针数）",
           "边缘针", "锁 3-4 回引拔于起针成小环——齿状花边收口装饰"),
    Stitch("逆短针", "逆X", "crab st / rev sc", "crab st", "逆細編み", "1→1（反向）",
           "边缘针", "反方向钩短针成绳状边——常用于玩偶边缘收边"),
    # ── 挑针与钩位修饰（不改针数，改纹理/朝向）──────────────────────
    Stitch("前/后半针", "FLO/BLO", "FL(O) / BL(O)", "FL / BL", "表山・裏山", "修饰",
           "挑针与钩位", "只挑半针：脊线圈（蜜蜂 BLO）、鞋底换面"
           "（Minion R3/R5/R6 交替）、无痕收口走前半针"),
    Stitch("内钩/外钩", "FP/BP", "FP / BP", "FP / BP", "浮き編み", "修饰",
           "挑针与钩位", "围绕针杆钩出浮凸条纹——CYC 官方 FPdc/BPsc 族"),
)

# US↔UK「错位一级」对照链（Shelley Husband / KnitPro 对照表）——
# 上一级的 UK 名 = 下一级的 US 名，此不变量由测试钉死。
_HEIGHT_LADDER_US_UK: tuple[tuple[str, str], ...] = (
    ("sc", "dc"),
    ("hdc", "htr"),
    ("dc", "tr"),
    ("tr", "dtr"),
    ("dtr", "ttr"),
)


def glossary_note_lines() -> list[str]:
    """导出图例追加行：针高阶梯 + 变化/边缘针族（紧凑两行）。"""
    ladder = "；".join(
        f"{s.symbol}={s.us}" for s in STITCH_GLOSSARY
        if s.symbol in {"X", "T", "F", "E"})
    cluster = "、".join(s.zh for s in STITCH_GLOSSARY if s.family == "簇生针")
    edge = "、".join(s.zh for s in STITCH_GLOSSARY if s.family == "边缘针")
    return [
        f"> 针高阶梯：{ladder}（UK 记号整体错位一级：US sc=UK dc、"
        "US dc=UK tr，读英系图解先辨口径）",
        f"> 变化针族（{cluster}）进出各 1 不改圈针数；边缘装饰"
        f"（{edge}）不占底部针位",
    ]
