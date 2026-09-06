# 外部校准证据链（图解来源索引）

**简体中文** | [English](SOURCES.en.md)

本系统的领域假设不是拍脑袋定的：每一条例子都来自真实可钩的公开图解，
逐字转录后先做机械代数核对，再落成可运行的测试夹具
（[`tests/test_reference_patterns.py`](../tests/test_reference_patterns.py)，
52 项）。真实图解四度推翻生成器先验，校验器随之修正——每处修正的
证据都在下表。仅取针数代数与圈结构，不复制创作文本（遵循各源版权声明）。

## 校验器演进：四先验修正 + 一规则存活

| # | 规则 | 修正 | 驱动证据 | 夹具 |
|---|------|------|----------|------|
| 1 | 非 6 倍数圈 | 硬错误 → notes | Clover AKIHIRO 22 针腿 / 16 针臂 / 9 针尾 | `test_published_akihiro_*` |
| 2 | 相邻圈跳变 ±6 | 硬错误 → notes（`allow_wide_jump` 白名单保留） | Spin a Yarn 8→16 倍增圈；Ms Premise-Conclusion 理想球体 sin 轮廓 | `test_professional_eight_stitch_ring_start_passes_validation`、`test_ideal_sphere_*` |
| 3 | 同圈加减速混用 | 硬错误 → notes | 紫柚手作垂耳兔眼窝圈 7X,7V,A,7V,7X | `test_cn_rabbit_head_face_shaping_passes` |
| 4 | 加针 ≤ 上圈源针 | 硬错误 → notes | granny 实心款第 2 圈：+16 加进 4 个锁针角空间（12 源针） | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| — | 减针 ≤ 上圈一半 | **保持硬错误**（正面印证） | 小黄人腿 R3：18 针内 sc4tog+4×sc2tog，减针当量 8 ≤ 9，最密真实圈也未越界 | `test_intl_minion_leg_densest_real_decrease_round` |

降级 ≠ 放水：硬错误现在只留"物理不可钩"项；notes 表示"完全可钩但超出
本生成器均匀分组 (aX,V)×n 表达，导出器会跳过该圈"。

## 来源清单

### 官方标准与专业机构

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [Clover 官方 AKIHIRO 玩偶](https://www.clover-mfg.com/en/project/amigurumi-akihiro-crochet-pattern/) | 22 针腿/16 针臂/9 针尾/14 针耳（先验修正 #1）；均匀 +6 头 | `test_published_akihiro_*` |
| [DROPS Design 苹果玩偶 23-60](https://www.garnstudio.com/pattern.php?id=5888&cid=17) | 7 起针对称球、官方密度 18sc/10cm；锁针果柄诚实警告 | `test_published_drops_apple_*` |
| [CYC 纱线重量系统](https://www.craftyarncouncil.com/standards/yarn-weight-system) | gauge 层 cyc_label 七档映射 | `test_gauge.py` |
| [CYC Project Levels](https://www.craftyarncouncil.com/standards/skill-levels) | 难度四级标签对齐 | `test_schemas.py` |
| [CYC 缩写规范](https://www.craftyarncouncil.com/standards/crochet-abbreviations) | CrochetPARADE DSL 令牌一致性 | `test_parade_tokens_align_with_cyc_abbreviations` |
| [Shelley Husband US↔UK 对照](https://shelleyhusbandcrochet.com/uk-and-us-crochet-terms-conversion-help-and-chart/) | 错位一级对照链（sc=dc、hdc=htr、dc=tr、tr=dtr、dtr=ttr）——针法表 UK 列 | `test_height_ladder_us_uk_offset_invariant` |
| [中文图解符号体系（知乎/Reddit 新手指南）](https://zhuanlan.zhihu.com/p/2397749055) | X/T/F/E/V/A 字母记号 ↔ sc/hdc/dc/tr——针法表中文列与符号列 | `tests/test_stitches.py` |
| [cbfiberworks 圈圈针](https://cbfiberworks.com/how-to-make-loop-stitches-for-amigurumi/) / [Yarnhild](https://yarnhild.com/how-to-crochet-the-loop-stitch/) | 纹理针族：环圈成于反面（反过来钩/front-side 变体）、减针挂 4 环并拉过、双圈内卷警告、费线提示 | `test_intl_loop_stitch_texture_rounds_pass`、`test_loop_stitch_family_entries` |
| [AmiguRoom 俄语熊](https://amigurum.ru/2018/04/medvezhonok-amigurumi.html)（Юлия Дейнеги） | 头部 6↔3 等分切换增减两向（与橘子先生互证）、17 圈漂移减针、5 起针尾巴；评论区共识：颈部塞棉紧实 → 组装说明 | `test_intl_ru_deynega_bear_*`、`test_assembly_neck_stuffing_note` |
| [Yarnspirations Red Heart Bear](https://www.yarnspirations.com/products/red-heart-bear-amigurumi)（Sarah Zimmerman） | 北美大厂锚点：10 起针全程合圈、腰身掐细一体件、眼距 = 最大圈/6 精确印证、12mm 眼 @ 23cm、13 sc/10cm 官方密度、脚外撇坐姿支撑 | `test_intl_red_heart_bear_*` |
| [Lion Brand 经典 granny](https://www.lionbrand.com/community/blog/how-to-crochet-a-classic-granny-square/) | 四角拓扑 +12/圈、边圈 76 | `test_intl_lionbrand_classic_granny_passes` |

### 专业设计工作室 / 独立设计师

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [Supergurumi 蜜蜂](https://www.supergurumi.com/amigurumi-crochet-bee-pattern) | 55 圈头身一体 66 峰值、逐圈换色、BLO 脊线、错位增减、33→9→6 奇数收尾；Catania 纱线校准 fine 档米数 | `test_published_bee_*` |
| [AllAboutAmi 大象](https://www.allaboutami.com/elephantpattern/) | 象鼻圆锥 −3/圈；椭圆起链身体/跨部件挑钩超出聚合模型（如实记录不夹注） | `test_intl_elephant_trunk_cone_taper_passes` |
| [StringyDingDing 袋鼠](https://stringydingding.com/kangaroo-amigurumi-free-crochet-pattern/) | 环起后先平钩、一体钩非均匀增减、21/15 奇数圈；**腿部 R5 出版矛盾**（真实印刷错误第二例，校验器正确拦截） | `test_published_kangaroo_*`、`test_validator_catches_published_kangaroo_leg_round5_contradiction` |
| [53stitches 低缝兔](https://53stitches.com/low-sew-bunny-free-crochet-pattern/) | MR 8 起环、泡芙针（5dc popcorn）直接成四肢 | `test_intl_lowsew_bunny_popcorn_limbs` |
| [Tiny Curl Monsieur Bear](https://www.tinycurl.co/monsieur-bear-free-amigurumi-crochet-pattern/) | 显式合圈贝雷帽 "joined rnds, not continuous spiral"、ch-3 计针、MR7 翻面 hdc 耳 | `test_intl_tinycurl_*` |
| [Craftably Ever After 坐姿熊](https://craftablyeverafter.wordpress.com/2022/04/22/patchy-bear-crochet-pattern/) | 锁针并腿身体 R15=36（13sc+2ch+16sc+2sc+3sc 逐字自报）；椭圆起针 [10]；眼位"帽沿上 2 行、间距 2 针" | `test_intl_patchy_bear_chain_joined_body_passes`、`test_intl_snout_oval_start_verbatim` |
| [Squirrel Picnic Motley Bear](https://squirrelpicnic.com/2015/04/24/motley-the-bear-crochet-pattern/) | 合圈与螺旋同件混用、起立锁针不计针、(sc,sk)×6 跳针收口、FLO 颈圈 | `test_intl_squirrelpicnic_motley_joined_muzzle_and_skip_close` |
| [Marching North 实心 granny](https://www.marchingnorth.com/solid-crochet-granny-square-pattern/) | +16/圈、空间加针（先验修正 #4 驱动源） | `test_intl_solid_granny_space_increase_downgraded_to_note` |
| [Chibiscraft 小黄人](https://blog.alwaysfreeamigurumi.com/cute-minion-amigurumi-free-crochet-pattern/) | 最密真实减针圈（规则存活）、鞋底 BLO/FLO 交替、54→9 收尾踩边界、椭圆起针 [12] | `test_intl_minion_*` |
| [Spin a Yarn Rudolph](https://spinayarncrochet.com/rudolph-ornament-free-crochet-pattern/) | 8 起环倍增（先验修正 #2 驱动源） | `test_professional_eight_stitch_ring_start_passes_validation` |
| [Ms Premise-Conclusion 理想球体](https://mspremiseconclusion.wordpress.com/2010/03/14/the-ideal-crochet-sphere/) | sin 轮廓逐圈对照独立重算；工艺警告落实 | `test_ideal_sphere_*` |

### 社区教程与论坛

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [PlanetJune magic ring](https://www.planetjune.com/blog/amigurumi-help/how-to-crochet-a-magic-ring/) | 6 起环 +6 公式口径；无痕收口（front loops 拉紧） | `test_generated_sphere_matches_community_formula` |
| [PlanetJune needlesculpting](https://www.planetjune.com/blog/tutorials/needlesculpting/) | 针塑形（可选组装步骤）：眼窝=横穿头内、两端同孔拉紧打结藏线；隐形走线法（V 形两线间进针）；锚点选择；「内建塑形的图解无需此步」定性 | `test_assembly_optional_needle_sculpting_step` |
| [r/Amigurumi 眼睛 wiki](https://www.reddit.com/r/Amigurumi/wiki/faq_eyeqs/) | 安全眼分档（迷你 5–6 / 常规 8–12 / 大型 14–20+ mm） | `test_crochet_params.py` 眼径梯 |
| [kruchcom.ru 泰迪指偶](https://kruchcom.ru/archives/22215) | 俄语圈 КА/ПРИБ/СБН 逐字——跨语言同一标准 | `test_russian_finger_puppet_rounds_pass_validation` |
| [Lovable Loops 樱桃 C2C](https://lovableloops.com/cherry-square-mini-c2c-crochet-pattern/) | 9×9 逐行色块全文回写 | `test_grid_pipeline_reproduces_published_c2c_chart` |
| [Lovable Loops 心形 C2C](https://lovableloops.com/mini-heart-square-c2c-crochet-pattern/) | 非对称行钉死读取方向（↙正面/↗反面） | `test_grid_written_rows_match_published_heart_chart` |
| [Maclafersa 定型线安全指南](https://maclafersa.com/how-to-add-wire-to-amigurumi-safely-for-posing/) | 端部折环+包裹防戳（胶带单独不可靠）、比量手→肩→手、尾线略短于成品、开口时放入、九大错误清单 | `test_materials_wire_row_for_limbs_only` |
| [Crafty Intentions 线材清单](https://craftyintentions.com/blog/2019/7/8/supplies-wire) | 纸包 18 号 18 英寸花艺线规格锚点（布包同号过软）、纸褶摩擦防移位、防锈 | `test_materials_wire_row_for_limbs_only` |
| [toruyuri 円の増し目の法則](https://toruyuri.com/2020/02/02/wanomashime/) | 日语圈错位加针法则（奇数段段尾/偶数段段中，六角形 vs 圆照片实证）；起针数实验（3 最小、10 露洞）；第 4 套语言 notation（段/目/増し目） | `test_japanese_circle_increase_law_passes`、`test_preamble_mentions_increase_offset_rule` |
| [Zepiany ES-Bee](https://www.zepiany.com/pages/es-bee1) / [Melonchillo 圆环法则](https://melonchillo.com/anillo-magico/) | 第 5 套语言 notation（vuelta/pb/aum）；30 峰对称球；第 3 例出版矛盾（V1 记号 6 vs 正文 8）；针高→起针数法则（短针 6/中长针 8/长针 12）；安全眼 3 岁以下/宠物警示 → 材料行 | `test_intl_zepiany_es_bee_body_and_contradiction`、`test_intl_melonchillo_dc_circle_start_height_law` |

### 国内图解（图片图解，视觉转录）

| 来源 | 印证内容 | 夹具 |
|------|----------|------|
| [紫柚手作·垂耳兔](https://www.bianzhirensheng.com/a/44051_zhifa.html) / [橘子先生](https://www.bianzhirensheng.com/a/44093_zhifa.html) | 面部塑形混用加减速（先验修正 #3 驱动源）、M 三并一、平织椭圆耳、3 等分帽子 +3/圈、7 起针头套、减到奇数 7 的脚 | `test_cn_tuanzi_*`、`test_cn_rabbit_*`、`test_cn_orange_*` |
| [骨头团子](https://www.bianzhirensheng.com/a/44074_zhifa.html) / [软糖系列](https://www.bianzhirensheng.com/a/44140_zhifa.html) | 对称节奏、倍增圈（8→16）如实降提示、枣形针 B 中性语义 + 图例 | `test_cn_bone_doubling_round_passes_with_note`、`test_cn_gummy_*` |
| [晴一手作·小兔叽妹妹](https://www.bianzhirensheng.com/a/43996_zhifa.html)（小红书原生） | 背带裤两腿并钩 24+24→48、胡萝卜先减后增收肩、5 起环奇数收口 | `test_cn_overalls_two_leg_join_passes`、`test_cn_carrot_*` |

## 抓取方法与诚实记录

- **逐字全文**：web 抓取 HTML 后只取圈行文本，机械核对每圈
  `st = prev + inc − dec` 后落夹具——四次转录错误全被校验器当场
  拦截（蜜蜂 R6、胡萝卜 R3、低缝兔省略行、软糖），夹具即勘误记录。
- **图片图解（国内主流形态）**：编辑器视觉识图逐圈转录，同样过校验器。
- **可达性欠账**（未能核验，如实记录）：Etsy 403、Ravelry 登录墙、
  小红书登录墙 + 图片图解、编织人生分享平台 502、部分论坛私密版块、
  Raffamusa 403、Hobbii PDF 无法直取、Ami Amour 404、Supergurumi
  /patterns 索引 404。这些来源未入夹具，未来若可达再补。
