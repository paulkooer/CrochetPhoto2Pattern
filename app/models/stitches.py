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
           "指定普通减针（Minion 原文注）。其他针高的减针（CYC 官方）："
           "hdc2tog / dc2tog / tr2tog，记号依各图解自定义"),
    Stitch("三放一", "W", "3 sc in same st", "3 dc in same st", "1目に3目",
           "1→3", "加减针", "一针目钩 3 短针——椭圆起针端盖与花瓣加厚"
           "（Patchy Bear 口鼻 [10] 的末针 3X；中文图解通用记号 W）"),
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
    # ── 纹理针（针数如标注，另带表面纹理/方向性）────────────────────
    Stitch("圈圈针", "loop st", "loop st", "loop st", "ループ編み",
           "1→1（反面起圈）", "纹理针",
           "钩短针时在指上绕大环——环圈成于**反面**：要么反过来钩让毛圈"
           "朝外，要么用 front-side 变体（cbfiberworks）；环起处勿直接"
           "钩圈圈（先 1 圈普通短针）；费线明显（Yarnhild）。玩偶毛发/"
           "绵羊卷毛主力"),
    Stitch("双圈圈针", "double loop", "double loop st", "double loop st",
           "ダブルループ", "1→1（反面起圈）", "纹理针",
           "一针内留两道环——更浓密但会使织物明显内卷，即使均匀加针"
           "（cbfiberworks 工艺警告）"),
    Stitch("圈圈减针", "loop dec", "loop st dec", "loop st dec", "ループ編み減らし",
           "2→1（挂4环并拉过）", "纹理针",
           "圈圈针减针：钩针上保留 4 个环再拉过（基础圈圈；front-side "
           "变体 3 环、双圈 5 环）——cbfiberworks 逐字"),
    # ── 挑针与钩位修饰（不改针数，改纹理/朝向）──────────────────────
    Stitch("前/后半针", "FLO/BLO", "FL(O) / BL(O)", "FL / BL", "表山・裏山", "修饰",
           "挑针与钩位", "只挑半针：脊线圈（蜜蜂 BLO）、鞋底换面"
           "（Minion R3/R5/R6 交替）、无痕收口走前半针"),
    Stitch("内钩/外钩", "FP/BP", "FP / BP", "FP / BP", "浮き編み", "修饰",
           "挑针与钩位", "围绕针杆钩出浮凸条纹——CYC 官方 FPdc/BPsc 族"),
)

# 突尼斯（Tunisian）针族——CYC 官方缩写表逐字（13 条：12 针 + 进程结构）。
# 与普通钩针不同：长钩带线，每行由「前进程（FwP）+ 退进程（RetP）」构成；
# 圈代数（st = prev + inc − dec）按行计，不适用于圈针数校验。
# 日语通称アフガン編み，各针无通行汉字略记，故 jp 列统一标注通称。
_TN = "突尼斯针"

TUNISIAN_GLOSSARY: tuple[Stitch, ...] = (
    Stitch("突尼斯简单针", "tss", "tss", "Tunisian simple st", "アフガン編み",
           "1→1（按前进程）", _TN, "突尼斯针的「平针」——柱上取针（CYC 官方）"),
    Stitch("突尼斯下针", "tks", "tks", "Tunisian knit st", "アフガン編み",
           "1→1（按前进程）", _TN, "织出棒针风「下针」纹理"),
    Stitch("突尼斯上针", "tps", "tps", "Tunisian purl st", "アフガン編み",
           "1→1（按前进程）", _TN, "织出棒针风「上针」纹理"),
    Stitch("突尼斯短针", "tsc", "tsc", "Tunisian single crochet", "アフガン編み",
           "1→1（按前进程）", _TN, "退进程即钩——织物最接近普通短针"),
    Stitch("突尼斯中长针", "thdc", "thdc", "Tunisian half double", "アフガン編み",
           "1→1（按前进程）", _TN, "CYC 官方 thdc"),
    Stitch("突尼斯长针", "tdc", "tdc", "Tunisian double crochet", "アフガン編み",
           "1→1（按前进程）", _TN, "CYC 官方 tdc"),
    Stitch("突尼斯反向针", "trs", "trs", "Tunisian reverse st", "アフガン編み",
           "1→1（按前进程）", _TN, "柱后方进针，形成凸起棱线"),
    Stitch("突尼斯引拔针", "tslst", "tslst", "Tunisian slip st", "アフガン編み",
           "1→1（按前进程）", _TN, "常用于收边或缩行"),
    Stitch("突尼斯长长针", "ttr", "ttr", "Tunisian treble", "アフガン編み",
           "1→1（按前进程）", _TN, "CYC 官方 ttr"),
    Stitch("突尼斯全针", "tfs", "tfs", "Tunisian full st", "アフガン編み",
           "1→1（按前进程）", _TN, "柱间空档进针（网格纹理）"),
    Stitch("扩展突尼斯简单针", "etss", "etss", "extended Tunisian simple",
           "アフガン編み", "1→1（按前进程）", _TN,
           "每针加一锁针垫高——防卷边（CYC 官方 etss）"),
    Stitch("扭针", "ttw", "ttw", "Tunisian twisted", "アフガン編み",
           "1→1（按前进程）", _TN, "CYC 官方 ttw（twisted simple stitch）"),
    Stitch("前进程/退进程", "FwP/RetP", "FwP / RetP", "forward / return pass",
           "アフガン編み", "—（行结构）", _TN,
           "突尼斯行 = 前进程挂线不退 + 退进程并锁收针；「圈」概念不适用"),
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


def _table_markdown(entries: tuple[Stitch, ...], title: str) -> str:
    """词条组 → markdown 表（结果页「针法速查」折叠区）。"""
    lines = [
        f"**{title}**",
        "",
        "| 记号 | 针法 | US | UK | 日语 | 针数 | 说明 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {s.symbol} | {s.zh} | {s.us} | {s.uk} | {s.jp} | "
        f"{s.count} | {s.note} |" for s in entries)
    return "\n".join(lines)


def symbol_strip_html() -> str:
    """钩织图解符号条（inline SVG）——与真实图解的图形记号对照。

    通道注意：st.html 的 DOMPurify 净化器会剥掉整个 <svg>（1.60 实测），
    必须走 st.markdown unsafe_allow_html（无空行、不经 markdown 重排）。
    """
    from app import theme

    def _svg(paths: str) -> str:
        return (f'<svg width="30" height="30" viewBox="0 0 24 24" '
                f'fill="none" stroke="{theme.INK}" stroke-width="1.8" '
                f'stroke-linecap="round" stroke-linejoin="round">'
                f"{paths}</svg>")

    _top = "M4.5 5.5 H19.5 M12 5.5 V19"
    glyphs: tuple[tuple[str, str, str], ...] = (
        ("锁针", "CH", _svg('<ellipse cx="12" cy="12" rx="8.5" ry="4.2"/>')),
        ("引拔", "SL", _svg(f'<circle cx="12" cy="12" r="3.2" '
                            f'fill="{theme.INK}"/>')),
        ("短针", "X", _svg('<path d="M5 4.5 L19 19.5 M19 4.5 L5 19.5"/>')),
        ("加针", "V", _svg('<path d="M5 5 L12 19 L19 5"/>')),
        ("减针", "A", _svg('<path d="M5 19 L12 5 L19 19"/>')),
        ("三放一", "W", _svg('<path d="M4 5 L8.5 19 L12 8 L15.5 19 L20 5"/>')),
        ("中长针", "T", _svg(f"<path d=\"{_top}\"/>")),
        ("长针", "F", _svg(f"<path d=\"{_top} M7.5 11.5 H16.5\"/>")),
        ("长长针", "E", _svg(f"<path d=\"{_top} M7.5 10.5 H16.5 "
                             f'M7.5 14.5 H16.5\"/>')),
        ("枣形针", "B", _svg('<path d="M12 3.5 C18 9 18 15 12 20.5 '
                             'C6 15 6 9 12 3.5 Z M10 9.5 V15.5 '
                             'M12 8.5 V16.5 M14 9.5 V15.5"/>')),
    )
    items = "".join(
        f'<div style="text-align:center;min-width:40px;">{svg}'
        f'<div style="font-size:11px;color:{theme.INK_SOFT};'
        f'margin-top:2px;white-space:nowrap;">{zh} {sym}</div></div>'
        for zh, sym, svg in glyphs)
    return (f'<div style="display:flex;flex-wrap:wrap;gap:8px 12px;'
            f'align-items:flex-end;">{items}</div>')


def glossary_table_markdown() -> str:
    """主针法表 + 突尼斯子表（每针含来源锚点；逐字口径见 docs/SOURCES.md）。"""
    parts = [
        _table_markdown(STITCH_GLOSSARY, "钩针针法（五体系对照）"),
        "",
        _table_markdown(TUNISIAN_GLOSSARY,
                        "突尼斯针族（アフガン編み；按行工艺，圈代数不适用）"),
        "",
        "> 各词条来源锚点与逐字口径见仓库内 docs/SOURCES.md"
        "（外部校准证据链）。",
    ]
    return "\n".join(parts)
