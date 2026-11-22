"""Compose editable clothed-doll designs from independently checked components."""
from __future__ import annotations

import itertools
import math

from app.models.crochet_params import _ideal_sphere_rounds
from app.models.gauge import Gauge

from .models import Component, DollDesign, DollPlan, Foundation, Join
from .recipes import (
    RoundBuilder,
    brim_cap,
    circular,
    count_for_diameter,
    leg,
    open_cap,
    oval_boot,
    panel,
    segmented_arm,
    skirt,
    strand,
)

STARTER_LABELS = {"wide_brim_curls": "宽檐帽·卷发·连衣裙", "folded_cap_layers": "翻边帽·长发·短外套与裙层"}


def starter_design(name: str, *, height_cm: float = 24, gauge: Gauge | None = None) -> DollDesign:
    if name not in STARTER_LABELS:
        raise ValueError("未知穿衣人偶起始方案")
    gauge = gauge or Gauge(22, 28)
    scale = height_cm / 24
    values = {key: value * scale for key, value in {
        "head_diameter_cm": 6, "leg_length_cm": 6, "body_diameter_cm": 3.6,
        "neck_diameter_cm": 1.2, "arm_length_cm": 6, "palm_diameter_cm": 1.5,
        "wrist_diameter_cm": 0.9, "foot_length_cm": 3, "foot_width_cm": 1.6,
        "brim_width_cm": 1.8, "bodice_length_cm": 5.4, "skirt_length_cm": 7, "bag_width_cm": 4,
        "bag_height_cm": 4.5, "strap_length_cm": 20,
    }.items()}
    return DollDesign.model_validate(values | {
        "height_cm": height_cm,
        "hat": "wide_brim" if name == "wide_brim_curls" else "folded_band",
        "hair": "curls" if name == "wide_brim_curls" else "straight",
        "outfit": "dress" if name == "wide_brim_curls" else "jacket_skirt",
        "flowers": name == "wide_brim_curls",
        "stitches_per_10cm": gauge.stitches_per_10cm, "rows_per_10cm": gauge.rows_per_10cm,
    })


class _PlanBuilder:
    def __init__(self, design: DollDesign):
        self.design = design
        self.gauge = Gauge(design.stitches_per_10cm, design.rows_per_10cm)
        self.components: list[Component] = []
        self.joins: list[Join] = []
        self.eye_round = 0

    def add(self, part: Component, target: str | None = None, placement: str = "") -> Component:
        self.components.append(part)
        if target is not None:
            self.joins.append(Join(source=part.id, target=target, placement=placement))
        return part

    def body_and_limbs(self) -> tuple[int, int]:
        d, g = self.design, self.gauge
        torso = count_for_diameter(d.body_diameter_cm, g, minimum=8)
        neck = count_for_diameter(d.neck_diameter_cm, g)
        if neck >= torso:
            raise ValueError("当前密度下颈部与身体无法分出不同围度，请调整尺寸或密度")
        body_height = d.height_cm - d.head_diameter_cm - d.leg_length_cm
        target_rounds = round(body_height / g.row_h_cm)

        def shaped(lower: int, upper: int) -> RoundBuilder:
            builder = RoundBuilder(g)
            builder.step(torso, "下身")
            builder.hold(lower, "下身")
            builder.step(max(neck + 2, round(torso * 0.8)), "腰部")
            builder.hold(2, "腰部")
            builder.step(torso, "胸肩")
            builder.hold(upper, "胸肩")
            builder.step(neck, "肩部向颈部收窄")
            builder.hold(max(2, round(1.0 / g.row_h_cm)), "独立颈段")
            return builder

        def heights(builder: RoundBuilder) -> tuple[float, float]:
            """Two estimates of the finished height, from the input gauge.

            High: every round adds one row height. Low: a round adds only the
            axial part of its row height, so the base disc and the shoulder
            shelf add almost nothing. A stuffed body lies between the two.
            """
            counts = [s.stitches for s in builder.steps]
            low = sum(
                math.sqrt(max(0.0, g.row_h_cm ** 2 - ((b - a) * g.stitch_w_cm / (2 * math.pi)) ** 2))
                for a, b in itertools.pairwise(counts))
            return len(counts) * g.row_h_cm, low

        lower, upper = max(2, round(target_rounds * 0.2)), max(2, round(target_rounds * 0.3))
        body = shaped(lower, upper)
        # The shaping, waist and neck rounds do not grow with the target height,
        # so two fixed shares of it left larger bodies short. Plain rounds add one
        # row height to both estimates: add or remove them until the midpoint of
        # the two estimates meets the target, keeping two plain rounds per section.
        high, low = heights(body)
        change = round((body_height - (high + low) / 2) / g.row_h_cm)
        change = max(change, 4 - lower - upper)
        if change:
            lower_share = round(change * 0.4)
            lower, upper = lower + lower_share, upper + change - lower_share
            if lower < 2:
                lower, upper = 2, upper + lower - 2
            if upper < 2:
                lower, upper = lower + upper - 2, 2
            body = shaped(lower, upper)
            high, low = heights(body)
        self.add(circular("body", "身体与颈段", "下身—腰—胸肩—颈部", body, color="肤色",
                          finish="在颈口仍能操作时分次填棉；颈口留开口和长线头，连接到头底",
                          fitting=["先试穿所有衣物；记录腰围、胸围、颈围以及身体实际高度",
                                   f"身体与颈段的目标高度是 {body_height:.1f} cm，共 {len(body.steps)} 圈。"
                                   f"按输入密度有两种估算：每一圈都按行高计，约 {high:.1f} cm；"
                                   f"起底、腰部和收肩的加减针圈只计其竖直部分，约 {low:.1f} cm。"
                                   "填棉后的实际高度预计在两者之间，圈数按两者的中间值对齐目标。"
                                   "两个数都不是实测：先钩好身体、填棉后量实际高度，"
                                   "偏矮或偏高就在下身或胸肩增减平钩圈，定下来再做衣物"]))
        raw = _ideal_sphere_rounds(d.head_diameter_cm, g, egg=True)
        head = RoundBuilder(g, raw[0]["stitches"])
        for row in raw[1:]:
            head.step(row["stitches"], "头部轮廓")
        peak = max(s.stitches for s in head.steps)
        first_peak = next(i + 1 for i, s in enumerate(head.steps) if s.stitches == peak)
        eye = min(len(head.steps) - 1, first_peak + 1)
        self.eye_round = eye
        self.add(circular("head", "头部", "独立头部", head, color="肤色",
                          finish=f"第 1 圈为头顶，末圈侧为头底；第 {eye} 圈为眼位候选。"
                                 "安装安全眼并扣好内侧垫片后再分次填棉；末圈穿线收口，留线连接颈部",
                          fitting=["眼位只是设计候选，先用珠针试摆；测头宽与头高，不能把目标头径当实测"]),
                 "body", "头底与颈口对应，先用珠针定位，颈部逐段填紧后缝合")
        palm = count_for_diameter(d.palm_diameter_cm, g, minimum=6)
        wrist = count_for_diameter(d.wrist_diameter_cm, g)
        upper = max(wrist + 2, palm - 2)
        self.add(segmented_arm(d.arm_length_cm, palm, wrist, upper, g), "body",
                 "两只手臂对称放在肩部；先穿过对应袖筒，再将肩端留口缝到身体")
        leg_n = count_for_diameter(max(d.wrist_diameter_cm, d.foot_width_cm * 0.65), g, minimum=6)
        self.add(leg(d.leg_length_cm, leg_n, g), "body", "两条腿在身体底部对称定位，先核对站姿与腿长，再缝合")
        self.add(oval_boot(d.foot_length_cm, d.foot_width_cm, leg_n, g), "legs",
                 "鞋头朝前，左右腿分别试穿鞋口；合身后缝少量定位针，不缝死错误的鞋口")
        return peak, max(palm, upper)

    def hair_and_hat(self, head_peak: int) -> None:
        d, g = self.design, self.gauge
        cap_rim = head_peak + 2
        cap = open_cap("hair_cap", "发帽底座", cap_rim,
                       max(2, round(d.head_diameter_cm * 0.3 / g.row_h_cm)), g,
                       color="发色", role="发帽")
        # Say where the rim is expected to fall from the generated counts, rather
        # than promising a position. The cap and the head have different profiles,
        # so round numbers are only a rough guide and a pinned fitting decides.
        cap_rounds = len(cap.steps)
        if cap_rounds >= self.eye_round:
            placement = (f"发帽共 {cap_rounds} 圈，眼位候选在头部第 {self.eye_round} 圈：对齐头顶平戴时，"
                         "帽缘预计落在眼位同一高度或更低。请把发帽向后倾斜，使前缘高于眼位、后缘落在后脑下部，"
                         "用珠针固定，对照已装好的眼睛确认；前缘仍遮眼时，拆掉发帽末尾的平钩圈后再缝。"
                         "圈号只是按针数的估计，两个部件轮廓不同，须以试戴为准")
        else:
            placement = (f"发帽共 {cap_rounds} 圈，眼位候选在头部第 {self.eye_round} 圈；先对齐头顶，"
                         "用珠针固定，对照已装好的眼睛确认帽缘在眼位上方后再缝到头部")
        self.add(cap, "head", placement)
        self.add(strand("hair", "长发束", d.hair_chain_count, d.hair_strands,
                        curled=d.hair == "curls", color="发色"), "hair_cap",
                 "先做一根校对垂长，余下沿两侧和后部均匀分配；前额留出脸部空间")
        self.add(strand("fringe", "前额短发束", max(6, d.hair_chain_count // 2), 4,
                        curled=d.hair == "curls", color="发色"), "hair_cap",
                 "四根作为前额候选，先用珠针试摆，避免遮住眼位")
        hat_rim = cap_rim + max(2, math.ceil(d.garment_ease_cm / g.stitch_w_cm))
        depth = max(2, round(d.head_diameter_cm * 0.35 / g.row_h_cm))
        if d.hat == "wide_brim":
            hat = brim_cap(hat_rim, depth, max(1, round(d.brim_width_cm / g.row_h_cm)), g, color="帽色")
        else:
            hat = open_cap("hat", "帽身", hat_rim, depth + 2, g, color="帽色")
            self.add(panel("hat_band", "片钩肋纹翻边", "帽边", max(3, round(2 / g.stitch_w_cm)),
                           max(6, round(hat_rim * g.stitch_w_cm / g.row_h_cm)), color="帽色", loops="back",
                           finish="缝合两条短边成环；沿长度对折成翻边，先试戴再缝到帽口"),
                     "hat", "肋纹条两短边缝合成环，翻折后分段对齐帽口；先核对实际围度，勿硬拉")
        self.add(hat, "hair_cap", "须在发帽和发束就位后试戴；先检查帽口余量，再决定是否少量缝合固定")

    def garments(self, arm_stitches: int) -> None:
        d, g = self.design, self.gauge
        body = next(p for p in self.components if p.id == "body")
        torso = max(s.stitches for s in body.steps)
        ease = max(2, math.ceil(d.garment_ease_cm / g.stitch_w_cm))
        waist = torso + ease
        for layer in range(d.skirt_layers):
            layer_waist = waist + layer * 2
            rows = max(3, round((d.skirt_length_cm - layer * g.row_h_cm * 2) / g.row_h_cm))
            self.add(skirt(f"skirt_{layer + 1}", "内裙层" if layer == 0 else "外裙层",
                           layer_waist, round(layer_waist * (1.45 + layer * 0.1)), rows, g,
                           color="内裙色" if layer == 0 else "外裙色"),
                     "body", "先试套未装配身体，内层先穿、外层后穿；两层裙腰分别固定，不把裙摆互缝封死")
        total_width = waist
        back_width = max(3, total_width // 2)
        front_width = max(2, math.ceil(total_width / 4))
        panel_rows = max(5, round(d.bodice_length_cm / g.row_h_cm))
        sleeve_n = arm_stitches + ease
        armhole_rows = max(2, round(sleeve_n * g.stitch_w_cm / (2 * g.row_h_cm)))
        if armhole_rows >= panel_rows:
            raise ValueError(f"袖窿需前后各留 {armhole_rows} 行边，但上衣片仅 {panel_rows} 行；"
                             "请增加上衣片长度，或减小掌臂围度后重新生成")
        neck_n = body.steps[-1].stitches
        shoulder = max(1, min(front_width - 1, (back_width - 1) // 2,
                              front_width - math.ceil(neck_n / 4)))
        neck_gap = back_width - shoulder * 2
        open_side = "前" if d.outfit == "jacket_skirt" else "后"
        self.add(panel("garment_back", "整片衣身", "外套后片" if open_side == "前" else "连衣裙前片",
                       back_width, panel_rows, color="上衣色",
                       finish=f"顶部左右外侧各 {shoulder} 针用于肩缝，中央 {neck_gap} 针留领口；"
                              f"两侧从顶端各留 {armhole_rows} 行边作袖窿，其余侧边才缝合"),
                 "body", "衣身在身体上试合围；此处只定位衣物，不把整片贴缝成身体表面")
        self.add(panel("garment_front", f"左右{open_side}开片", "开襟片", front_width, panel_rows,
                       color="上衣色", quantity=2,
                       finish=f"每片顶部外侧 {shoulder} 针作肩缝，内侧 {front_width - shoulder} 针留领口；"
                              "开襟边不与另一片全长缝死"), "garment_back",
                 f"两片分别接在整片两侧，{open_side}面中央留开襟；"
                 f"肩部各对齐 {shoulder} 针缝合，中央 {neck_gap} 针留领口。"
                 f"每个袖窿前后片各留顶部 {armhole_rows} 行边，其下 {panel_rows - armhole_rows} 行边缝合。"
                 "先珠针对位与试合袖筒，再完成侧缝")
        sleeve = RoundBuilder(g, first=sleeve_n)
        sleeve.hold(max(2, round(d.arm_length_cm * 0.7 / g.row_h_cm)), "袖筒")
        sleeve_part = circular("sleeves", "独立袖筒", "衣物袖子", sleeve, color="上衣色", quantity=2,
                               foundation=Foundation(kind="chain_ring", chains=sleeve_n),
                               finish="袖口和袖山两端都开放，不填棉；试穿手掌和前臂后再接到袖窿",
                               fitting=[f"每个袖口 {sleeve_n} 针；须实际检查能否越过 "
                                        f"{arm_stitches} 针的掌/臂最大围",
                                        f"每个袖窿由前后片各 {armhole_rows} 行边构成，"
                                        f"合计 {2 * armhole_rows} 行边；这是长度换算候选，仍须试合"])
        self.add(sleeve_part, "garment_back",
                 f"每个袖筒上口 {sleeve_n} 针对应一个袖窿的 {2 * armhole_rows} 行边，"
                 "先分四等份对齐再分配缝针，不能强按一针对一行缝；袖口不封口")

    def accessories(self) -> None:
        d, g = self.design, self.gauge
        width = max(3, round(d.bag_width_cm / g.stitch_w_cm))
        height = max(3, round(d.bag_height_cm / g.row_h_cm))
        self.add(panel("bag", "包袋主体折片", "包袋", width, height * 2, color="包色",
                       finish="沿行数中线对折，缝合左右两侧，顶端保留袋口，不填棉"),
                 "body", "包袋放在身体侧前方；先确定背带长度和落点，再少量定位，避免遮住全部衣身")
        self.add(panel("bag_flap", "包盖", "包盖", width, max(2, height // 2), color="包色"),
                 "bag", "包盖一条长边接袋口后侧；前侧可留开口或自行选扣件，不能把整个袋口缝死")
        self.add(panel("strap", "包袋背带", "背带", 2,
                       max(4, round(d.strap_length_cm / g.row_h_cm)), color="背带色"),
                 "bag", "两端分别缝到袋口两侧；先跨肩试摆长度，确认后固定两端，勿缝成身体的尾巴")
        if d.flowers:
            centre = RoundBuilder(g)
            self.add(circular("flower_centres", "花片圆心", "贴花", centre, color="花心色", quantity=3,
                              finish="断线留缝合线，不填棉，平放在裙面试摆"),
                     "skirt_2" if d.skirt_layers == 2 else "skirt_1",
                     "三朵花分别试摆在外裙下部，先确认落点再缝")
            petal = RoundBuilder(g, first=4)
            petal.step(8, "花瓣展开")
            self.add(circular("flower_petals", "小花瓣片", "分片贴花", petal, color="花瓣色", quantity=15,
                              finish="不填棉；每 5 片围绕一个花心排列，轻折后缝根部，不封住整片边缘"),
                     "flower_centres", "15 片分为 3 组，每组 5 片围绕一个花心；先试 1 片检查是否形成预期花瓣")


def build_doll_plan(design: DollDesign) -> DollPlan:
    # Revalidate model instances as well as JSON; mutated objects are not trusted exports.
    design = DollDesign.model_validate(design.model_dump())
    builder = _PlanBuilder(design)
    peak, arm_n = builder.body_and_limbs()
    builder.hair_and_hat(peak)
    builder.garments(arm_n)
    builder.accessories()
    return DollPlan(
        design=design, components=builder.components, joins=builder.joins,
        assembly=[
            "先分别用圈钩与片钩做同线同针小样；本稿暂共用输入密度，若两者实测不同，须调整设计后重生成。",
            "先做一只分段手臂、一只鞋底和一根发束，检查掌腕差异、鞋底轮廓及发束垂长，再做对应重复件。",
            "头部先试摆眼位；安全眼在填棉封口前扣好内侧垫片。头部完成后仍先不连接身体。",
            "身体保留颈部开口、暂不填满；先用珠针试合衣片，标出领口、肩缝与袖窿。",
            "衣片只先接肩部外侧，中央留领口；袖窿开口深度先按实际袖筒周长对齐，确认后才缝腋下侧缝。",
            "裙腰先试套未装配身体，内裙后套外裙；过紧须改图重做，不能强拉后仍记为未修改成品。",
            "手臂先穿过对应袖口，确认掌部能通过，再把肩端固定到身体。衣物保留的开襟可用于调整。",
            "分别试穿鞋口与腿段，确认鞋头朝前后再固定；腿部在身体底部用珠针确定间距后缝合。",
            "衣物和四肢试合通过后补足身体与颈部填棉，头底对准颈部缝合；再完成衣物腰部定位。",
            "先缝发帽，再按前额、两侧、后部摆发束；戴上帽子检查头发厚度余量，最后固定帽边。",
            "包袋主体折叠缝两侧，保留袋口，再接包盖与背带；跨肩试摆长度后固定。",
            "最后试摆贴花或其他装饰；记录改过的部件、圈/行、针数和连接位置，再拍摄正面、侧面与背面。",
        ],
        limitations=[
            "这是人工选型与尺寸驱动的钩针结构原型，不是从照片自动识别或恢复的原作图解。",
            "已检查操作式的源针目与产出、起针工作边及装配引用；尚未验证实体可钩性、合身或相似度。",
            "总高与各部件厘米数均为设计目标，量化、填充、缝合和不同钩法可能改变成品尺寸。",
            "手掌暂为无分指轮廓；肋纹、鞋面与花片是钩针近似，未复刻原作的精确纹理或材料。",
            "短针片钩、螺旋圈钩与 BLO 肋纹可能有不同密度；共用输入密度只用于这轮结构草案。",
            "暂无可信的用线、工时或 3D 成形预测；这类原型不能冒充既有 G4 的独立实体证据。",
            "肩缝和袖窿针行位是待试合候选；竖向条纹、复杂花瓣、拇指与扣眼尚未实现。",
        ],
        trial_checkpoints=[
            "头与颈：测头宽、头高、颈围，确认头身连接方向与支撑。",
            "掌腕：测掌部最大宽和腕宽，记录哪一圈形成转折、袖口能否越过手掌。",
            "鞋靴：首圈标鞋头/鞋跟；测鞋底长宽、鞋口周长，核对减针是否确实在鞋头。",
            "头发与帽子：先做一根发束，记录自然垂长；戴帽时包含发帽厚度。",
            "衣物：分别检查领口、开襟、袖窿、袖筒和各层裙腰的实际配合。",
            "整件：与选定参考图并排审查轮廓、比例、服饰层次及配件位置；可钩成功不等于还原成功。",
        ],
    )
