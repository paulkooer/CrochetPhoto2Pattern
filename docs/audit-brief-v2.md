# CrochetPhoto2Pattern 审核任务书 v2（第二次全面深审）

> 本文件是 v2 版审查任务书。v1（`audit-brief.md`，2026-08-29 早版）的
> §6 发现（F13–F22）已全部处置并记入 `handoff-review.md` §22；本轮是
> **第二次全面深审**，重点是 v1 未覆盖的面、其后新增的 ~2,400 行代码、
> 以及**跨功能交互面**。v1 仍可作为背景阅读，但与代码冲突处以代码和
> 本文件为准。

---

## 0. 角色与产出要求

**角色**：严苛但公正的资深审查者，执行第 16 轮后的第二次全面深审。
此前系统已经过：fable5 两轮、本仓自审数轮、Opus 5 两轮（审查+优化）
——**低垂果实已被摘尽**。本轮价值在于：更深的交互面、更刁钻的输入、
以及前几轮没有的代码。

**产出格式（对每条发现，与 v1 §0 相同）**：

```
[严重度] 编号 — 一句话标题
位置: 文件:行号（精确到行）
类别: bug | 领域错误 | 安全面 | 性能 | 可维护性 | 文档失实
证据: 复现脚本（可直接运行）或逐行推理链；禁止推测
影响: 用户可见的行为
建议: 具体修法
```

**硬性纪律**：

1. 先复现再上报；写不出复现脚本或完整推理链的发现不提交。
2. 先读 §6（刻意设计清单）与 §8（历史误报清单）——16 轮里约 1/3 的
   外部发现是误报。
3. 区分三档：bug / 取舍 / 增强。
4. 严重度：blocker / high / medium / low。
5. 本轮特别要求：**至少一半的发现应来自"交互面"或"对抗输入"**
   （§5.B/§5.C），单函数内部逻辑已被 585 条测试与三轮 AI 审查覆盖，
   重复扫同一层面边际收益极低。

## 1. 系统一句话定位

照片 → Amigurumi 钩织图解生成器。双解析路径（AI 严格结构化输出 /
本地免费管线）+ 手动输入 + 2D 网格。输出：逐圈 X/V/A 图解（含日式↔CYC
双语对照）、逐圈配色、逐色材料（克重/米数/品牌色号）、自检徽章、环形
图+符号条、轮廓验证 SVG、进度勾选、快速调尺寸、JSON 修正、SQLite
历史（缩略图/命名/搜索）、备份导入、分享链接、Markdown/PDF 导出、
CLI 无头模式（单图+目录批量并发）。Streamlit GUI + CLI 双形态。

## 2. 当前基线（先跑通再开始）

```bash
cd CrochetPhoto2Pattern
.venv/bin/python -m pytest -q --cov=app     # 585 passed + 1 skipped（CROCHET_EVAL_DIR 评测脚手架）
.venv/bin/python -m ruff check app tests    # 零告警
VIRTUAL_ENV=.venv uv build --wheel -o /tmp/w . && rm -rf build
.venv/bin/python -m app.cli --head 9 --height 18 --out /tmp/t.json --quiet
.venv/bin/python -m streamlit run app/main.py
```

环境事实：Python 3.9.6（`.venv`，uv 管理）；**requires-python = ">=3.9"**
——U32 升 3.11 曾尝试并回滚（zip strict= 是 3.10+ 特性，3.9 运行时不
支持；完整方案见 handoff §23，待 3.11 环境专项）。可选依赖：reportlab
已装；mediapipe 未装（[pose] 路径全部走回退）。平台 macOS arm64；
CI：ci.yml（py3.9–3.12 矩阵）+ extras.yml（[pdf]/[pose] 金丝雀）。

## 3. 模块地图（行数 ≈ 审查优先级；★ 为本轮新深审重点）

| 模块 | 行数 | 职责 | 优先级 |
|---|---|---|---|
| `models/crochet_params.py` | 881 | 领域核心：全形状圈数代数、bridge_rounds、estimate_minutes（校准模型）、语义配色、材料/装配派生、生成门禁 | ★★★ |
| `ui/result_renderer.py` | 545+ | 结果页状态机 + 新增：快速调尺寸（透传 style/gauge/color_bands/spans）、逐色材料色样、自检徽章、环形图/符号条、分享链接、历史命名 | ★★★ |
| `models/image_parser.py` | 434 | Vision 双路径（strict parse+重试+legacy 回退）、中转站、**异常全层脱敏**、色板直量化 | ★★★ |
| `models/validator.py` | ~90 | 代数自洽 + **物理边界（allow_wide_jump 白名单）** | ★★★ |
| `models/subject.py` | 209 | GrabCut（三档种子/Otsu 钳位/FGD 下限 144/腐蚀/退化回退） | ★★ |
| `models/pose.py` | 206 | 姿态实测 span（可选 [pose]）、模型 SHA256、span hints 进 prompt | ★★ |
| `models/ring_chart.py` | 195 | 环形图（真实半径/只标变化圈）+ 符号条 | ★★ |
| `models/colors.py` | 238 | CIEDE2000（标量+**向量化**，34 组官方数据锁定）、pick_yarn_palette、MST 色表、品牌色号 | ★★ |
| `utils/history.py` | ~140 | SQLite（preview/title 列、幂等迁移、校验、搜索） | ★★ |
| `utils/share.py` | ~60 | 分享 token（九键同构/zlib+base64url/6000 门控） | ★★ |
| `cli.py` | 157+ | 单图/手动/Mock/目录批量**并发**（每图独立 orchestrator） | ★★ |
| `models/local_vision.py` | 201 | 人脸/比例/剖面/flare | ★ |
| `models/profile_shaping.py` | 199 | 剖面→筒壁、strip_dome、侧影 SVG | ★ |
| `models/color_design.py` | 199 | 色带（掩码驱动/空带延续） | ★ |
| `models/gauge.py` | 144 | 密度单一来源（米数为经验估算——V6 后如实署名） | ★ |
| `utils/pdf_export.py` | 135 | PDF（全文 esc 转义、CID 字体、密度行） | ★ |
| `ui/*` 其余 + `utils/images.py` | ~500 | 侧栏/Tab/上传（EXIF+白底合成+缓存） | ★ |

## 4. 本轮深审重点（按此投入精力）

### A. 跨功能交互面（前两轮审查最少覆盖的部分）
- **分享链接 × 全部下游**：token 含九键 → 载入 → 快速调尺寸（style
  恢复？spans 恢复？）→ 存入历史（title/preview 占位）→ 再次分享
  （二级 token 是否保真？多轮分享-载入-分享循环有无信息衰减？）。
- **历史 × 结果页**：旧 schema 库迁移（无 preview/title 列）→ 载入 →
  勾选进度 → JSON 修正 → 再存入（title 保留还是丢失？）。
- **CLI 批量 × 自检门禁 × 并发**：批量中一张图触发 PatternGenerationError
  时其余图片是否继续？并发下 stderr 输出交错是否掩盖失败？每图独立
  orchestrator 是否真的隔离了 parser 实例状态？
- **validator 白名单 × JSON 修正**：用户手改 JSON 把 allow_wide_jump
  设为 true 并放大跳变——门禁会放行吗？（这是显式机制被滥用的通道）
- **快速调尺寸 × 一体件 × 波浪摆 × pose spans**：这些选项叠加时
  spans（来自旧照片）对新生成的部件是否仍然成立？

### B. 对抗输入（构造刁钻但合法的输入）
- JSON 修正框：负数针数（schema 拦？）、`allow_wide_jump: true` 滥用、
  超长 notes（5MB 字符串）、Unicode 零宽字符/RTL 覆盖符进 notes/色名、
  parts 数组里 1 万个部件。
- 分享 token：手工构造的 zlib 炸弹（解压后 100MB）、嵌套极深的
  structure、params.parts 含循环引用的 JSON（encode 端 default=str
  的行为）。
- 历史 DB：手改 blob 为非法 JSON、title 含 SQL 通配符（`%`/`_` 进
  LIKE 模式——搜索功能的行为）。
- 图片：极端宽高比（1×10000）、全透明、16-bit PNG、CMYK JPEG、
  巨大 EXIF、损坏的 ICC profile。

### C. 领域正确性的新面
- estimate_minutes 校准模型（6.5s/针 + 10s/圈）：极端输入下的下限
  30 分钟是否合理（单部件 2 圈的 4cm 玩偶）？
- 帽子侧壁 max(3, 0.6·直径)——20cm 头径时侧壁 12 圈 ≈ 7.5cm，
  帽子总高（含帽顶）是否仍合理？
- 一体件 strip_dome 口径：非 ladder 球（egg/ideal）+ 一体时 head_kept
  截断的圈号语义。
- 波浪摆 allow_wide_jump：只豁免 |Δ|≤6，但"每针放 2 针"的针数
  （hem_st*2）本身是否该有上界？

### D. 安全面
- 异常脱敏（F14）覆盖面：CLI 的 stderr、批量模式异常、share 解码
  异常是否也过 _sanitize？
- 分享 token 无签名——用户可手改 token 内容（zlib 可编辑）载入任意
  JSON：评估风险等级（本地工具 vs 数据完整性）。
- PDF：`<font>`/`<img>` 标签转义后的残余面；文件名注入
  （download_button file_name 恒定，确认无用户输入进文件名）。

### E. 测试真实性
- fake SDK 的 message.parsed/refusal 形状 vs 真实 openai 2.48。
- 评测脚手架（CROCHET_EVAL_DIR）从未真实运行——manifest 契约本身
  是否自洽？
- 264+48 组矩阵与 hypothesis 的域是否仍有未覆盖组合（本报告 §6）。

## 5. 发现清单（第二次全面深审 · Opus 5 · 2026-08-29）

### 5.0 基线复现结果（先说与 §2 不符的地方）

```
.venv/bin/python -m pytest -q
→ 1 failed, 584 passed, 1 skipped        （§2 声称 585 passed + 1 skipped）
FAILED tests/test_round14.py::test_cli_batch_directory - assert 1 == 0

OPENAI_API_KEY= ANTHROPIC_API_KEY= .venv/bin/python -m pytest -q
→ 585 passed, 1 skipped                  ✅ 与 §2 一致
```

`ruff check` 零告警、`uv build --wheel`、`app.cli --head 9 --height 18`
三项均与 §2 一致。基线差异的根因是 **F33**（测试套件非 hermetic）。

**分档统计**：14 条 bug + 3 条取舍 + 4 条增强（取舍/增强见 §5.E）。

| 严重度 | 条数 | 编号 |
|---|---|---|
| blocker | 0 | — |
| high | 4 | F23 F24 F28 F33 |
| medium | 3 | F25 F27 F36 |
| low | 7 | F26 F29 F30 F31 F32 F34 F35 |

**区域分布（§0.5 硬性要求：≥50% 来自交互面/对抗输入）**

| 区域 | 条数 | 占比 |
|---|---|---|
| §4.A 跨功能交互面 | 5（F23–F27） | 36% |
| §4.B 对抗输入 | 4（F28–F31） | 29% |
| §4.C 领域正确性新面 | 1（F36） | 7% |
| §4.D 安全面 | 1（F32） | 7% |
| §4.E 测试真实性 | 3（F33–F35） | 21% |
| **A+B 合计** | **9 / 14** | **64% ✅** |

§4.C 只出 1 条（F36，且是"两套口径打架"而非算错）——1800 组塑形矩阵零异常零
自检失败，印证了 §0「单函数内部逻辑已被覆盖」的判断。查过但确认**无问题**的
面见 §5.F 负面结果。

---

### 5.A 跨功能交互面（§4.A）

```
[high] F23 — 分享链接只有「收」没有「发」：encode_result 是死代码，UI 无任何生成入口
```

**位置**: `app/utils/share.py:24`（`encode_result` 定义）· `app/ui/result_renderer.py:449-546`（结果页全部按钮，无一处调用）· `README.md:23`（对外宣称已交付）

**类别**: bug（功能缺失）+ 文档失实

**证据**:

```bash
# 1) 全仓库只有测试调用 encode_result，产品代码零调用
grep -rn "encode_result" . --exclude-dir=.venv --exclude-dir=.git --exclude-dir=.codegraph
#   app/utils/share.py:24:def encode_result(...)      ← 定义
#   tests/test_round14.py:62,74,89,103               ← 只有测试

# 2) 端到端：把结果页完整渲染出来，枚举所有 widget，没有任何分享入口
.venv/bin/python - <<'PY'
import os, sys, tempfile
os.environ['CROCHET_HISTORY_DB'] = os.path.join(tempfile.mkdtemp(), 'h.db')
sys.path.insert(0, '.')
from streamlit.testing.v1 import AppTest
from tests.test_app_smoke import _mock_result
from app.utils.share import encode_result
at = AppTest.from_file('app/main.py', default_timeout=60)
at.query_params['p'] = encode_result(_mock_result('share-x'))   # 只能靠测试自己造 token
at.run()
ks = [w.key for w in list(at.button) + list(at.text_area) + list(at.text_input)]
print('载入成功:', 'result' in at.session_state)
print('含 share 的 widget:', [k for k in ks if k and 'share' in k.lower()] or '【无】')
print('按钮文案含「分享」:', [b.label for b in at.button if '分享' in b.label] or '【无】')
print('页面文本出现 ?p= :', '?p=' in ' '.join(m.value for m in at.markdown))
PY
```

实测输出：

```
载入成功: True
含 share 的 widget: 【无】
按钮文案含「分享」: 【无】
页面文本出现 ?p= : False
```

`main.py:30-51` 的**接收**侧完整可用（decode + `_validated_backup` + uuid rid），
`_WIDGET_KEY_PREFIXES`（`result_renderer.py:21-25`）里也没有任何 `share_` 前缀
——说明分享按钮**从未被写进结果页**，不是后来被删掉的。

**影响**: 用户永远无法产生分享链接。`README.md:23`「🔗 分享链接：小图解可压缩进
URL 直接打开」是空承诺；`docs/optimization-brief.md:127`「接收方打开后能否另存到
我的历史」讨论的是一条无人能进入的流程。§4.A 第一条要求审的「多轮分享-载入-分享
循环」在产品上根本不存在（我只能在库层面验证，见 §5.F-1）。

**建议**: `result_renderer.py` 的备份/导出区（现 `col_bk1`–`col_bk3` 一带）加第
四个入口：

```python
from app.utils.share import encode_result
_tok = encode_result(result)          # 传完整 result，九键才齐
if _tok:
    st.code(f"?p={_tok}", language="")        # 用户复制拼到自己的部署域名后
    st.caption(f"分享链接 {len(_tok)}/6000 字符")
else:
    st.caption("图解过大（>6000 字符），请用「💾 备份完整结果」文件分享")
```

并把新 key（如 `share_`）加进 `_WIDGET_KEY_PREFIXES`。若判定该特性暂不交付，
则必须同步删掉 `README.md:23` 与 `share.py` 的 encode 半边，别留半成品。

---

```
[high] F24 — 备份 JSON 只存三键：导入后「快速调尺寸」把一体件静默拆回分件、egg 球退化成 ladder
```

**位置**: `app/ui/result_renderer.py:477-480`（备份只写 3 键）· `:538-543`（导入只回填 4 键）· `:396-412`（调尺寸读 `result["style"]`，读不到就用 `_st_def` 默认）

**类别**: bug（领域错误，静默）

**证据**（`share.py:17-21` 的 V4 注释明确写了这个风险——"缺 style/spans 会让接收方
快速调整尺寸行为漂移（egg→ladder、配色回退先验）"——分享 token 修了九键，
**备份下载/导入这条同源路径没修**）：

```bash
.venv/bin/python - <<'PY'
import json, sys; sys.path.insert(0, '.')
from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis
from app.ui.result_renderer import _rebuild_params, _validated_backup

a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                  main_features=[], pose="站立", difficulty="easy",
                  parts=["头部", "身体", "腿部"])
s = StructureDesigner.design_3d_structure(a)
g, style = Gauge(20.0, 24.0), ShapingStyle("egg", True, "attached", True)
params = CrochetParamsGenerator.generate_params(a, s, gauge=g, style=style)
print("① 生成（蛋形头+头身一体+波浪摆）部件 =", [p.name for p in params["parts"]])

# ── result_renderer.py:477-480 原样：备份只写 analysis/structure/params ──
sp = json.loads(json.dumps(params, default=lambda o: o.model_dump(), ensure_ascii=False))
backup = json.dumps({"analysis": a.model_dump(), "structure": s, "params": sp})
print("② 备份文件顶层键 =", sorted(json.loads(backup)))

# ── result_renderer.py:530-543 原样：导入只回填 4 键 ──
d = json.loads(backup)
an, stc = _validated_backup(d)
imported = {"analysis": an, "structure": stc,
            "params": _rebuild_params(dict(d["params"])), "result_id": "imp1"}

# ── result_renderer.py:396-412 原样：快速调尺寸 ──
_st_def = {"sphere_mode": "ladder", "one_piece": False,
           "skirt_style": "ring", "ruffle_hem": False}
_style = ShapingStyle(**{**_st_def, **(imported.get("style") or {})})
_na = ImageAnalysis(**{**imported["analysis"], "head_diameter_cm": 10.0})
_ns = StructureDesigner.design_3d_structure(_na)
_gd = imported.get("gauge") or sp.get("gauge")      # gauge 靠 params 那份幸存
_np = CrochetParamsGenerator.generate_params(
    _na, _ns, color_bands=imported.get("color_bands"),
    gauge=Gauge(_gd["stitches_per_10cm"], _gd["rows_per_10cm"]),
    style=_style, spans=imported.get("spans"))
print("③ 调尺寸后 style =", _style)
print("③ 调尺寸后部件 =", [p.name for p in _np["parts"]])
assert _style.sphere_mode == "egg", f"❌ egg → {_style.sphere_mode}"
PY
```

实测输出：

```
① 生成（蛋形头+头身一体+波浪摆）部件 = ['头身（一体）', '腿部']
② 备份文件顶层键 = ['analysis', 'params', 'structure']
③ 调尺寸后 style = ShapingStyle(sphere_mode='ladder', one_piece=False,
                                skirt_style='ring', ruffle_hem=False)
③ 调尺寸后部件 = ['头部', '身体', '腿部']
AssertionError: ❌ egg → ladder
```

丢失键清单（`grep -n` 对比 `orchestrator.py:134-158` 与 `result_renderer.py:477-480`）：
`style`、`color_bands`、`spans`、`spans_measured`、`vision_meta`、`preview`。
`gauge` 是唯一幸存的——因为它另有一份随 `params` 序列化（`crochet_params.py:897`）。

**影响**: 用户备份 → 换会话导入 → 点「📐 按新尺寸重新生成」，得到的图解**默默换了
工艺**：免缝合的一体件变回要缝头的两件、蛋形头变阶梯球、波浪裙摆消失、照片配色
退回先验色带、实测分段失效。全程无任何提示，用户只会以为"尺寸改了"。这是照
着钩出来才会发现的错误。

**建议**: 备份与 token 走同一个键集常量——把 `share.py:20` 的 `_SHARE_KEYS` 提升为
共用定义（加 `preview` 后作为"备份键集"，token 侧仍排除 `preview`）：

```python
# share.py
_BACKUP_KEYS = ("analysis", "structure", "params", "style", "gauge",
                "color_bands", "spans", "spans_measured", "vision_meta")
_SHARE_KEYS = _BACKUP_KEYS            # token 侧不含 preview，保持 6000 门控

# result_renderer.py:477
backup_json = json.dumps({k: (serializable_params if k == "params" else result.get(k))
                          for k in _BACKUP_KEYS}, ensure_ascii=False)
# result_renderer.py:538 导入侧同样按 _BACKUP_KEYS 回填（缺键给默认值，兼容旧备份）
```

回归测试建议直接断言"备份键集 == `_SHARE_KEYS`"，把这类漂移钉死在结构层。

---

```
[medium] F25 — 历史命名往返即丢：载入后再「存入历史」，title 被 NULL 覆盖
```

**位置**: `app/ui/result_renderer.py:512-513`（`hist_title_` 输入框载入时不回填）· `:519-522`（空串 → `None`）· `app/utils/history.py:90-94`（`INSERT OR REPLACE` 整行覆盖）

**类别**: bug

**证据**:

```bash
.venv/bin/python - <<'PY'
import os, sys, tempfile
os.environ["CROCHET_HISTORY_DB"] = os.path.join(tempfile.mkdtemp(), "h.db")
sys.path.insert(0, '.')
from app.utils import history
BASE = {"result_id": "rid-aaa",
        "analysis": {"body_type": "标准", "head_diameter_cm": 9.0, "height_cm": 18.0,
                     "main_features": [], "pose": "站立", "difficulty": "easy",
                     "parts": ["头部"]},
        "structure": {"parts": [{"name": "头部", "shape": "sphere"}]},
        "params": {"parts": [{"name": "头部", "type": "sphere", "color": "白色",
                              "rounds": [{"row": 1, "stitches": 6}]}]}}
history.save_result(dict(BASE), title="小熊·第三版")
print("① 命名存入      :", repr(history.list_results()[0]["title"]))
loaded = history.load_result("rid-aaa")            # 侧栏「载入」sidebar.py:135
print("② blob 里有 title:", "title" in loaded)     # title 是列，不在 blob 里
history.save_result(loaded, title=("" or "").strip() or None)   # 再点「存入历史」
print("③ 再存入后 title :", repr(history.list_results()[0]["title"]))
PY
```

实测输出：

```
① 命名存入      : '小熊·第三版'
② blob 里有 title: False
③ 再存入后 title : None
```

推理链：`title` 存在 `patterns.title` **列**里，不在 `blob` 内（`history.py:90-94`）。
`load_result` 只 `SELECT blob`（`:129-133`），所以 title 不随载入回到 session。
结果页的 `hist_title_{rid}` 输入框（`:512`）初值为空，`:520-521` 取到空串 →
`or None` → `save_result(title=None)` → `INSERT OR REPLACE` 把该行 title 写成 NULL。
`rid` 在载入时被 `sidebar.py:154` `setdefault` 保留为原 rid，所以命中的是**同一行**。

**影响**: 用户给图解起的名字，在"载回来 → 勾几圈进度 → 再存一次"之后消失，侧栏
退回 `_summary()` 的「标准 · 头9.0cm · 高18.0cm · 1 部件」——多份同尺寸玩偶从此无法
区分。§4.A 问的"title 保留还是丢失"，答案是**丢失**。

**建议**: 两处任一即可，建议都做。（a）`load_result` 一并取回 title 并写入 result：

```python
row = conn.execute("SELECT blob, title FROM patterns WHERE rid = ?", (rid,)).fetchone()
data = json.loads(row[0])
if row[1]:
    data["title"] = row[1]
return data
```

配合 `result_renderer.py:512` 用 `value=result.get("title", "")` 回填输入框。
（b）`save_result` 的 title 改为"None 表示不动"语义：

```python
if title is None:      # 只更新 blob/summary，保留原 title
    conn.execute("INSERT INTO patterns(...) VALUES(...) "
                 "ON CONFLICT(rid) DO UPDATE SET created_at=?, summary=?, "
                 "blob=?, preview=?", ...)
```

---

```
[low] F26 — 「快速调尺寸」丢掉 preview：调完尺寸再存历史，缩略图变成占位符
```

**位置**: `app/ui/result_renderer.py:416-428`（写回 11 键，独缺 `preview`）· 对照 `app/models/orchestrator.py:134-158`（产出 11 个顶层键，含 `preview`）

**类别**: bug

**证据**（键集对差，可脚本化验证）：

```bash
.venv/bin/python - <<'PY'
import re
orch = open('app/models/orchestrator.py').read().split('return {')[-1]
orch_keys = set(re.findall(r'^\s{12}"(\w+)":', orch, re.M))
# result_renderer.py:416-428 的字面键集
resize_keys = {"analysis","structure","params","result_id","usage","vision_meta",
               "gauge","style","color_bands","spans","spans_measured"}
print("orchestrator 顶层键:", sorted(orch_keys))
print("调尺寸写回键      :", sorted(resize_keys))
print("❌ 调尺寸后丢失   :", sorted(orch_keys - resize_keys))
PY
```

实测输出：`❌ 调尺寸后丢失 : ['preview']`

链路：照片路径生成 → `orchestrator.py:152` 带 96px 缩略图 → 用户点「📐 按新尺寸
重新生成」→ `result_renderer.py:416` 新建的 result 无 `preview` → 「🗂 存入历史」→
`history.py:87` 取到 `None` → 侧栏走 `sidebar.py:127-131` 的 🧶 虚线占位框。

**影响**: 侧栏「我的图解」列表里，凡是调过尺寸的记录都没有照片缩略图，只有占位
方块；同尺寸的几条记录在视觉上无法区分（叠加 F25 的 title 丢失后更严重）。
§4.A 问的"preview 占位"，答案是：**分享/导入路径没有 preview 是刻意设计（§6），
但调尺寸路径丢 preview 是 bug**。

**建议**: `result_renderer.py:416-428` 的字典补一行 `"preview": result.get("preview")`。
根治方式同 F24——用共用键集常量构造，避免逐处手抄漏项。

---

```
[medium] F27 — CLI 批量按 stem 组输出名：doll.png 与 doll.jpg 并发互相覆盖，仍报「2/2」+ rc=0
```

**位置**: `app/cli.py:140-141`（`f"{img.stem}.json"` / `.md`）· `:150-151`（`ThreadPoolExecutor` 并发）· `:158-159`（成功计数与返回码）

**类别**: bug（静默数据丢失）

**证据**:

```bash
.venv/bin/python - <<'PY'
import json, os, sys, tempfile
os.environ.pop("OPENAI_API_KEY", None); os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, '.')
from PIL import Image, ImageDraw
from app import cli
d = tempfile.mkdtemp(); in_dir = os.path.join(d, "in"); out_dir = os.path.join(d, "out")
os.makedirs(in_dir)
for ext, size, color in (("png", (100, 300), (0, 120, 215)),
                         ("jpg", (100, 120), (220, 50, 50))):
    img = Image.new("RGB", size, (245, 245, 245)); dr = ImageDraw.Draw(img)
    dr.ellipse([30, 12, 70, 52], fill=(230, 180, 150))
    dr.rounded_rectangle([35, 55, 65, size[1] - 10], radius=8, fill=color)
    img.save(os.path.join(in_dir, f"doll.{ext}"))       # stem 相同
print("输入:", sorted(os.listdir(in_dir)))
print("rc =", cli.main(["--batch-dir", in_dir, "--out-dir", out_dir, "--local", "--quiet"]))
print("输出:", sorted(os.listdir(out_dir)))
PY
```

实测输出：

```
✅ doll.jpg
✅ doll.png
批量完成 2/2
输入: ['doll.jpg', 'doll.png']
rc = 0
输出: ['doll.json', 'doll.md']       ← 2 进 1 出
```

两个 worker 拿到同一个 `out` 路径，`main()` 里 `Path(args.out).write_text(...)`
（`cli.py:185`）并发写同一文件：后完成者整体覆盖前者（`write_text` 不是原子，
极端时序下还可能得到截断/混合内容）。`ok` 计数按 `rc==0` 累加，两者都成功，
所以 `批量完成 2/2` + `rc=0`——CI/脚本层完全看不出丢了一份图解。

§4.A 另两问的答案（这部分**没有**问题，见 §5.F-2）：一张图失败其余继续 ✅；
每图独立 orchestrator 确实隔离了 parser 实例状态 ✅。

**附带（同一处，low）**: `cli.py:142` 硬置 `"pdf": None`，`--batch-dir` 与 `--pdf`
同时给出时 PDF 被静默丢弃，无警告——实测 `产出 PDF 文件: []` 而 `rc=0`。

**建议**: 输出名带上扩展名消歧，并在撞名时显式报错而不是静默覆盖：

```python
def _one(img):
    stem = img.stem if len(stems[img.stem]) == 1 else f"{img.stem}_{img.suffix[1:]}"
    ns = argparse.Namespace(**{**vars(args), "image": str(img),
                               "out": str(out_dir / f"{stem}.json"),
                               "md": str(out_dir / f"{stem}.md"),
                               "pdf": None, "batch_dir": None})
```

其中 `stems` 在 `images` 求出后预先分组（`collections.defaultdict(list)`）。
另建议 `--pdf` 在批量模式下按 `{stem}.pdf` 逐图导出，或在 `run_batch` 入口
`print("--pdf 在批量模式下不支持，已忽略", file=sys.stderr)`。

---

### 5.B 对抗输入（§4.B）

```
[high] F28 — 2D 网格行数由宽高比推导且无上界：一张 1×10000 的图吃掉 4.5GB 内存并把 2.2GB SVG 塞进 session_state
```

**位置**: `app/models/grid_pattern.py:68`（`grid_height` 推导，只有下界 `max(2, …)`，无上界）· `app/ui/tab_grid.py:70-85`（生成后把 svg/chart/c2c 四份字符串一起写进 `st.session_state.grid_view`）

**类别**: bug（性能 / 可用性 · 单次上传即可打死进程）

**证据**（§4.B 点名的"极端宽高比（1×10000）"——这是四类对抗图片里**唯一**真的出事的）：

```bash
.venv/bin/python - <<'PY'
import resource, signal, sys, time; sys.path.insert(0, '.')
from PIL import Image
from app.models.grid_pattern import generate_grid_pattern, render_svg
print("grid_height = max(2, int(grid_width * H/W * aspect + 0.5))   ← 无上界")
for w, h, gw in [(200, 300, 40), (1, 10000, 40), (1, 10000, 80)]:
    gh = max(2, int(gw * h / w * 0.75 + 0.5))
    print(f"  源图 {w:>6}x{h:<6} 网格宽 {gw:>3} → 行数 {gh:>9,}  单元 {gw*gh:>12,}")
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError(">120s")))
signal.alarm(120)
t0 = time.time()
p = generate_grid_pattern(Image.new("RGB", (1, 10000), (200, 150, 120)), grid_width=40)
print(f"\n生成 {p.width}x{p.height} 用时 {time.time()-t0:.1f}s "
      f"峰值RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e6:.0f}MB")
signal.alarm(120); t0 = time.time(); s = render_svg(p)
print(f"render_svg → {len(s)/1e6:.0f}MB 字符串，用时 {time.time()-t0:.1f}s")
PY
```

实测输出（macOS arm64 / py3.9.6）：

```
grid_height = max(2, int(grid_width * H/W * aspect + 0.5))   ← 无上界
  源图    200x300    网格宽  40 → 行数        45  单元        1,800
  源图      1x10000  网格宽  40 → 行数   300,000  单元   12,000,000
  源图      1x10000  网格宽  80 → 行数   600,000  单元   48,000,000

生成 40x300000 用时 31.5s 峰值RSS 4563MB
render_svg → 2211MB 字符串，用时 40.7s
```

放大链条（`tab_grid.py:35` 的滑块上限 80 时再 ×4，48M 单元 ≈ 18GB）：

1. `grid_pattern.py:68` 行数 = 40 × (10000/1) × 0.75 = **300,000 行**；
2. `:82-98` 对 1200 万像素跑 `_srgb_to_lab_vec` + `ciede2000_vec`（`(1.2e7, n_colors)` 的 float 距离矩阵）→ 4.5GB；
3. `:98-101` 生成 1200 万个 `GridCell` dataclass 实例；
4. `tab_grid.py:80-84` **四份**渲染字符串（`svg` 2.2GB + `chart` + `c2c` + 两份图例）一起存进 `st.session_state.grid_view`——**session 级驻留，不随 rerun 释放**；
5. `tab_grid.py:97` `components.html(2.2GB)` 与 `:112-117` `download_button(2.2GB)` 再各自复制一份。

`utils/images.py` 的两道防线都拦不住：`MAX_UPLOAD_MB=20` 只看**文件字节数**
（1×10000 的 PNG 只有几 KB），PIL 的 `MAX_IMAGE_PIXELS` 只看**总像素**
（10000 像素远低于阈值）。失控量来自**宽高比**，现有代码没有任何地方检查它。

**影响**: 用户在「📹 2D 像素网格」Tab 上传一张细长图（截图长条、拼接长图、
误传的进度条截图都是这个形状），Streamlit 进程内存冲到数 GB 后被 OOM
killer 杀掉或把机器拖进 swap；即使侥幸生成完，浏览器也会被 2.2GB 的
`components.html` 打死。§7 把"多人共享部署"列为已知场景（`sidebar.py:102`
提醒勿在共享部署输入 Key），在那种部署下这是一次上传即可完成的 DoS。

**建议**: 在推导处直接钳住行数，并让 UI 诚实告知被钳制：

```python
# grid_pattern.py:68 —— 单元总数上界（8 万格 ≈ 80 列 × 1000 行，已远超实用图案）
_MAX_CELLS = 80_000
grid_height = max(2, int(grid_width * orig_h / orig_w * aspect_ratio + 0.5))
clamped = min(grid_height, max(2, _MAX_CELLS // grid_width))
```

`GridPattern` 增一个 `clamped_from: Optional[int]` 字段，`tab_grid.py:89` 的
`st.success` 里追加"（原始比例需 300,000 行，已钳至 1,000 行——请先裁剪图片）"。
这比静默截断可靠，也比在 UI 层加"图片太长"的硬拒绝更符合"尽力生成"的产品语义。

---

```
[low] F29 — 分享 token 只在 encode 端有 6000 门控，decode 端无长度/解压上限（zlib 放大 ~770×）
```

**位置**: `app/utils/share.py:31-33`（`_MAX_TOKEN_CHARS` 只用于 encode）· `:39`（`zlib.decompress` 无 `max_length`，`base64.urlsafe_b64decode` 无长度检查）· `app/main.py:35`（`decode_result(_qp["p"])` 是入口）

**类别**: 安全面（DoS 面）

**证据**（§4.B 点名的"手工构造的 zlib 炸弹"）：

```bash
.venv/bin/python - <<'PY'
import base64, sys, time, zlib; sys.path.insert(0, '.')
from app.utils.share import _MAX_TOKEN_CHARS, decode_result
print("encode 端门控 =", _MAX_TOKEN_CHARS, "字符 / decode 端门控 = 无")
for tok_chars in (6000, 32768):                 # 6000=自家门限，32768≈浏览器地址栏上限
    pad = "A" * (tok_chars * 3 // 4 * 1000)
    payload = '{"analysis":{},"structure":{},"params":{"pad":"' + pad + '"}}'
    tok = base64.urlsafe_b64encode(zlib.compress(payload.encode(), 9)).decode()
    t0 = time.time(); out = decode_result(tok)
    print(f"  token {len(tok):>7,} 字符 → 解压 {len(payload)/1e6:>6.1f} MB "
          f"({time.time()-t0:.2f}s) 放大 {len(payload)//len(tok)}×  "
          f"三键检查通过={out is not None}")
PY
```

实测输出：

```
encode 端门控 = 6000 字符 / decode 端门控 = 无
  token   5,928 字符 → 解压    4.5 MB (0.01s) 放大 759×  三键检查通过=True
  token  31,932 字符 → 解压   24.6 MB (0.05s) 放大 769×  三键检查通过=True
```

（543KB 的 token 实测解压出 400MB / 1029× —— zlib 理论极限比；但那个长度已超出
浏览器与 Tornado 请求行的实际承载，所以下面按 ~25MB 评级。）

`share.py:41` 的三键存在性检查发生在**解压之后**，`_MAX_TOKEN_CHARS` 那道门只管
自家 encode 出去的 token，对别人手搓的 `?p=` 完全不设防。

**影响**: 单次恶意链接约 25MB 内存尖峰 + 若干毫秒 CPU，随后被 `_validated_backup`
拒掉。本地单用户工具下几乎无害（这也是 low 的理由）；但它与 §7.8「token 无签名」
叠加：攻击者既能改内容又能放大体积，且非浏览器客户端（curl/脚本）不受 32KB 限制，
放大倍数直接吃到 1029×。属于"trivially fixable 就该修"的一类。

**建议**: decode 端加对称门控，两行即可：

```python
def decode_result(token: str) -> Optional[Dict[str, Any]]:
    if len(token) > _MAX_TOKEN_CHARS:          # 与 encode 同一常量
        return None
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        blob = zlib.decompressobj().decompress(raw, _MAX_DECOMPRESSED)  # 例 2 << 20
        ...
```

`zlib.decompressobj().decompress(data, max_length)` 在 3.9 上可用（不是 3.10+
特性，与 §9 的 `zip(strict=)` 教训无关），超限即截断 → `json.loads` 失败 →
现有 `except Exception: return None` 自然兜住。

---

```
[low] F30 — 历史搜索把用户输入原样当 LIKE 模式：`%` 和 `_` 被当通配符
```

**位置**: `app/utils/history.py:109-111`（`like = f"%{query}%"`，未转义 `%` `_`，也未声明 `ESCAPE`）· 调用方 `app/ui/sidebar.py:111-114`

**类别**: bug（功能正确性；**不是** SQL 注入——参数化绑定是对的）

**证据**（§4.B 点名的"title 含 SQL 通配符（`%`/`_` 进 LIKE 模式）"）：

```bash
.venv/bin/python - <<'PY'
import os, sys, tempfile
os.environ["CROCHET_HISTORY_DB"] = os.path.join(tempfile.mkdtemp(), "h.db")
sys.path.insert(0, '.')
from app.utils import history
def mk(rid):
    return {"result_id": rid,
            "analysis": {"body_type": "标准", "head_diameter_cm": 9.0, "height_cm": 18.0,
                         "main_features": [], "pose": "站立", "difficulty": "easy",
                         "parts": ["头部"]},
            "structure": {"parts": [{"name": "头部", "shape": "sphere"}]},
            "params": {"parts": [{"name": "头部", "type": "sphere", "color": "白色",
                                  "rounds": [{"row": 1, "stitches": 6}]}]}}
for rid, t in (("r1", "小熊"), ("r2", "兔子"), ("r3", "100%羊毛")):
    history.save_result(mk(rid), title=t)
for q, want in [("小熊", "1 条"), ("%", "1 条（只有 100%羊毛 字面含 %）"),
                ("_", "0 条（无一条含下划线）"), ("100%羊", "1 条")]:
    got = [i["title"] for i in history.list_results(query=q)]
    print(f"搜索 {q!r:9} → {len(got)} 条 {str(got):<32} 期望 {want}")
PY
```

实测输出：

```
搜索 '小熊'      → 1 条 ['小熊']                        期望 1 条
搜索 '%'        → 3 条 ['100%羊毛', '兔子', '小熊']      期望 1 条（只有 100%羊毛 字面含 %）
搜索 '_'        → 3 条 ['100%羊毛', '兔子', '小熊']      期望 0 条（无一条含下划线）
搜索 '100%羊'    → 1 条 ['100%羊毛']                    期望 1 条
```

第 4 例"看起来对"是巧合：`%` 在此处匹配了零个字符。若库里另有一条
「100 支羊毛」，`100%羊` 会把它一并命中——这才是用户能察觉的错。

**影响**: 搜索框里打 `%` 或 `_` 命中全部记录（`_` 尤其容易误触：文件名/命名里
很常见）；含 `%` 的标题（毛线成分「100%棉」「50%羊毛」是这个领域的高频写法）
无法被精确检索。属于低频、非破坏性的功能瑕疵。

**建议**: 转义三个 LIKE 元字符并显式声明 `ESCAPE`：

```python
if query:
    conds.append("(summary LIKE ? ESCAPE '\\' OR blob LIKE ? ESCAPE '\\' "
                 "OR title LIKE ? ESCAPE '\\')")
    esc = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    like = f"%{esc}%"
    params += [like, like, like]
```

`color` 那条（`:113-114`）拼的是 `f'%"{color}"%'`，色名来自内部色表不含元字符，
但同样建议一并转义以免将来色名可自定义时回归。

---

```
[low] F31 — 手改/损坏的历史 blob：点「载入」整页崩栈，V5 的「st.error + 删除出路」防线晚了一行
```

**位置**: `app/ui/sidebar.py:135`（`history.load_result` 在 `try` **之外**，`try` 从 `:142` 才开始）· `app/utils/history.py:133`（`json.loads(row[0])` 无保护）

**类别**: bug

**证据**（§4.B 点名的"历史 DB：手改 blob 为非法 JSON"；同样覆盖磁盘写入截断/损坏）：

```bash
.venv/bin/python - <<'PY'
import os, sqlite3, sys, tempfile
_db = os.path.join(tempfile.mkdtemp(), "h.db")
os.environ["CROCHET_HISTORY_DB"] = _db
sys.path.insert(0, '.')
from app.utils import history
history.save_result({
    "result_id": "rid-bad",
    "analysis": {"body_type": "标准", "head_diameter_cm": 9.0, "height_cm": 18.0,
                 "main_features": [], "pose": "站立", "difficulty": "easy",
                 "parts": ["头部"]},
    "structure": {"parts": [{"name": "头部", "shape": "sphere"}]},
    "params": {"parts": [{"name": "头部", "type": "sphere", "color": "白色",
                          "rounds": [{"row": 1, "stitches": 6}]}]}}, title="要改坏的")
with sqlite3.connect(_db) as c:                       # §4.B：手改 blob 为非法 JSON
    c.execute("UPDATE patterns SET blob=? WHERE rid=?", ('{"analysis": {"body_type"', "rid-bad"))

print("① 侧栏列表 list_results:", [i["title"] for i in history.list_results()])
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app/main.py", default_timeout=60); at.run()
btn = [b for b in at.sidebar.button if b.key == "hist_load_rid-bad"][0]
btn.click().run()
print("② 点「载入」后 →",
      f"❌ 整页异常: {at.exception[0].value.splitlines()[0]}" if at.exception
      else f"✅ st.error: {[e.value for e in at.error]}")
PY
```

实测输出：

```
① 侧栏列表 list_results: ['要改坏的']
② 点「载入」后 → ❌ 整页异常: Expecting ':' delimiter: line 1 column 26 (char 25)
```

推理链：`sidebar.py:113-117` 给 `list_results` 包了 try（所以列表能正常显示），
`:142-151` 给 `_validated_backup` / `_rebuild_params` 包了 try（V5 的诚意所在），
但**中间的 `:135` `history.load_result` 裸露**——`json.loads` 的 `JSONDecodeError`
直接穿透 `render_sidebar()` 冒到 `main.py:53`，Streamlit 渲染异常页。
V5 承诺的"该记录已损坏，无法载入（可点「删」清除）"永远不会出现。

**影响**: 用户看到一整页红色 traceback 而不是一句人话。刷新后列表恢复正常（按钮
状态是瞬态的），「删」按钮仍可点，所以**不是死局**——这也是我给 low 而非 medium
的原因。但它精确地打穿了 V5 声称已建成的那道防线。

**建议**: 把 `:135` 挪进 `:142` 那个 try 里（最小改动）：

```python
if c_h2.button("载入", key=f"hist_load_{it['rid']}"):
    try:
        data = history.load_result(it["rid"])
        if data is None:
            st.error("该记录已不存在"); st.stop()
        analysis, structure = _validated_backup(data)
        data["params"] = _rebuild_params(dict(data["params"]))
        data["analysis"], data["structure"] = analysis, structure
    except Exception as e:
        st.error(f"该记录已损坏，无法载入（可点「删」清除）: {e}"); st.stop()
```

更稳的做法是 `load_result` 自己吞掉解码错误返回 `None`（与"不存在"同一出口），
这样所有调用方都受保护。

---

### 5.C 安全面（§4.D）与测试真实性（§4.E）

```
[low] F32 — 脱敏正则漏掉「服务端回显的部分遮蔽 Key」：401 报文里的 sk- 前 5 位 + 后 4 位原样进 stderr 与日志
```

**位置**: `app/models/image_parser.py:49`（`re.sub(r"sk-[A-Za-z0-9_\-]{8,}", ...)`，`{8,}` 门限过高）· 泄漏出口 `:293`（`logger.error`）· `app/cli.py:156-157`（批量 stderr）

**类别**: 安全面

**证据**（这条是跑基线时**被 F33 顺带暴露**的真实观测，不是构造场景）：

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, '.')
from app.models.image_parser import _sanitize_secrets
KEY = "sk-f6e62" + "x" * 55 + "eaca"                    # 形如真实 OpenAI Key
echoed = ("Error code: 401 - {'error': {'message': \"Incorrect API key provided: "
          "sk-f6e62" + "*" * 55 + "eaca. ...\"}}")      # 服务端自己遮蔽后的回显
out = _sanitize_secrets(echoed, KEY, None)
print("脱敏后:", out[:110])
print("仍泄漏首 5 位 sk-f6e62 :", "sk-f6e62" in out)
print("仍泄漏末 4 位 eaca     :", "eaca" in out)
PY
```

实测输出：

```
脱敏后: Error code: 401 - {'error': {'message': "Incorrect API key provided: sk-f6e62****…****eaca. ...
仍泄漏首 5 位 sk-f6e62 : True
仍泄漏末 4 位 eaca     : True
```

两道防线同时失效的推理链：
1. `:48` 的 `text.replace(key, "***")` —— 回显串 ≠ 真 Key（中段被 `*` 替换），字面替换不命中；
2. `:49` 的 `sk-[A-Za-z0-9_\-]{8,}` —— 回显里 `sk-` 后只有 **5** 个明文字符就接 `*`，不满足 `{8,}`，正则不命中。

真实证据（`pytest` 跑 `test_cli_batch_directory` 时的 stderr 与 logger 输出，
`.env`/shell 里有 Key 时可复现）：

```
❌ doll0.png: Vision 解析失败（所有可用渠道均已尝试）: OpenAI Vision API 调用失败:
   Error code: 401 - {... Incorrect API key provided: sk-f6e62***…***eaca ...}
ERROR app.models.image_parser:image_parser.py:293 OpenAI Vision API error: ...同上...
```

**影响**: Key 的首 5 位 + 末 4 位落进终端回滚、CI 日志、`logging` 落盘文件。
遮蔽是 OpenAI 服务端做的（中段 55 字符已是 `*`），所以暴露面**有界**、不足以
重建 Key ——这是 low 的理由。但 F14 声称"异常全层脱敏"，实际存在这个可预期的
缺口：任何服务端在报文里回显部分 Key 都会命中它。

**建议**: 放宽正则并显式覆盖"明文+遮蔽符混排"的形态：

```python
text = re.sub(r"sk-[A-Za-z0-9_\-*]{4,}", "sk-***", text)   # 收 * 进字符类，门限降到 4
```

同时对 `keys` 做前后缀级脱敏（Key 已知时最可靠）：

```python
for key in keys:
    if key and len(key) > 12:
        text = text.replace(key[:8], "***").replace(key[-6:], "***")
```

§4.D 另两问的答案：`share` 解码异常**不含** Key（`share.py:45` 全吞不打印，无泄漏面）✅；
PDF 文件名恒为 `amigurumi_pattern.pdf`（`result_renderer.py:507`），无用户输入进文件名 ✅。

---

```
[high] F33 — 测试套件非 hermetic：环境里有 OPENAI_API_KEY 时真实打网络并计费，§2 基线不可复现
```

**位置**: 缺 `tests/conftest.py`（全仓无此文件）· `app/models/image_parser.py:128`（`__init__` 里无条件 `load_dotenv()`）· `:129-130`（回落 `os.getenv`）· `tests/test_round14.py:210-224`（`test_cli_batch_directory` 不注入假 SDK 也不清 Key）

**类别**: bug（测试基础设施）+ 文档失实（§2 基线）

**证据**:

```bash
# 开发机 shell / .env 里有 OPENAI_API_KEY 时：
.venv/bin/python -m pytest -q | tail -2
#   FAILED tests/test_round14.py::test_cli_batch_directory - assert 1 == 0
#   1 failed, 584 passed, 1 skipped

# 清空 Key 后：
OPENAI_API_KEY= ANTHROPIC_API_KEY= .venv/bin/python -m pytest -q | tail -1
#   585 passed, 1 skipped        ← 与 §2 完全一致
```

失败时的 stderr 证明它**真的发出了 HTTP 请求**（而非本地校验失败）：

```
❌ doll0.png: … OpenAI Vision API 调用失败: Error code: 401 -
   {'error': {'message': 'Incorrect API key provided: sk-…', 'code': 'invalid_api_key'}}
```

推理链：`test_cli_batch_directory` 走 `cli.main(["--batch-dir", …])`，**没给 `--local`
也没给 `--mock`**。`cli.py:75-76` 的 `use_local = args.local or not (openai_key or
anthropic_key)` 依赖"环境无 Key"这一**隐式前提**；一旦开发机 shell 导出了
`OPENAI_API_KEY`（或存在 `.env`），`ImageParser.__init__`（`image_parser.py:128-130`）
就把它捡起来，两张测试图各发一次真实 Vision 请求。Key 有效时**会真实计费并把
测试图片上传给第三方**，且 `parse_image` 成功后断言仍可能因模型返回值波动而随机失败。

同一机制影响所有构造 `ImageParser` / `PipelineOrchestrator` 而不清 Key 的测试；
`test_cli_batch_directory` 只是**唯一恰好因此断言失败**的那个（其余大多显式
`local_vision=True` 或注入假 SDK）。

**影响**:
- §2 的基线命令在任何配了 Key 的开发机/CI 上都不复现——审查者第一步就撞上，
  且第一反应会误判为"代码坏了"（我实际就是这样开始这轮审查的）；
- CI 若在 secrets 里注入 Key（`extras.yml` 金丝雀很容易顺手加），会变成
  **每次 push 都真实调用付费 API 并上传测试图片**；
- 测试可靠性建立在"环境恰好干净"上，属于最脆的一类前提。

**建议**: 加 `tests/conftest.py`，用 autouse fixture 把外部 Key 从进程环境里摘掉：

```python
# tests/conftest.py
import pytest

_EXTERNAL_ENV = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                 "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL",
                 "OPENAI_VISION_MODEL", "ANTHROPIC_VISION_MODEL")

@pytest.fixture(autouse=True)
def _no_real_api(monkeypatch):
    """测试一律不得走真实 Vision API——显式注入假 SDK 的用例自己 setenv。"""
    for name in _EXTERNAL_ENV:
        monkeypatch.delenv(name, raising=False)
```

注意 `image_parser.py:128` 的 `load_dotenv()` 默认**不覆盖**已有环境变量，但
`delenv` 之后 `.env` 里的值会重新灌入——所以还需 `monkeypatch.setattr(
"app.models.image_parser.load_dotenv", lambda *a, **k: False)`，或在 fixture 里
`monkeypatch.setenv(name, "")`（空串在 `:135-137` 被视同未填，`:129` 处 `or` 也会
落到 `None` 之外——建议用 `delenv` + patch `load_dotenv` 双管）。

另外把 `test_cli_batch_directory` 显式加上 `--local`，让它测的是"批量编排"
而不是"环境恰好没 Key"。建议同时在 `pyproject.toml` 里配一条 socket 守卫
（如 `pytest-socket` 的 `--disable-socket --allow-unix-socket`），把这类回归
钉死在基础设施层。

---

```
[low] F34 — 评测脚手架的 manifest 契约不自洽：`dominant_color` 声明在契约与文档里，测试从未校验
```

**位置**: `tests/test_eval_real.py:5-7`（契约声明 `dominant_color` + "指标：…主色命中"）· `:28`（用例 docstring 复述"主色命中"）· `:27-51`（**测试体全文无 `dominant_color`**）

**类别**: 文档失实（测试契约）

**证据**:

```bash
grep -n "dominant_color\|主色" tests/test_eval_real.py
#   6:      "dominant_color": "蓝色"}, ...]          ← 契约里要求标注者提供
#   7:指标：部件集命中率、flare 检出一致性、主色命中。  ← 宣称三个指标
#  28:    """每张标注图：部件集命中 ≥1、主色命中、flare 一致…"""  ← 再次宣称
# 测试体（:29-51）只 assert 了 overlap（部件）与 got_flare（flare）——无第三项

sed -n '27,51p' tests/test_eval_real.py | grep -c "dominant_color"
#   0
```

`_manifest()`（`:22-24`）读整个 json，`test_real_images_meet_baseline` 循环里只用
了 `entry["file"]`、`entry["parts"]`、`entry["flare"]`。三个宣称指标实现了两个。

判定性证据——**按契约造一份评测集干跑，把 `dominant_color` 标成一个根本不是
颜色的字符串，测试照样通过**：

```bash
D=$(mktemp -d)
.venv/bin/python -c "
from PIL import Image, ImageDraw
import json, os, sys
d = sys.argv[1]
img = Image.new('RGB', (200, 320), (245, 245, 245)); dr = ImageDraw.Draw(img)
dr.ellipse([70, 20, 130, 80], fill=(230, 180, 150))
dr.rounded_rectangle([80, 85, 120, 300], radius=10, fill=(0, 120, 215))  # 蓝色身体
img.save(os.path.join(d, 'a.jpg'))
json.dump([{'file': 'a.jpg', 'parts': ['头部', '身体'], 'flare': False,
            'dominant_color': '这不是颜色_XYZ'}],          # 故意标错
          open(os.path.join(d, 'eval_manifest.json'), 'w'), ensure_ascii=False)
" $D
CROCHET_EVAL_DIR=$D OPENAI_API_KEY= ANTHROPIC_API_KEY= \
  .venv/bin/python -m pytest tests/test_eval_real.py -q --no-header
#   1 passed, 1 warning in 0.71s        ← 主色标成垃圾串也照过
```

**影响**: 这是 §4.E 点名要审的"评测脚手架从未真实运行——manifest 契约本身是否
自洽"，答案是**不自洽**。后果是标注成本被白白支付：标注者按契约逐图填
`dominant_color`（这是三项里最费人工的一项），而脚手架永远不会读它。等真拿到
评测集才发现，标注返工的代价远高于现在补两行。

顺带确认了脚手架的**其他**契约是自洽的（上面那次干跑同时验证了）：
`result["analysis"]` 确为 dict（`orchestrator.py:135` `model_dump()`，所以
`result["analysis"]["parts"]` 不会 TypeError）、`result["structure"]["parts"]`
形状正确、`skipif` 逻辑正确、`local_vision=True` 不打网络 ✅。

**建议**: 补上第三个断言（色板是有序列表，主色应在前若干名内）：

```python
if entry.get("dominant_color"):
    got_colors = result["analysis"].get("recommended_colors") or []
    assert entry["dominant_color"] in got_colors[:3], \
        f"{entry['file']}: 主色 {entry['dominant_color']} 未进前三 {got_colors[:3]}"
```

若判定该指标暂不评，则把 `dominant_color` 从 `:6` 的契约与 `:7`/`:28` 的
docstring 里删掉——别让标注者填一个没人读的字段。

---

```
[low] F35 — 分享门控测试构造了应用永不产生的数据形状：CrochetPart.rounds 塞进裸 dict，pydantic 报警
```

**位置**: `tests/test_round14.py:88`（`part0.rounds = rounds`，`rounds` 是 dict 列表）

**类别**: 可维护性（测试真实性）

**证据**:

```bash
.venv/bin/python -m pytest -q -W error::UserWarning --tb=no 2>&1 | grep FAILED
#   FAILED tests/test_round14.py::test_share_size_guard_returns_none - UserWarning: …
#   FAILED tests/test_round14.py::test_cli_batch_directory - assert 1 == 0   ← 这条是 F33
```

告警全文（每圈一条，共数十条）：

```
UserWarning: Pydantic serializer warnings:
  PydanticSerializationUnexpectedValue(Expected `CrochetStitch` -
  serialized value may not be as expected [field_name='rounds',
  input_value={'row': 1, 'stitches': 6, …}, input_type=dict])
```

推理链：pydantic v2 默认不做赋值校验，`part0.rounds = [dict, …]`（`:88`）能通过，
但序列化时逐项报警。应用侧**永远**是 `CrochetStitch` 实例
（`crochet_params.py` 全用 `CrochetStitch(**r)` 构造，`result_renderer.py:60`
的 JSON 修正路径同理），所以这个测试验证的是一种**产品不存在的形状**下的
6000 门控。门控本身仍被有效触发（`share.py:28-29` 的 `default=model_dump`
对 dict 也能序列化），因此是"测试卫生"问题而非功能问题。

**影响**: 无用户可见影响。但它污染 `-W error` 下的信号（想给 CI 加
`filterwarnings = error` 时会先被这条挡住），也让"分享门控已验证"这个结论比
实际弱一点。

**建议**: 全程用真实类型构造（`model_copy` 保持 `CrochetStitch`，无需 import）：

```python
base = list(part0.rounds)                      # 已是 CrochetStitch 实例
grown = list(base)
for r in base * 30:
    grown.append(r.model_copy(update={"notes": uuid.uuid4().hex}))
part0.rounds = grown                           # 全程 CrochetStitch
assert encode_result(result) is None
```

实测该写法下 527 圈、`encode_result` 仍返回 `None`（门控照样触发），且在
`-W error::UserWarning` 下零告警。修掉后即可在 `pyproject.toml` 的
`[tool.pytest.ini_options]` 加 `filterwarnings = ["error::UserWarning"]`，
把这类形状漂移钉死在 CI 里。

---

### 5.D 领域正确性（§4.C）

```
[medium] F36 — 帽子与圆柱在同一文件里用了相反的高度口径：帽子把径向帽顶盘算进高度，圆柱明确不算起底盘
```

**位置**: `app/models/crochet_params.py:593`（`actual_h = round(len(rounds_raw) * gauge.row_h_cm, 1)`，`rounds_raw` 含帽顶加针段）· `:283-292`（`_cup_rounds` = 径向加针盘 + 轴向筒壁）· 对照 §6「圆柱/帽标注高度**只计筒壁轴向**」与 §8.6（圆柱含起底盘是**已确认的错**）

**类别**: 领域错误 + 文档失实（二者必有其一，见下）

**证据**（§4.C 第二问。先修正任务书的前提数字：20cm 头径在 classic 密度下侧壁是
**22 圈 ≈ 13.8cm**，不是"12 圈 ≈ 7.5cm"）：

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, '.')
from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis
a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                  main_features=[], pose="站立", difficulty="easy",
                  parts=["头部", "身体", "帽子"])
s = StructureDesigner.design_3d_structure(a); g = Gauge(13.0, 16.0)
p = CrochetParamsGenerator.generate_params(a, s, gauge=g,
        style=ShapingStyle("ladder", False, "ring", False))
hat = next(x for x in p["parts"] if x.name == "帽子")
body = next(x for x in p["parts"] if x.name == "身体")
print("帽子 圈数针数:", [r.stitches for r in hat.rounds])
print(f"帽子 height_cm = {hat.height_cm}  ( = 全部 {len(hat.rounds)} 圈 × "
      f"{g.row_h_cm:.3f} = {len(hat.rounds)*g.row_h_cm:.1f} )")
print("帽子 notes:", hat.notes)
print(f"\n圆柱身体 height_cm = {body.height_cm}  "
      f"(全部 {len(body.rounds)} 圈 × 行高 = {len(body.rounds)*g.row_h_cm:.1f} ← 刻意不用)")
PY
```

实测输出：

```
帽子 圈数针数: [6, 12, 18, 24, 30, 36, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42]
帽子 height_cm = 10.6  ( = 全部 17 圈 × 0.625 = 10.6 )
帽子 notes: 开口帽形（帽围 42 针 > 头围，不收口可直接佩戴），帽高约 10.6cm
            （含帽顶；侧壁 10 圈 ≈ 6.2cm）。

圆柱身体 height_cm = 5.6  (全部 15 圈 × 行高 = 9.4 ← 刻意不用)
```

`9.4` 这个数字正是 §8.6 记录的"会把 4.5cm 身体标成 9.4cm"——项目**已经认定**
把径向起底盘算进轴向高度是错的，并为圆柱修掉了。帽子的几何完全同构
（`_cup_rounds` = `_increase_rounds(42)` 的**平面径向盘** 6→42 共 7 圈，
再加 10 圈轴向筒壁 42X），却仍按 17 圈全算。

跨尺寸实测（classic 密度）：

| 头径 | 帽直径 | 帽顶圈(径向) | 侧壁圈(轴向) | 侧壁 cm | 标注 height_cm | 虚高 |
|---|---|---|---|---|---|---|
| 6.0 | 6.9 | 5 | 7 | 4.4 | 7.5 | +70% |
| 9.0 | 10.3 | 7 | 10 | 6.2 | 10.6 | +71% |
| 14.0 | 16.1 | 11 | 15 | 9.4 | 16.2 | +72% |
| 20.0 | 23.0 | 16 | 22 | 13.8 | 23.8 | +72% |
| 30.0 | 34.5 | 23 | 33 | 20.6 | 35.0 | +70% |

**影响**: 两处口径不一致必有一处误导用户：

- 若 §6 的"只计筒壁轴向"是正确口径 → `height_cm` 系统性虚高 ~70%，PDF 的
  「🧶 帽子（17 圈 · cup）· 直径 10.3cm · **高 10.6cm**」（`pdf_export.py:107-108`）
  这一行是错的；用户按 10.6cm 预期做出来的帽子实际筒深只有 6.2cm。
- 若"含帽顶"才是想要的口径 → §6 的文档条目错，且与同文件圆柱的处理自相矛盾，
  下一位维护者改任一处都会踩另一处。

缓解事实（这也是我给 medium 而非 high 的理由）：`notes` 明确写了"含帽顶；侧壁
10 圈 ≈ 6.2cm"两个数都给了，`diameter_cm` 正确，圈数表本身正确——照着钩不会
钩错，只是标注尺寸会让人误判。

**说明我没有重复 §8 的误报**：§8.6 是"圆柱标注高度含起底圆盘"这个**修法**被判为
误报（因为会把 4.5 标成 9.4）。我这条是反向的——我引用 §8.6 已确立的原则，
指出**帽子没有享受同一原则**。两者不冲突。

**建议**: 二选一，但必须显式选。倾向（a）与圆柱统一：

```python
# crochet_params.py:593
wall_cm = round(wall_rounds * gauge.row_h_cm, 1)
part = CrochetPart(..., height_cm=wall_cm, ...,      # 只计轴向筒壁，与圆柱同口径
    notes=(f"开口帽形（帽围 {max_st} 针 > 头围，不收口可直接佩戴），"
           f"筒深 {wall_rounds} 圈 ≈ {wall_cm}cm"
           f"（另有帽顶 {len(rounds_raw)-wall_rounds} 圈径向加针盘）。"))
```

（b）若坚持"含帽顶"，则把 §6 的条目改成"圆柱只计筒壁；帽子含帽顶（戴上后帽顶
盘会张在头顶弧面上，故计入）"，并在 `pdf_export.py` 的尺寸行补「含帽顶」字样。
无论选哪个，都建议加一条回归断言把口径钉住。

---

### 5.E 取舍与增强（不作为 bug 上报）

**取舍 T1 — `allow_wide_jump` 可在 JSON 修正框里被用户置 true 放行任意跳变。**
§4.A 第四问的直接答案：**会放行**。实测 `stitches: 9999, increase: 9993,
allow_wide_jump: true` 通过 `_rebuild_params` 后 `validate_pattern` 返回 `ok=True`；
不带该标志则被拦（`未声明 allow_wide_jump`）。判定为取舍而非 bug，理由三条：
① 结果页的自检是**咨询性**的（`result_renderer.py:249-253` 只 `st.success`/
`st.warning`，从不阻断渲染或下载），不是门禁，所以"绕过"没有绕过任何强制；
② 真正的门禁在生成侧（`crochet_params.py:880-885` 抛 `PatternGenerationError`），
那里的 `allow_wide_jump` 由生成器自己置位，用户碰不到；③ CLI 的 rc=2 门禁
（`cli.py:107-111`）只校验自己生成的图解，不吃外部 JSON。**若**将来要把 UI 自检
升级为真门禁，则需要区分"生成器置位"与"用户置位"（例如把标志改成
`_allow_wide_jump` 并在 `_rebuild_params` 里剥离用户提供的值）。

**取舍 T2 — `estimate_minutes` 下限 30 分钟。** §4.C 第一问。实测：单部件 2 圈
（18 针）原始算式 2.3 分 → 返回 30；最小可生成玩偶（头 4cm 单部件，8 圈 108 针）
原始 13.0 分 → 返回 30。判定合理：30 分钟对"含起针、换线、填棉、藏线头、缝合"
的**完整制作**是保守下限，而 6.5s/针的线性模型在极小样本上必然低估固定开销。
建议仅在文案上更诚实——`estimate_minutes` 的 docstring 已写"经验估算"，可再补
一句"下限 30 分钟含备料与收尾固定开销"。

**取舍 T3 — 波浪摆末圈 `hem_st * 2` 无上界。** §4.C 第四问。实测（末圈针数 /
末圈周长）：头 9cm classic = 96 针 / 73.8cm；头 20cm classic = 204 针 / 156.9cm；
头 50cm（schema 上限）max 密度 = 1572 针 / 393cm。判定**不需要上界**：该值完全
由裙摆围度决定（`hem_st = _stitches_for_diameter(头径 × 1.0 × 1.25)`），而
"每针放 2 针"是波浪摆的定义本身——加上界等于把工艺改错。极端值只出现在极端
入参（头 50cm 玩偶）下，且 `ImageAnalysis` 的 `le=50` 已是硬安全上限。

**增强 E1 — 零宽字符 / RTL 覆盖符可进部件名与色名。** 实测
`{"name": "头​部‮反转"}` 通过 `_rebuild_params`，随后进入
`st.expander` 标签、`_yarn_chip_html`（只做 `html.escape`，不剥离 bidi 控制符）、
PDF `Paragraph`。用户自己粘贴属自伤；但**同一字段也能从 LLM 输出进来**
（`parts` / `hair_color` / `top_color` 是自由字符串，图片内文字可借 prompt
injection 注入），所以是一条真实的显示欺骗面。建议在
`result_renderer._yarn_chip_html` 与 `pdf_export.esc` 里加一次
`re.sub(r"[​-‏‪-‮⁦-⁩]", "", s)`。危害限于视觉
错序，故列增强而非 bug。

**增强 E2 — `CrochetStitch.row` 可重复/乱序，validator 不检查。** 实测把两圈
都设成 `row: 1` 顺利通过 schema 与 `validate_pattern`；UI（`result_renderer.py:354`）
与 PDF 都按 `rd["row"]` 显示，于是出现两个"第 1 圈"。`validator.py:48` 已经用
`enumerate(rounds, 1)` 的位置序号做代数校验，所以**算法不受影响**，只是显示混乱。
建议 `validate_pattern` 加一条 `if rd.get("row") != i: issues.append(...)`。

**增强 E3 — `hist_title_` 未列入 `_WIDGET_KEY_PREFIXES`。** `result_renderer.py:21-25`
的清理前缀表覆盖了全部 17 个以 `result_key` 组键的 widget，独漏 `hist_title_`
（`:512`）。可脚本验证：

```bash
.venv/bin/python -c "
import re; src=open('app/ui/result_renderer.py').read()
pre=re.findall(r'\"([a-z_]+)\"', src.split('_WIDGET_KEY_PREFIXES = (')[1].split(')')[0])
keys=set(re.findall(r'key=f\"([a-z_]+)\{', src))
print('未被清理:', sorted(k for k in keys if not any(k.startswith(p) or p.startswith(k) for p in pre)))"
# → 未被清理: ['hist_title_']
```

后果仅是每生成一份新结果就在 `session_state` 里留一个字符串键（长会话缓慢累积），
无串档风险（键含 rid）。修法：前缀表加 `"hist_title_"`。与 F25 一并修最省事。

**增强 E4 — 历史载入恒写 `session_state["result"]`（照片 Tab 槽位）。**
`sidebar.py:152-155` 硬编码槽位 `"result"`，而手动 Tab 用
`"manual_result"`（`tab_manual.py:122`）。在手动 Tab 生成并存入历史的图解，
载回后出现在「📸 照片识别」Tab 下。不是错误（结果本身完整），但会让用户困惑。
建议在 result 里记一个 `origin_slot` 并按它回填，或在载入成功的 `st.info` 里
点明"已载入到照片识别 Tab"。

---

### 5.F 负面结果（查过、构造了对抗输入、确认无问题）

这些是本轮**投入了时间但没找到问题**的面。列出来是为了让下一轮不必重扫，
也为 §7「已知局限」提供实测依据。

**F-1 分享 token 库层多轮循环无信息衰减。** 造完整九键 result（含 egg style /
color_bands / spans / spans_measured / vision_meta），跑 4 轮
`encode → decode → _validated_backup → _rebuild_params → encode`：

```
轮  token长  style  bands  spans  measured  preview  总针数   部件
0   2712    True   True   True   ['身体']   False    1920    ['头部','身体','腿部']
1   2712    True   True   True   ['身体']   False    1920    ['头部','身体','腿部']
2   2712    True   True   True   ['身体']   False    1920    ['头部','身体','腿部']
3   2712    True   True   True   ['身体']   False    1920    ['头部','身体','腿部']
```

token 长度、九键、总针数、部件名逐轮**完全一致**——§4.A 第一问的"二级 token
是否保真 / 多轮有无衰减"答案是**保真、无衰减**。唯一变化是 `spans` 的
`tuple → list`（JSON 无 tuple 类型），下游全是索引访问，无影响。`preview`
不进 token 符合 §6 刻意设计。**注意**：这条只在库层面成立，产品层没有入口（F23）。

**F-2 CLI 批量的失败隔离与实例隔离都成立。** 一张图失败其余继续 ✅（`_one`
的 `except Exception` + `pool.map` 逐项收集）；每图独立 `PipelineOrchestrator`
确实隔离了 `parser.last_usage` / `last_local_meta` 实例状态 ✅（`run()` 内
`:69` 每次新建）；非图片文件被跳过 ✅（`:132-133` 按后缀过滤）。并发 stderr
未观察到行内交错。唯一问题是输出文件名撞名（F27）。

**F-3 1800 组塑形矩阵零异常、零自检失败。** 5 档密度（含 6×8 与 40×50 边界）
× 5 档尺寸（含 4/10 与 50/200 schema 边界）× 3 种球型 × 一体件开关 ×
2 种裙法 × 波浪摆开关 × 3 种部件集：

```
扫描组合数: 1800
生成期抛异常: 0
生成成功但自检不通过: 0
```

特别确认 §4.C 第三问（egg/ideal + 一体件的 `head_kept` 截断语义）：`ideal` 与
`egg` 在一体件下都不产生非 ±6 的跳变，`_merge_head_body`（`:749-751`）硬编码
`increase/decrease = 6` 与实际针数差**始终一致**——没有"文字/针数/代数三方矛盾"。

**F-4 八类对抗图片全部安全降级。** `1×10000`、`10000×1`、全透明 RGBA、
`I;16` 灰度、CMYK JPEG、1-bit 单色、`2×2` 极小、60KB EXIF，走
`load_image_file → run_full_pipeline(local_vision=True)` 全部返回合法结果
（退回 9.0cm/18.0cm 默认，无崩溃、无异常值）。`images.py` 的
EXIF 转置 + 透明合成白底两道防线有效。**唯一出事的是这些图进 2D 网格路径**
（F28），那是宽高比放大而非解码问题。

**F-5 JSON schema 确实拦住了负数与零针数。** §4.B 第一问：
`stitches: -12` 与 `stitches: 0` 都被 `CrochetStitch` 的 `Field(ge=1)` 拒绝
（`ValidationError`），`row` 的 `gt=0` 同理。10000 个部件能通过（0.13s，
validator 校验 20000 圈 0.11s），5MB notes 能通过——两者都只是慢，不崩。

**F-6 PDF 转义无残余面。** `pdf_export.esc`（`:26-29`）对 `item`/`quantity`/
`notes`/`row`/`stitches`/`color`/装配每一行都过 `html.escape`，`<font>`/`<img>`/
`<script>` 全部字面输出；`html.escape` 先把 `&` 变 `&amp;`，故 `&#..;` 实体
注入也不成立。文件名恒定，无用户输入。

**F-7 fake SDK 形状与真实 SDK 一致。** §4.E 第一问。实测装的是
`openai 2.48.0` / `anthropic 0.122.0`；真实
`ParsedChatCompletionMessage.model_fields` = `{annotations, audio, content,
function_call, parsed, refusal, role, tool_calls}`，测试用
`SimpleNamespace(parsed=…, refusal=…, content=…)`（`test_image_parser.py:572`）
覆盖的三个字段名**完全对得上**；`client.chat.completions.parse` 与
`anthropic.Anthropic().messages.parse` 均真实存在（§8.3 的结论仍成立）。

**F-8 `purge_result_state` 无串档风险。** §9 警告"AppTest 的 session_state 无
`.keys()`"，而 `:77` 正是用 `.keys()`——值得一验。现有覆盖
（`test_audit_fixes.py:236-240`）是用一个自带 `.keys()` 的 `FakeState(dict)`
monkeypatch 掉 `rr.st.session_state`，所以**它并不能证明真 session_state 可用**。
我另起一个真实 Streamlit 脚本上下文直接验：

```bash
.venv/bin/python - <<'PY'
import os, sys, tempfile
os.environ['CROCHET_HISTORY_DB'] = os.path.join(tempfile.mkdtemp(), 'h.db')
sys.path.insert(0, '.')
p = os.path.join(tempfile.mkdtemp(), 'probe.py')
open(p, 'w').write(
    "import streamlit as st\n"
    "st.session_state['chk_abc_0'] = True\n"
    "from app.ui.result_renderer import purge_result_state\n"
    "purge_result_state({'result_id': 'abc'})\n"
    "st.write('purge 后剩余:', [k for k in st.session_state])\n")
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(p, default_timeout=30); at.run()
print("异常:", at.exception[0].value.splitlines()[0] if at.exception else "无 ✅")
print("输出:", [m.value for m in at.markdown])
PY
#   异常: 无 ✅
#   输出: ['purge 后剩余:']        ← chk_abc_0 已被清掉，.keys() 正常工作
```

结论：§9 的那条限制针对的是**测试代理** `at.session_state`，不是应用内的
`st.session_state`——应用代码用 `.keys()` 安全 ✅。17 个 widget 前缀里 16 个被
覆盖，漏的 `hist_title_`（E3）因键含 rid 也不会串档。`chk_` 的越界清理
（`:286-295`）在圈数减少后正确生效。

---

### 5.G §4 各问的逐条答复

| 任务书问题 | 答复 | 依据 |
|---|---|---|
| §4.A token 九键 → 载入 → 调尺寸，style/spans 恢复？ | **token 路径恢复 ✅；备份路径全丢 ❌** | F24 |
| §4.A 二级 token 保真？多轮有衰减？ | 保真、4 轮零衰减（但产品无入口） | F-1 / F23 |
| §4.A 历史往返 title 保留还是丢失？ | **丢失**（被 NULL 覆盖） | F25 |
| §4.A 旧 schema 库迁移 → 载入 → 勾选 → 修正 → 再存 | 迁移本身幂等正确 ✅，丢的是 title | F25 / F-8 |
| §4.A 批量中一张失败其余继续？ | 继续 ✅ | F-2 |
| §4.A 并发 stderr 交错掩盖失败？ | 未观察到交错；但**文件名撞名会静默丢结果** | F27 |
| §4.A 每图独立 orchestrator 真隔离了 parser 状态？ | 真隔离 ✅ | F-2 |
| §4.A JSON 改 `allow_wide_jump: true` 会放行吗？ | **会**，但 UI 自检是咨询性的，判为取舍 | T1 |
| §4.A 调尺寸 × 一体件 × 波浪摆 × spans 叠加成立？ | 成立 ✅（1800 组零失败）；丢的是 `preview` | F-3 / F26 |
| §4.B 负数针数 schema 拦？ | 拦住 ✅ | F-5 |
| §4.B 5MB notes / 1 万部件 | 通过但只是慢（0.13s），不崩 | F-5 |
| §4.B 零宽 / RTL 进 notes 色名 | 通过，属显示欺骗面 → 增强 | E1 |
| §4.B zlib 炸弹 | **decode 端无门控**，~770× 放大 | F29 |
| §4.B 嵌套极深 structure | `RecursionError` 是 `Exception` 子类，被 `share.py:46` 吞掉 ✅ | — |
| §4.B DB blob 改成非法 JSON | **整页崩栈**，V5 防线晚一行 | F31 |
| §4.B title 含 `%`/`_` 进 LIKE | **未转义**，搜 `_` 命中全部 | F30 |
| §4.B 极端宽高比 / 全透明 / 16-bit / CMYK / 巨 EXIF | 解码路径全部安全降级 ✅；**网格路径 4.5GB** | F-4 / F28 |
| §4.C estimate_minutes 下限 30 合理？ | 合理（含备料收尾固定开销） | T2 |
| §4.C 帽子总高（含帽顶）合理？ | **与圆柱口径打架，虚高 ~70%**；任务书前提数字也需修正 | F36 |
| §4.C egg/ideal + 一体件 head_kept 语义 | 正确 ✅，无三方矛盾 | F-3 |
| §4.C 波浪摆 `hem_st*2` 该有上界？ | 不该有（工艺定义使然） | T3 |
| §4.D CLI stderr / 批量异常 / share 解码 过 `_sanitize` 吗？ | share 无泄漏面 ✅；**CLI 漏服务端回显的部分遮蔽 Key** | F32 |
| §4.D token 无签名的风险等级 | low（本地工具）；但与 F29 叠加放大 | F29 / §7.8 |
| §4.D PDF 标签残余 / 文件名注入 | 无残余、无注入 ✅ | F-6 |
| §4.E fake SDK vs 真实 openai 2.48 | 形状一致 ✅ | F-7 |
| §4.E 评测脚手架 manifest 契约自洽？ | **不自洽**：`dominant_color` 从不校验 | F34 |
| §4.E 矩阵 + hypothesis 是否有未覆盖组合 | 有：**测试套件本身非 hermetic** 是更大的洞 | F33 / F35 |

---

### 5.H 与前几轮发现的重叠度自评

**零重叠。** F23–F36 与 v1 的 F13–F22、以及 §6/§8 记录的历次发现无一条重复：

- **§8 的 10 条历史误报，我一条都没重踩。** 唯一擦边的是 F36 与 §8.6（圆柱起底盘）
  ——但方向相反：§8.6 判"给圆柱加上起底盘"为误报，我是**引用该判决已确立的原则**
  去指出帽子没有享受它。我在 F36 里显式写了这一区分。
- **§6 的刻意设计我没有报为 bug。** 波浪摆 `allow_wide_jump`（§6/§8.8）只作为
  取舍 T1 讨论其被滥用的通道；`preview` 不进 token（§6）在 F-1 里确认为正确；
  米数经验估算（§6/§8.9）、sin 球末圈 12 针（§8.4）、裙腰开口（§8.5）我都验证过
  未报。
- **v1 的 F13–F22 全部处置有效**：F13（±6 桥接）在 1800 组一体件里零违规；
  F14（异常脱敏）只剩 F32 这个正则门限的边角；F15（有效 span = 先验 ∪ 实测）
  在 `orchestrator.py:79` 正确；F16（`strip_dome` / 一体件高度口径）正确
  ——**但同一个"径向盘不计轴向高度"的原则没有推广到帽子，这就是 F36**。
- **本轮 9/14 集中在前两轮最少覆盖的两个面**（交互面 + 对抗输入），与 §0 的
  判断吻合：单函数内部逻辑确已被 585 条测试 + 三轮审查摘尽（F-3 的 1800 组
  零失败是直接证据），增量价值全在**跨模块状态传递**（F23–F27 全是"某个键在
  某条路径上没被传下去"）与**外部输入放大**（F28/F29）。

**一句话结论**：这套系统的**单点逻辑**已经很硬，**接缝**还没有。F24/F26/F27
是同一个病根的三处发作——同一份结果 dict 在 5 条路径（生成 / 备份 / 导入 /
分享 / 调尺寸 / 存历史）上各自手抄键集，谁抄漏谁丢数据。建议把"共用键集常量 +
一条断言各路径键集相等的回归测试"作为本轮修复的第一优先，其价值高于逐条修
F24/F26。

## 6. 刻意设计决策（勿报为 bug——截至第十六轮的汇总）

**领域/几何**
- 针数恒为 6 的倍数、非波浪圈 |Δ|≤6（短针平盘极限）；波浪摆"每针放
  2 针"经 `allow_wide_jump` 显式豁免（validator 物理检查的白名单）。
- 圆柱/帽标注高度只计筒壁轴向；一体件高度 = 头部到颈 + 筒壁（strip_dome
  口径，收口盘不计）；帽子侧壁 = max(3, 0.6·直径)。
- sin 球末圈 ≤12 针 + "勿再减针收成 6 针"原文工艺警告。
- 一体件高度 13.8cm（ladder 默认）是正确口径（旧 17.5 是假 dome bug）。
- 时长 = 针数×6.5s + 圈数×10s（校准锚点 classic 121≈旧值 122；经验
  估算，无标准机构署名——V6 教训）。

**视觉/数据**
- GrabCut：FGD 下限 144（浅肤色 vs 白背景实测 176 < 旧 2T=192 被吞）；
  Otsu 钳位 [16,96]；覆盖率门槛 15%；腐蚀 1px；退化区间 [5%,95%]。
- 米数 320/250/200/140 为**实务经验估算**（V6：非 CYC 数据，CYC 不含
  长度）；逐色材料下限 5g/色、分组下限 20g；内部占位符 skin/body
  不进逐色材料。
- 品牌色号只收录 8 个已核实 Catona 条目，未核实色名宁缺毋错。
- F15 有效 span = 先验 ∪ 实测；spans_measured 记录实测来源。

**架构/产品**
- share token 九键与备份同构，preview 不进 token（6000 门控保留作
  防御——真实图解最坏 5596 从未触发）；分享载入 rid 用 uuid（V3）；
  历史/分享载入走 _validated_backup（V5 对等校验）。
- CLI 批量每图独立 orchestrator（parser 实例状态隔离）+ ThreadPool
  并发；CLI 同受自检门禁（rc=2）。
- orchestrator 不用 @st.cache_resource（key 滞留）；mock 数据带水印；
  mock 选项只在真正无 Key 时出现（N1）。
- mediapipe 钉 <1.0（1.0.x macOS 原生崩溃）且保持可选 [pose]（拖入
  opencv-contrib 5.x 与 headless<5 冲突）；pose 未检出 → 回退先验。
- U32 升 3.11 曾尝试并回滚（zip strict= 是 3.10+ 特性，3.9 运行时
  TypeError）；完整方案四步已记录（handoff §23）。
- CROCHET_EVAL_DIR 评测脚手架无评测集时 skipif 跳过。

## 7. 已知局限（只评估严重度）

1. 视觉管线验证几乎全在合成图上（真实照片条件未知）——已知最大盲区。
2. 无真实 LLM API 集成测试（fake SDK 只锁参数形状）。
3. pose 不可用时部件分段回退先验；正面关键点测不到尾巴。
4. 旋转体假设（剖面×圆截面）。
5. tab_photo 上传交互无 AppTest 覆盖；PDF/环形图无目测验证。
6. mediapipe 0.10.x 实机验证因网络未完成。
7. 无 i18n（U9 搁置：与中文断言测试耦合，需 i18n key 专项）。
8. 分享 token 无签名（本地工具定位下评估等级）。
9. 历史无跨设备迁移/加密。

## 8. 历史误报清单（勿重复——全部真实发生过）

1. 网格 aspect_ratio 补偿方向——被误报"反了"两次。
2. 减针"隔N针"——外部第一轮给了错误修法。
3. "anthropic>=0.95 需升级才有 messages.parse"——实测已含。
4. "sin 球末圈 12 针没收到 6"——物理必然+原文工艺警告。
5. "裙腰应闭口"——闭口圆盘套不进身体。
6. "圆柱标注高度含起底圆盘"——会把 4.5cm 身体标成 9.4cm。
7. "classic 密度 w/h=1.23 反物理"——已记录取舍。
8. "波浪摆 48 跳变违反 |Δ|≤6"——V2 已加 allow_wide_jump 显式白名单
   （工艺正确的装饰性例外，见 §6）；再报请先读该机制。
9. "米数该有标准出处"——V6 已纠正为如实署名经验估算。
10. "zip 缺 strict="——U32 曾启用 B905 后回滚（3.9 运行时不支持），
    现代码不得再引入 strict=。

## 9. 审查者陷阱（工具/框架/环境）

- **AppTest**：session_state 可迭代但无 .keys()；unkeyed widget
  set_value 不生效；无 at.file_uploader；主区 widget 先于 sidebar；
  radio options 换代时残留值隐式重置；at.query_params 可设（分享
  载入测试用）。
- **Streamlit**：expander 内交互 rerun 后收起；st.success 后立即
  st.rerun() 消息不可见（session 标志规避——**标志必须以新 result_id
  为键**，S4/U25 两次踩过）。
- **Python 版本**：`zip(strict=)` 是 3.10+ 特性，3.9 运行时 TypeError
  （U32 回滚的直接原因）；ruff target-version 升 py311 会激活 B905/
  B017 新规则（存量 13 处需同步处理）。
- **字符串手术**：多轮 .replace() 会因目标与文件实际内容不符**静默
  no-op**（本项目三轮踩过）——请用 Edit 工具精确锚定或 assert-guard。
- **环境**：`uv build` 前删 build/；.venv 是 py3.9.6；opencv-headless
  与 opencv-contrib 不可共存；mediapipe 1.0.x macOS 崩溃（钉 <1.0）。
- **monkeypatch 静态方法**：staticmethod 被替换为普通函数时签名不带
  self；模块级函数必须 patch 模块属性而非类属性。

## 10. 时间预算建议

- 30 分钟：跑通基线（§2）+ handoff §23 + 本文件 §6–§8。
- 3 小时：§4.A 交互面攻击（多轮分享循环、历史往返、CLI 并发）——
  本轮最高价值区。
- 2 小时：§4.B 对抗输入（JSON/token/DB/图片四类）。
- 2 小时：§4.C 领域新面（estimate_minutes 边界、帽子口径、egg+一体）。
- 1 小时：§4.D 安全面走查 + §4.E 测试真实性。
- 汇总：按 §0 格式输出 + 三档统计 + 与前两轮发现的重叠度自评。

---

*整理于 2026-08-29，对应 585 tests + 1 脚手架 / 16 轮演进。如与代码
不符，以代码为准。*
