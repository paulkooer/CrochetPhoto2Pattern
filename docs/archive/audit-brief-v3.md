# CrochetPhoto2Pattern 审核任务书 v3（第三次全面深审）

> v1（`audit-brief.md`）→ Opus 5 第一轮（F13–F22，已处置 handoff §22）
> → v2（`audit-brief-v2.md`）→ Opus 5 第二轮（F23–F36 + E1–E4，已处置
> handoff §24）→ 自审（U34–U36，已落地）→ **本文件 = 第三次全面深审**。
>
> 前两轮共 36 条发现全部处置，另有两批负面结果（v2 §5.F 八条 + 自审
> 四项探针）已记录。本轮的价值定位：**v2 落地了约 1200 行修复/新功能
> 代码——审查这些"修复本身"是否引入了新问题**，以及探入前两轮均未
> 深入的面。

---

## 0. 角色与产出要求

**角色**：第三次全面深审。与 v2 相同的六元组格式与硬性纪律（先复现、
先读 §5/§7、三档分类、严重度定义），补充以下第 6 条：

6. **每条发现标注"引入轮次"**——是 v2 修复（F23–F36/E 系列）引入的
   新 bug，还是一直存在但前两轮漏掉的？这直接决定下一轮修复的方向。

## 1. 系统一句话定位

照片 → Amigurumi 钩织图解生成器。GUI（Streamlit 三 Tab）+ CLI（单图/
目录批量并发）双形态。双解析路径（AI strict parse / 本地免费管线含
GrabCut+Otsu+姿态关键点）+ 手动输入 + 2D 网格。输出含逐圈 X/V/A 双语
对照、逐色材料（克重/米数/品牌色号）、自检门禁（代数+物理）、环形图+
符号条、SQLite 历史（缩略图/命名/搜索）、分享链接、PDF 打印导出。

## 2. 当前基线（先跑通再开始）

```bash
cd CrochetPhoto2Pattern
.venv/bin/python -m pytest -q --cov=app     # 586 passed + 1 skipped（eval 脚手架）
.venv/bin/python -m ruff check app tests    # 零告警
.venv/bin/python -m app.cli --head 9 --height 18 --out /tmp/t.json --quiet
```

环境事实（与前两轮的差异加粗）：
- Python 3.9.6（.venv）；requires-python = ">=3.9"（U32 升 3.11 曾尝试
  并回滚，handoff §23 有完整四步方案）
- 可选依赖：reportlab 已装；mediapipe 未装；**hypothesis 已装**（dev）
- **pyproject filterwarnings = ["error::UserWarning"]**（F35 落地——
  子集运行时如遇 numpy reload 警告可能升级为异常，全量运行已验证安全）
- **tests/conftest.py 存在**（F33 落地——autouse 清 Key/禁 load_dotenv/
  重定向 CROCHET_HISTORY_DB）
- CLI 三模式全通；批量目录模式带 ThreadPoolExecutor 并发

## 3. 模块地图（★ = v2 审查后新增或大幅修改的代码——本轮深审重点）

| 模块 | 行数 | 自 v2 以来的变更 | 优先级 |
|---|---|---|---|
| `models/crochet_params.py` | 908 | +bridge_rounds、+allow_wide_jump、+estimate_minutes（校准模型）、+F36 帽子口径统一、+T2 占位符过滤、+U23 模型升级 | ★★★ |
| `ui/result_renderer.py` | 585 | +分享入口 UI（F23）、+备份/导入 _BACKUP_KEYS、+快速调尺寸补 preview、+自检徽章、+逐色材料色样、+符号条/环形图、+历史命名/搜索、+E1 剥离 | ★★★ |
| `models/validator.py` | 72 | +物理边界检查（|Δ|≤6 + allow_wide_jump 白名单）——**全新文件** | ★★★ |
| `models/colors.py` | 344 | +CIEDE2000 标量→向量化、+pick_yarn_palette 直量化、+MST 肤色扩充、+品牌色号、+nearest_yarn_batch | ★★★ |
| `models/pose.py` | 206 | +模型 SHA256 校验、+FGD 下限 144、+span hints 进 prompt | ★★（43% 覆盖——最大盲区） |
| `utils/share.py` | 64 | +九键同构、+decode 门控（F29）、+_BACKUP_KEYS/_SHARE_KEYS 常量 | ★★ |
| `models/subject.py` | 209 | +FGD 下限 144（N-G 浅肤色修复）、+Otsu 钳位、+人脸框种子 | ★★ |
| `utils/history.py` | 170 | +title/preview 列、+幂等迁移、+搜索（! 转义）、+V5 校验 | ★★ |
| `cli.py` | 220 | +批量并发（ThreadPool+每图独立 orch）、+撞名消歧、+门禁 rc=2 | ★★ |
| `models/ring_chart.py` | 195 | +只标变化圈（F19）、+符号条（U7） | ★ |
| `models/grid_pattern.py` | 247 | +直量化色板、+C2C 逐行指令、+F28 钳制 | ★ |
| `ui/sidebar.py` | 159 | +历史缩略图/搜索/命名/占位、+V5 校验、+中转站 | ★ |
| `models/image_parser.py` | 439 | +strict parse、+脱敏（F14/F32）、+span hints、+批量等价 | ★ |
| `utils/pdf_export.py` | 156 | +全文 esc 转义、+密度行、+双语记号对照 | ★ |
| `models/local_vision.py` | 201 | +flare 主体范围内取窗 | ★ |
| `models/profile_shaping.py` | 199 | +线性插值、+strip_dome、+真实尺度 SVG | ★ |

## 4. 本轮深审重点

### A. v2 修复引入的回归（★★★——最高优先级）
前两轮修复了 36 条问题、落地了约 1200 行新代码。**修复本身是最容易
引入新 bug 的操作**（F35 的 filterwarnings 差点破坏子集运行就是预兆）：

- F36 帽子口径改只计筒壁 → 旧备份/分享 token 里的 height_cm 是旧口径
  （含帽顶）→ 导入后与新生成的部件混排时高度标注是否自洽？
- U23 时长模型改 6.5s/针 + 10s/圈 → 旧备份的 estimated_time_minutes
  与新计算的模型不一致 → refresh_derived 后会跳变——是否自洽？
- F30 搜索改用 `!` 转义符 → 用户搜索含 `!` 的标题（"时尚!"）是否
  正确按字面匹配？
- F28 网格钳制 → clamped_from 传给 GridPattern 但 share/备份是否
  序列化/恢复这个字段？
- F32 脱敏正则 `sk-[A-Za-z0-9_\-*]{4,}` 会不会误伤 URL 里的合法
  `sk-` 路径段或测试里的 fake key（`sk-ant-your-key-here`）？
- F33 conftest 清 Key + 禁 load_dotenv → 会不会影响测试中显式 setenv
  的用例（如 test_env_keys_default_to_ai_and_hide_mock 的 setenv 顺序）？

### B. 校准常量的合理性（★——所有阈值/系数/分档）
项目现在有 **30+ 个魔法数字/阈值/系数**，多数只有注释说明没有
实证数据。逐个审视：

| 常数 | 位置 | 当前值 | 质疑点 |
|---|---|---|---|
| SECONDS_PER_STITCH | crochet_params | 6.5 | 钩织速度因人/针法差异大；有无实际计时数据？ |
| SECONDS_PER_ROUND_OVERHEAD | crochet_params | 10 | 起头/记号扣/换线的真实固定开销？ |
| FGD 下限 | subject.py | 144 | 浅肤色 vs 白背景 184 是唯一数据点；深肤色/深背景？ |
| Otsu 钳位上限 | subject.py | 96 | 为什么 96？高对比图 Otsu t=200+ 会被钳——是否该放宽？ |
| 覆盖率门槛 | subject.py | 15% | 头部只占条带 7% 被吞——7%~15% 之间的主体色会怎样？ |
| MIN_SUBJECT_FRAC | subject.py | 0.05/0.95 | 主体占 3% 的小图（远景）会被拒——合理？ |
| 1% 长尾剔除 | colors.py | 0.01 | 均匀多色图案（如渐变）会被剔成几色？ |
| 品牌色号下限 | crochet_params | 5g/色 | 单色 <5g 的配件被强制提升到 5g——误导？ |
| MINUTES_PER_ROUND | crochet_params | 2.5 | 仅为锚点保留——是否还有引用？ |
| HAT_DEPTH_RATIO | crochet_params | 0.6 | 帽深/帽径比=0.6 的来源？ |
| BODY_HEAD_RATIO | crochet_params | 1.0 | 身体直径=头径的 Q 版假设 |
| LIMB_HEAD_RATIO | crochet_params | 0.33 | 四肢直径=头径 1/3 |
| F25 title 长度 | history.py | 无限制 | title 存 100KB 文本进 SQLite？ |
| 历史上限 | history.py | 30 | list_results LIMIT 30——够用？ |

### C. CLI 批量并发的深入（★——v2 落地的新并发代码）
- ThreadPoolExecutor(max_workers=4)：GrabCut 在 cv2 内部释放 GIL——
  4 worker 并发跑 GrabCut 时 numpy/cv2 的线程池是否会竞争？
- 每图独立 orchestrator 确认隔离了 parser 状态，但 **estimate_minutes/
  bridge_rounds/validate_pattern 是模块级函数**——线程安全吗？
- 批量模式 --out 缺省打印到 stdout：6 张图时 stdout 会输出 6 份 JSON
  混杂——行为是否符合预期？
- --batch-dir 与 --image 同时给时 argparse 互斥组的处理是否正确？

### D. pose.py 43% 覆盖（最大覆盖盲区）
`model_path()` 的 SHA256 校验、`get_body_landmarks` 的 mediapipe 调用、
`format_span_hints` 的注入进 prompt——这些分支在 mediapipe 未装时
全部走 ImportError 回退，**从未被正向测试过**。审查：
- SHA256 校验逻辑的正确性（竞态：tmp.replace(path) 是否原子？）
- format_span_hints 注入 prompt 的格式是否会被 LLM 误读？
- _MIN_VISIBILITY=0.5 的可见性阈值是否有 mediapipe 文档依据？

### E. CIEDE2000 向量化的边界
- `ciede2000_vec` 的 pairwise=None 自动判——哪些调用方可能误判？
- `_srgb_to_lab_vec` 的 f(t) 分支：`np.clip(x, 1e-12, None)` 在 t=0
  时行为与标量版 `t ** (1/3)`（0 的立方根 = 0）是否一致？
- 品牌色号 ΔE00≤10 的门槛（Opus 5 提出但未验证）——"蓝色 113 近似"
  的实际 ΔE 值是多少？

### F. 文档一致性（v3 新增面——16 轮 × 多份文档）
- handoff-review.md 现有 24 个 §，**内交叉引用是否自洽**？
- audit-brief.md（v1）/ audit-brief-v2.md / audit-brief-v3.md（本文件）
  / optimization-brief.md 四份文档间的"已实现清单"是否一致？
- README 功能清单逐条对照实现（14 轮的快速迭代极容易遗漏更新）。

## 5. 发现清单（第三次全面深审 · Opus 5 · 2026-08-29/30）

### 5.0 基线复现结果

```
.venv/bin/python -m pytest -q          → 586 passed, 1 skipped   ✅ 与 §2 一致
.venv/bin/python -m ruff check app tests → All checks passed!     ✅
.venv/bin/python -m app.cli --head 9 --height 18 --out /tmp/t.json --quiet → rc=0 ✅
```

环境事实核对：Python 3.9.6 / reportlab 5.0.1 ✅ / mediapipe 未装 ✅ /
hypothesis 6.141.1 ✅ / openai 2.48.0 / anthropic 0.122.0 / numpy 2.0.2。
§2 声称的"子集运行可能因 numpy reload 警告升级为异常"——**实测 7 个子集
全通过**（见 §5.F-6），该顾虑不成立。

**§3 模块行数核对**：16 项中 15 项精确相符，唯 `ui/sidebar.py` 任务书写
137 实为 **159**（G9）。

**分档统计**：10 条 bug/文档失实 + 3 条取舍 + 1 条增强。

| 严重度 | 条数 | 编号 |
|---|---|---|
| blocker | 0 | — |
| high | 2 | G1 G2 |
| medium | 3 | G3 G4 G8 |
| low | 5 | G5 G6 G7 G9 G10 |

**引入轮次分布（§0.6 硬性要求）**

| 引入轮次 | 条数 | 编号 |
|---|---|---|
| **v2 修复引入的新问题**（F23–F36/E 系列的修复本身） | **7** | G1 G3 G5 G6 G7 G8 G10 |
| 一直存在、前两轮漏掉 | 3 | G2 G4 G9 |

**这是本轮最重要的结论**：7/10 出自 v2 的修复代码，且**其中 4 条是同一
种病**——修复只落地了一半（G1 写侧修了读侧没修、G3 钳制修了提示没修、
G6 三个出口修了两个、G8 承诺的回归断言从未写）。§4.A 的假设
（"修复本身是最容易引入新 bug 的操作"）被完全证实，而且比预期更严重：
G1 让 F24 的**用户可见症状原样复现**，等于 F24 实际没修。

**区域分布**

| 区域 | 条数 |
|---|---|
| §4.A v2 修复引入的回归 | 6（G1 G3 G5 G6 G8 G10） |
| §4.B 校准常量 | 1（G2） |
| §4.C CLI 批量并发 | 1（G7） |
| §4.D pose 覆盖盲区 | 0（见 §5.F-4） |
| §4.E CIEDE2000 边界 | 0（见 §5.F-5，另 T3） |
| §4.F 文档一致性 | 1（G9） |
| 领域正确性（跨面） | 1（G4） |

---

### 5.A v2 修复引入的回归（§4.A）

```
[high] G1 — F24 只修了写侧：备份导入把 8 个非核心键全部写成 None，egg→ladder 原样复现
```

**位置**: `app/ui/result_renderer.py:576-577`（`for k in _BACKUP_KEYS: imported.setdefault(k, None)`）·
`:568-573`（`imported` 只放 4 键）· 对照已修好的写侧 `:491-495` 与分享接收侧
`app/main.py:47-49`

**类别**: bug（领域错误，静默）· **引入轮次：v2 修复引入（F24 的读侧从未落地）**

**证据**（`data` 里明明有这 8 个键，`setdefault` 却在给"已经不存在"的键填
None——因为 `imported` 里压根没先从 `data` 取过它们）：

```bash
.venv/bin/python - <<'PY'
import json, sys, uuid; sys.path.insert(0, '.')
from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import Gauge, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis
from app.ui.result_renderer import _rebuild_params, _validated_backup
from app.utils.share import _BACKUP_KEYS

a = ImageAnalysis(body_type="标准", head_diameter_cm=9.0, height_cm=18.0,
                  main_features=[], pose="站立", difficulty="easy",
                  parts=["头部", "身体", "腿部"])
s = StructureDesigner.design_3d_structure(a)
g, style = Gauge(20.0, 24.0), ShapingStyle("egg", True, "attached", True)
params = CrochetParamsGenerator.generate_params(a, s, gauge=g, style=style)
print("① 生成（蛋形头+头身一体）部件 =", [p.name for p in params["parts"]])

result = {"analysis": a.model_dump(), "structure": s, "params": params,
          "style": {"sphere_mode":"egg","one_piece":True,
                    "skirt_style":"attached","ruffle_hem":True},
          "gauge": {"stitches_per_10cm":20.0,"rows_per_10cm":24.0},
          "color_bands": [{"start":0.0,"end":1.0,"color":"红色"}],
          "spans": {"身体":[0.3,0.7]}, "spans_measured": ["身体"],
          "vision_meta": {"source":"openai"}, "preview": "data:png;base64,xx",
          "usage": {"input_tokens": 5}, "result_id": "r0"}

# ── result_renderer.py:491-495 原样（F24 已修的写侧）──
sp = json.loads(json.dumps(params, default=lambda o: o.model_dump(), ensure_ascii=False))
backup = json.dumps({k: (sp if k == "params" else result.get(k))
                     for k in _BACKUP_KEYS}, ensure_ascii=False)
print("② 备份文件顶层键 =", sorted(json.loads(backup)))

# ── result_renderer.py:563-578 原样（读侧）──
data = json.loads(backup)
an, stc = _validated_backup(data)
imported = {"analysis": an, "structure": stc,
            "params": _rebuild_params(dict(data["params"])),
            "result_id": uuid.uuid4().hex[:12]}
for k in _BACKUP_KEYS:
    imported.setdefault(k, None)
for k in _BACKUP_KEYS:
    if k in ("analysis","structure","params"): continue
    print(f"     {k:16} 备份里={str(data.get(k))[:34]:36} 导入后={imported[k]}")

_st_def = {"sphere_mode": "ladder", "one_piece": False,
           "skirt_style": "ring", "ruffle_hem": False}
_style = ShapingStyle(**{**_st_def, **(imported.get("style") or {})})
print("③ 调尺寸用的 style =", _style)
assert _style.sphere_mode == "egg", f"❌ egg → {_style.sphere_mode}"
PY
```

实测输出：

```
① 生成（蛋形头+头身一体）部件 = ['头身（一体）', '腿部']
② 备份文件顶层键 = ['analysis','color_bands','gauge','params','preview',
                    'spans','spans_measured','structure','style','usage','vision_meta']
     style            备份里={'sphere_mode': 'egg', 'one_pie  导入后=None
     gauge            备份里={'stitches_per_10cm': 20.0, 'ro  导入后=None
     color_bands      备份里=[{'start': 0.0, 'end': 1.0, 'co  导入后=None
     spans            备份里={'身体': [0.3, 0.7]}               导入后=None
     spans_measured   备份里=['身体']                           导入后=None
     vision_meta      备份里={'source': 'openai'}             导入后=None
     preview          备份里=data:png;base64,xx               导入后=None
     usage            备份里={'input_tokens': 5}              导入后=None
③ 调尺寸用的 style = ShapingStyle(sphere_mode='ladder', one_piece=False, ...)
AssertionError: ❌ egg → ladder
```

端到端 AppTest 复现（真实点「导入并替换当前结果」按钮，并与**正确**的分享
token 路径对照）：

```bash
.venv/bin/python - <<'PY'
import json, os, sys, tempfile
os.environ['CROCHET_HISTORY_DB'] = os.path.join(tempfile.mkdtemp(), 'h.db')
sys.path.insert(0, '.')
from streamlit.testing.v1 import AppTest
from app.utils.share import encode_result, _BACKUP_KEYS
from tests.test_app_smoke import _mock_result
r = _mock_result('e2e-1')
r["style"] = {"sphere_mode":"egg","one_piece":False,"skirt_style":"ring","ruffle_hem":True}
r["gauge"] = {"stitches_per_10cm":20.0,"rows_per_10cm":24.0}
r["spans"] = {"身体":[0.3,0.7]}; r["spans_measured"] = ["身体"]
r["vision_meta"] = {"source":"openai","note":"x"}
r["color_bands"] = [{"start":0.0,"end":1.0,"color":"红色"}]

at = AppTest.from_file('app/main.py', default_timeout=120)
at.query_params['p'] = encode_result(r); at.run()
print("A) 分享 token 载入 → style =", at.session_state['result'].get('style'))

at2 = AppTest.from_file('app/main.py', default_timeout=120); at2.run()
at2.session_state['result'] = r; at2.run()
sp = json.loads(json.dumps(r["params"], default=lambda o: o.model_dump(), ensure_ascii=False))
backup = json.dumps({k: (sp if k=="params" else r.get(k)) for k in _BACKUP_KEYS},
                    ensure_ascii=False)
[t for t in at2.text_area if t.key and t.key.startswith('import_')][0].set_value(backup).run()
[b for b in at2.button if b.key and b.key.startswith('importbtn_')][0].click().run()
res = at2.session_state['result']
print("B) 备份导入   → " + "  ".join(
    f"{k}={res.get(k)}" for k in ("style","gauge","spans","vision_meta")))
print("   异常:", at2.exception[0].value.splitlines()[0] if at2.exception else "无")
PY
```

实测输出：

```
A) 分享 token 载入 → style = {'sphere_mode': 'egg', 'one_piece': False,
                              'skirt_style': 'ring', 'ruffle_hem': True}
B) 备份导入   → style=None  gauge=None  spans=None  vision_meta=None
   异常: 无
```

**影响**: **F24 判定为"已处置"，但它的用户可见症状 100% 原样复现**——用户
备份 → 换会话导入 → 点「📐 按新尺寸重新生成」，免缝合的一体件变回要缝头的
两件、蛋形头退回阶梯球、波浪裙摆消失、照片配色退回先验、实测分段失效，
全程无提示。区别只在于：v2 之前是"备份文件里没有这些数据"，v2 之后是
"备份文件里有，导入时被主动丢掉"——数据完整地躺在用户的 JSON 里，只差
一行代码就能读回来。同时 `vision_meta=None` 让结果页的解析来源标注
（`:154-166`）与用量（`:146`）在导入后一并消失。分享 token 路径
（`main.py:47-49` 整份 `_shared` 入 session）**是对的**，两条同源路径再次分叉。

**建议**: 把 `setdefault(None)` 改成从 `data` 取值——一行：

```python
# result_renderer.py:576-577
for k in _BACKUP_KEYS:
    imported.setdefault(k, data.get(k))     # ← 旧备份缺键自然得 None
```

并**补上 G8 里那条从未写过的断言**（否则下一轮还会退化）：

```python
def test_backup_roundtrip_preserves_all_keys():
    """备份 → 导入 后，_BACKUP_KEYS 每一键都必须与备份内容相等。"""
    ...
    for k in _BACKUP_KEYS:
        assert imported[k] == json.loads(backup)[k], f"导入丢键: {k}"
```

---

```
[high] G2 — GrabCut 掩码可以整块丢掉头部却通过 5%/95% 退化门：逐圈配色静默退化为单色
```

**位置**: `app/models/subject.py:203-205`（唯一的掩码 sanity check 是**总面积**
占比 `[0.05, 0.95]`）· 消费方 `app/models/color_design.py:84-85`、
`app/models/image_parser.py:94-95`、`app/models/local_vision.py:73-74`（三处都
"拿到掩码就无条件信任"）

**类别**: bug（领域错误，静默降级）· **引入轮次：一直存在（GrabCut 引入以来），
前两轮漏掉**——v2 §5.F-4 测了八类**对抗图片**确认"安全降级"，但没测
**普通图片下掩码本身是否正确**；§4.B 点名了 FGD 下限/Otsu 钳位/覆盖率三个
常数，真正的洞却不在任何单个常数上（见下方反证）

**证据**（把背景灰阶从 250 调到 246——肉眼无差别的 1.5% 明度变化——逐圈配色
从 3 色塌成 1 色）：

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, '.')
import numpy as np
from PIL import Image, ImageDraw
from app.models import color_design as CD
from app.models import subject as S

def synth(bgv, noise=0, grad=False, w=200, h=320, seed=0):
    img = Image.new("RGB", (w, h), (bgv, bgv, bgv))
    if grad:                                  # 真实照片的柔和光照梯度
        a = np.asarray(img).astype(np.int16)
        a += np.linspace(-8, 8, h).astype(np.int16)[:, None, None]
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img); cx, cy, r = w // 2, int(h * 0.14), 30
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(245, 194, 158))       # 浅肤色头
    d.rounded_rectangle([cx-20, cy+r, cx+20, int(h*0.92)], radius=8,
                        fill=(0, 120, 215))                          # 蓝身体
    if noise:
        rng = np.random.default_rng(seed); a = np.asarray(img).astype(np.int16)
        a += rng.integers(-noise, noise+1, a.shape, dtype=np.int16)
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return img

def bands(img, no_mask=False):
    if no_mask:                               # 强制走"无掩码"启发式回退
        orig = S.extract_subject; S.extract_subject = lambda *a, **k: None
        try: return [b['color'] for b in CD.vertical_color_bands(img)]
        finally: S.extract_subject = orig
    return [b['color'] for b in CD.vertical_color_bands(img)]

print(f"{'背景':>5}{'噪声':>5}{'渐变':>6} | {'掩码占比':>8}{'头部命中':>8}  "
      f"{'掩码路径色带':<30}{'无掩码回退色带':<32}")
for bgv, noise, grad in ((255,0,False),(250,0,False),(246,0,False),(240,0,False),
                         (240,6,False),(240,6,True),(230,10,True),(205,8,True)):
    img = synth(bgv, noise, grad)
    res = S.extract_subject(img, max_side=160)
    frac = "None" if res is None else f"{res[0].mean():.3f}"
    hit = "—" if res is None else f"{res[0][:int(res[0].shape[0]*0.25)].mean():.2f}"
    bm, bn = bands(img), bands(img, no_mask=True)
    star = " ★掩码更差" if len(bn) > len(bm) else ""
    print(f"{bgv:>5}{noise:>5}{str(grad):>6} | {frac:>8}{hit:>8}  "
          f"{str(bm):<30}{str(bn):<32}{star}")
print(f"\n退化门槛 = [{S._MIN_SUBJECT_FRAC}, {S._MAX_SUBJECT_FRAC}]（只看总面积）")
PY
```

实测输出：

```
   背景   噪声    渐变 |     掩码占比    头部命中  掩码路径色带                  无掩码回退色带
  255    0 False |    0.160    0.14  ['浅肤色','钢蓝色','蓝色']    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差
  250    0 False |    0.160    0.14  ['浅肤色','钢蓝色','蓝色']    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差
  246    0 False |    0.129    0.01  ['蓝色']                    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差
  240    0 False |    0.129    0.01  ['蓝色']                    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差
  240    6 False |    0.161    0.14  ['浅肤色','钢蓝色','蓝色']    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差
  240    6  True |    0.128    0.01  ['蓝色']                    ['浅肤色','钢蓝色','蓝色','灰色']   ★掩码更差
  230   10  True |    0.128    0.01  ['蓝色']                    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差
  205    8  True |    0.128    0.01  ['蓝色']                    ['浅肤色','钢蓝色','蓝色','钢蓝色'] ★掩码更差

退化门槛 = [0.05, 0.95]（只看总面积）
```

推理链（三步，每步都可独立复算）：

1. **头部被整块吞掉**：头部条带命中率从 0.14 掉到 0.01（头椭圆面积 ≈ 条带
   面积的 17%，0.14 = 基本完整，0.01 = 一个像素都没剩）。
2. **退化门看不见**：丢头掩码的总占比 **0.128**，与正常掩码的 0.161 只差
   20%，稳稳落在 `[0.05, 0.95]` 内——`subject.py:203` 的门是**面积门**，
   对"面积对、区域错"完全无感。
3. **下游静默塌成单色**：`vertical_color_bands` 只统计掩码内像素，头没了
   就只剩身体色 → 逐圈配色从 3 段变 1 段。而**同一张图走无掩码回退反而
   给出 4 段正确色带**——8 个组合里掩码路径无一次优于回退，4 次严重更差。

**反证（我先怀疑过 `_FGD_FLOOR=144` 是元凶，已排除，不要照这个方向修）**：

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from app.models import subject as S
# ... 同上 synth/bands ...
for floor in (144, 120, 96, 64):
    S._FGD_FLOOR = floor
    # 逐个背景灰阶重跑
"
# _FGD_FLOOR=144 → 255:✅  250:✅  240:❌  220:❌  200:❌
# _FGD_FLOOR=120 → 255:✅  250:✅  240:❌  220:❌  200:❌
# _FGD_FLOOR= 96 → 255:✅  250:✅  240:❌  220:❌  200:❌
# _FGD_FLOOR= 64 → 255:✅  250:✅  240:❌  220:❌  200:❌   ← 降门槛完全无效
```

进一步 instrument 证明**种子推导对 250/246/240 几乎完全一致**（背景代表色
都是 `[248,248,248]`（16 级量化把 240–255 归为同桶）、`t_seed` 都是 96、
`_fgd_t` 都是 144、头部区拿到 `GC_FGD` 的像素数 87/72/68）。**翻盘发生在
GrabCut 的 GMM+图割内部**——它正好坐在决策边界上，与主体断开的头部块被
数据项整体判回背景。所以这**不是常数标定问题，是缺少区域级 sanity
check**：§4.B 表里的 FGD 下限 144 / Otsu 钳位 96 / 覆盖率 15% 三项经此实测
**均无需改动**（见 §5.F-2）。

**影响**: README 首屏卖点「🎨 照片配色设计：纵向色带映射到逐圈毛线色，自动
生成换线说明」在**普通浅灰/米色背景 + 柔和光照梯度**（影棚灰、阴天白墙、
木地板暖调——照片里最常见的几种底）下**静默退化为整件单色**，用户拿到的
图解没有任何"配色未能提取"的提示，只会以为"这张照片就是单色的"。同时
`recommended_colors` 丢掉肤色（实测 `['蓝色','浅肤色']` → `['蓝色']`），
`extract_color_palette` 的"主体像素统计"退化为"衣服像素统计"。
本应用的主要用途是**给玩偶/毛绒/宠物照片出图解**，这类照片 haar 人脸检测
基本不命中（唯一的救回通道 `subject.py:183-187` 人脸框种子失效——机制本身
有效，实测强制注入人脸框后头部命中率回到 0.14），因此实际命中率比人像照更高。

**建议**: 加**区域级**校验，而不是调常数。最小改动是在 `extract_subject`
返回前做一次"上部条带必须有主体"的检查，失败即返回 `None` 走回退：

```python
# subject.py:203 之后追加
top = subject[:max(1, int(h * 0.25))]
if top.mean() < 0.02:            # 上 1/4 几乎无主体 = 头被吞（旋转体玩偶必有头）
    logger.debug("GrabCut 掩码上部为空（疑似丢失头部），回退启发式")
    return None
```

更稳的做法是让 `extract_subject` 一并返回置信度 meta，`vertical_color_bands`
在"掩码色段数 < 回退色段数"时择优（实测回退路径在 8/8 组合里都不更差），
并在结果页 `vision_meta` 里诚实标注"主体分割置信度低，配色按全图估算"。
另建议把这 8 个组合固化成回归矩阵——它是目前唯一能覆盖"掩码正确性"
（而非"不崩溃"）的测试面，§7.1「视觉管线验证几乎全在合成图上」的严重度
应因此**上调**：合成图不只是"覆盖不足"，它连已有的合成图都没验过正确性。

---

### 5.B 中等严重度

```
[medium] G3 — F28 的「已钳制」提示是死代码：grid_view 从不写 clamped_from，300,000 行被静默压成 2,000 行
```

**位置**: `app/ui/tab_grid.py:76-85`（`st.session_state.grid_view` 的字面键集
**不含** `clamped_from`）· `:89-91`（`view.get("clamped_from")` 恒为 None →
`_clamp_note` 恒为空串）· 数据源 `app/models/grid_pattern.py:77-80`（钳制本身
正确）、`:29`（`GridPattern.clamped_from` 字段正确）

**类别**: bug（静默数据截断）· **引入轮次：v2 修复引入（F28 的 UI 半边从未接线）**

**证据**:

```bash
.venv/bin/python - <<'PY'
import re, sys; sys.path.insert(0, '.')
from PIL import Image
from app.models.grid_pattern import generate_grid_pattern

p = generate_grid_pattern(Image.new("RGB", (1, 10000), (200, 150, 120)), grid_width=40)
print(f"① 模型层：1×10000 图 → 网格 {p.width}×{p.height}，clamped_from={p.clamped_from}"
      f"（压缩 {p.clamped_from // p.height}×）")

src = open('app/ui/tab_grid.py').read()
body = src.split("st.session_state.grid_view = {")[1].split("}")[0]
keys = re.findall(r'"(\w+)":', body)
print("② UI 层写入 grid_view 的键 =", keys)
print("   含 clamped_from ?", "clamped_from" in keys)
print("③ clamped_from 在 tab_grid.py 的全部出现位置（只有读、没有写）：")
for i, line in enumerate(src.splitlines(), 1):
    if "clamped_from" in line:
        print(f"     :{i}  {line.strip()}")
view = {k: None for k in keys}
print("④ 实测 _clamp_note =", repr("（有提示）" if view.get("clamped_from") else ""))
PY
```

实测输出：

```
① 模型层：1×10000 图 → 网格 40×2000，clamped_from=300000（压缩 150×）
② UI 层写入 grid_view 的键 = ['width','height','n_colors','svg','legend',
                              'legend_html','chart','c2c']
   含 clamped_from ? False
③ clamped_from 在 tab_grid.py 的全部出现位置（只有读、没有写）：
     :89  _clamp_note = (f"（原始比例需 {view['clamped_from']:,} 行，已达单元上限，"
     :91  if view.get("clamped_from") else "")
④ 实测 _clamp_note = ''
```

**影响**: F28 报告的建议原文是"这比静默截断可靠"——结果**恰恰仍是静默截断**。
用户上传细长图（拼接长图、进度条截图、条幅），拿到的是纵向被压缩 150× 的
网格（40×2000 而非 40×300000），`st.success` 只说「✅ 网格大小：40 列 ×
2000 行，6 种颜色」，完全不提比例已被改写；照着钩出来会是一个完全不同形状
的图案。F28 的 OOM 风险确实被消除了（这半边有效），但它换来的是一种**新的
静默错误**：图案比例失真且不告知。`:89-91` 的整段提示代码是不可达分支
（ruff/覆盖率都发现不了——它是"永远走 else"而非语法死码）。

**建议**: `tab_grid.py:76` 的字典补一行，与 F28 建议的原意对齐：

```python
st.session_state.grid_view = {
    "width": pattern.width,
    "height": pattern.height,
    "clamped_from": pattern.clamped_from,     # ← 补这一行
    ...
```

并加一条断言把这类"写侧漏键"钉死（与 G1/G8 同一根因）：
`assert set(grid_view) >= {"clamped_from"}`，或更好——直接断言
`grid_view` 的键集覆盖 `_clamp_note` 与后续渲染读取的全部键。

---

```
[medium] G4 — 高度口径双标：同一部件在 §2 结构表与 §3 图解里给出两个高度，最大差 +140%
```

**位置**: `app/models/crochet_params.py:525-526`（裙子：圈数预算发给
`flare+straight`，**不含腰部起针圈**）· `:561`（`actual_h = len(rounds_raw) ×
row_h`，**含**腰部起针圈）· `:656` + `:661`（圆柱：预算 `body_r`，计数含
`_cylinder_rounds` 尾部 2 圈收针）· 显示侧 `app/ui/result_renderer.py:229-235`
（§2 结构表显示 `structure` 的目标高）vs `:343-344`/`app/utils/pdf_export.py:112`
（§3 显示 `params` 的标注高）

**类别**: bug（领域错误 / 显示不自洽）· **引入轮次：一直存在（裙子自 F1、
圆柱自更早），前两轮漏掉**——F36 统一了帽子口径，但没有人比对过
"structure 目标高 ↔ params 标注高"这一对

**证据一（同屏两个数字，跨密度×尺寸全量扫描）**:

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, '.')
from app.models.crochet_params import CrochetParamsGenerator
from app.models.gauge import PRESETS, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis
worst = []
for gname, g in PRESETS.items():
    for head, height in ((9.0,18.0),(6.0,12.0),(14.0,30.0),(20.0,50.0)):
        a = ImageAnalysis(body_type="标准", head_diameter_cm=head, height_cm=height,
                          main_features=[], pose="站立", difficulty="easy",
                          parts=["头部","身体","腿部","裙子","帽子"])
        s = StructureDesigner.design_3d_structure(a)
        p = CrochetParamsGenerator.generate_params(a, s, gauge=g, style=ShapingStyle())
        sd = {x["name"]: x for x in s["parts"]}
        for part in p["parts"]:
            tgt = sd.get(part.name, {}).get("height_cm") or sd.get(part.name, {}).get("length_cm")
            if tgt is None or part.height_cm is None: continue
            rel = (part.height_cm - tgt) / tgt * 100
            worst.append((abs(rel), gname, head, height, part.name, tgt, part.height_cm))
print("相对差 >15% 的组合（共 %d / %d 组）：" % (sum(1 for w in worst if w[0] > 15), len(worst)))
for w in sorted(worst, reverse=True)[:8]:
    print(f"  {w[1]:>8} 头{w[2]}/高{w[3]}  {w[4]}: §2 结构表 {w[5]}cm → §3 图解 {w[6]}cm （+{w[0]:.0f}%）")
PY
```

实测输出：

```
相对差 >15% 的组合（共 24 / 36 组）：
       dk 头6.0/高12.0  裙子: §2 结构表 1.5cm → §3 图解 3.6cm （+140%）
     fine 头6.0/高12.0  裙子: §2 结构表 1.5cm → §3 图解 3.1cm （+107%）
     fine 头9.0/高18.0  裙子: §2 结构表 2.2cm → §3 图解 3.8cm （+73%）
  classic 头6.0/高12.0  裙子: §2 结构表 1.5cm → §3 图解 2.5cm （+67%）
       dk 头9.0/高18.0  裙子: §2 结构表 2.2cm → §3 图解 3.6cm （+64%）
     fine 头6.0/高12.0  身体: §2 结构表 3.0cm → §3 图解 4.4cm （+47%）
  classic 头6.0/高12.0  身体: §2 结构表 3.0cm → §3 图解 4.4cm （+47%）
       dk 头6.0/高12.0  身体: §2 结构表 3.0cm → §3 图解 4.3cm （+43%）
```

**证据二（把偏差拆成两个可独立复算的成因）**:

裙子——`总圈数 = 1 + 圈数预算`（腰部起针圈没进预算），且 `flare+2` 下限
在小玩偶上直接压过高度预算：

```bash
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, '.')
from app.models.crochet_params import (CrochetParamsGenerator, _stitches_for_diameter,
                                       BODY_HEAD_RATIO, SKIRT_BODY_RATIO)
from app.models.gauge import PRESETS, ShapingStyle
from app.models.structure_designer import StructureDesigner
from app.schemas import ImageAnalysis
for gname, g in PRESETS.items():
    for head, height in ((6.0,12.0),(9.0,18.0),(20.0,50.0)):
        a = ImageAnalysis(body_type="标准", head_diameter_cm=head, height_cm=height,
                          main_features=[], pose="站立", difficulty="easy",
                          parts=["身体","裙子"])
        s = StructureDesigner.design_3d_structure(a)
        length = [x for x in s["parts"] if x["name"]=="裙子"][0]["height_cm"]
        waist = _stitches_for_diameter(head*BODY_HEAD_RATIO, g)
        hem = _stitches_for_diameter(head*BODY_HEAD_RATIO*SKIRT_BODY_RATIO, g)
        flare = max(0, (hem-waist)//6)
        budget = max(flare+2, g.rounds_for_height(length))     # :525
        p = CrochetParamsGenerator.generate_params(a, s, gauge=g, style=ShapingStyle())
        n = len(next(x for x in p["parts"] if x.name=="裙子").rounds)
        assert n == 1 + budget, "off-by-one 假设不成立"
        print(f"  {gname:>8} 头{head:>4} 目标{length:>4}cm  预算{budget:>3}圈"
              f"(flare下限 {flare+2}, 高度需求 {g.rounds_for_height(length)})"
              f"  实际{n:>3}圈 = 1+预算  ✓")
print("→ 全 9 组均满足 实际圈数 = 1 + 圈数预算")
PY
```

实测输出（节选）：

```
   classic 头 6.0 目标 1.5cm  预算  3圈(flare下限 3, 高度需求 2)  实际  4圈 = 1+预算  ✓
        dk 头 6.0 目标 1.5cm  预算  4圈(flare下限 4, 高度需求 2)  实际  5圈 = 1+预算  ✓
      fine 头 9.0 目标 2.2cm  预算  5圈(flare下限 5, 高度需求 3)  实际  6圈 = 1+预算  ✓
→ 全 9 组均满足 实际圈数 = 1 + 圈数预算
```

圆柱（身体/腿部/手臂）——轴向计数恒为 `预算 + 2`（`_cylinder_rounds` 尾部
2 圈收针计入标注高度、不计入预算）：

```
 classic 头 9.0/高18.0 | 身体 目标 4.5  预算 body_r=7  轴向计数 9  +2  标注 5.6cm
 classic 头20.0/高50.0 | 身体 目标15.0  预算 body_r=24 轴向计数 26 +2  标注16.2cm
      dk 头 9.0/高18.0 | 腿部 目标 3.6  预算 body_r=5  轴向计数 7  +2  标注 5.0cm
```

**影响**: 用户在同一页上看到同一个部件的两个高度：§2「立体结构设计」表里
「裙子 · 高 1.5cm」，§3 图解与 PDF/Markdown 里「高度/长度 3.6cm」，notes 还
写「实际高约 3.6cm」。小玩偶（头 6cm）的裙子实际是设计目标的 **2.4 倍**，
按 §2 的比例预期做出来的玩偶下摆会长过腿。这**不是** §8.6 的重复
（§8.6 讲的是"起底盘不该计入轴向高度"，本条讲的是"圈数预算与圈数计数用了
两套边界"）——`params` 侧的 `actual_h` 是**对的**（它确实等于钩出来的高度），
错的是**预算没按同一边界算**，于是 `structure` 的目标从未被满足，而两个数字
都摆在用户面前。

**建议**: 让预算与计数用同一边界，两处各一行：

```python
# crochet_params.py:525-526  裙子：预算包含腰部起针圈
total_target = max(flare + 2, gauge.rounds_for_height(length))
straight = max(1, total_target - flare - 1)      # ← 减去腰部起针圈

# crochet_params.py:656  圆柱：预算扣掉尾部 2 圈收针
body_r = max(4, gauge.rounds_for_height(height) - 2)
```

并加一条回归断言把口径钉住（这类"两套边界"最容易复发）：
`assert abs(part.height_cm - structure_target) <= gauge.row_h_cm`（允许 1 圈
量化误差）。若判定"实际高度优先、结构表只是设计意图"是刻意取舍，则必须
**改显示**：§2 表头改成「设计目标尺寸」、§3 保留「实际钩出尺寸」，并在偏差
超 1 圈时给一句 caption 说明为何不同——现在两个数字并列且都没标签，用户
无从判断该信哪个。

---

```
[medium] G8 — v2 承诺"把漂移钉死在结构层"的那条断言从未写：share.py 注释指向不存在的测试文件
```

**位置**: `app/utils/share.py:25`（注释 `键集相等断言见 tests/test_round16.py::test_result_key_sets_consistent`）·
`tests/` 目录下**无 test_round16.py**

**类别**: 文档失实 + 可维护性（缺失的回归防线）· **引入轮次：v2 修复引入**

**证据**:

```bash
grep -rn "test_round16" app/ tests/ docs/
#   app/utils/share.py:25:# tests/test_round16.py::test_result_key_sets_consistent。
ls tests/ | grep round
#   test_round12.py
#   test_round14.py
#   test_round15.py          ← 没有 test_round16.py

grep -rn "_BACKUP_KEYS\|_SHARE_KEYS" tests/
#   （无输出——全部测试文件里零引用）
```

**影响**: v2 §5.H 的收尾结论是"建议把『共用键集常量 + 一条断言各路径键集
相等的回归测试』作为本轮修复的第一优先，其价值高于逐条修 F24/F26"——常量
做了，**断言没做**，注释却已经按"做了"的口径写进源码。直接后果就是 G1：
读侧写错了一行，586 条测试全绿，注释还在告诉下一位维护者"这里有断言保护"。
同类"写侧漏键"的 G3 也是同一个缺口漏过去的。这条本身不改变运行时行为，
但它是 G1/G3 能存在的**结构性原因**，所以给 medium 而非 low。

顺带核实：`_BACKUP_KEYS`（11 键）与 `orchestrator.run_full_pipeline` 的返回
键集（`orchestrator.py:134-157`，11 键）确实一致 ✅；但**生产方仍在各自手抄**
——`tab_manual.py:49-60` 只写 6 键（缺 gauge/spans/spans_measured/vision_meta/
usage/preview）、`cli.py:97-105` 写 11 键。这些缺键目前都被消费侧的
`or {}` / `or []` 兜住，**无用户可见影响**，但"单一事实来源"只在消费侧成立。

**建议**: 补上那条断言，并把范围扩到生产方与往返：

```python
# tests/test_round16.py
from app.utils.share import _BACKUP_KEYS, _SHARE_KEYS

def test_share_keys_are_backup_minus_preview():
    assert set(_SHARE_KEYS) == set(_BACKUP_KEYS) - {"preview"}

def test_orchestrator_produces_every_backup_key():
    result = ...  # local_vision=True 跑一次
    assert set(_BACKUP_KEYS) - {"params"} <= set(result)

def test_backup_roundtrip_preserves_all_keys():   # ← 会直接抓住 G1
    ...
```

若不打算写，最低要求是**删掉 share.py:25 那行注释**——留着比没有更糟。

---

### 5.C 低严重度

```
[low] G5 — F33 的 conftest 把历史库指到相对路径：每次跑测试在仓库根产出一个 SQLite 文件，且未 gitignore
```

**位置**: `tests/conftest.py:27`（`monkeypatch.setenv("CROCHET_HISTORY_DB", "test-history-db-unset")`
——注释写的是"重定向到临时目录"，实际是**当前工作目录下的相对路径**）·
`app/utils/history.py:34-37`（`Path(env)` 原样使用）· `:41-43`
（`path.parent.mkdir` + `sqlite3.connect` 真的建库）

**类别**: bug（测试基础设施 / 仓库卫生）· **引入轮次：v2 修复引入（F33）**

**证据**:

```bash
rm -f test-history-db-unset
.venv/bin/python -m pytest tests/test_app_smoke.py -q
ls -la test-history-db-unset
git check-ignore -v test-history-db-unset || echo "NOT ignored"
.venv/bin/python -c "
import sqlite3; c = sqlite3.connect('test-history-db-unset')
print('表:', c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())"
```

实测输出：

```
24 passed in 3.05s
-rw-r--r--@ 1 <user>  staff  12288 ... test-history-db-unset
NOT ignored
表: [('patterns',)]
```

逐文件定位（哪个测试创建它）：

```bash
rm -f test-history-db-unset
for f in tests/test_*.py; do
  .venv/bin/python -m pytest "$f" -q >/dev/null 2>&1
  [ -f test-history-db-unset ] && { echo "★ 创建者: $f"; rm -f test-history-db-unset; }
done
#   ★ 创建者: tests/test_app_smoke.py
```

`test_app_smoke.py` 用 AppTest 跑整个 `main.py` → `render_sidebar()` →
`history.list_results()` → `_connect()` → 在 CWD 建库。本次审查开始时
`git status` 里那条 `?? test-history-db-unset` 就是它（时间戳 16:22）。

**影响**: 三层：① 仓库工作树被污染，每次 `pytest` 后 `git status` 多一条
未跟踪文件，且 `.gitignore` 没覆盖它——迟早被 `git add .` 提交进版本库
（12KB 的二进制 SQLite）；② 这个库**跨测试会话复用**（不是 tmp_path），
今天写入的行明天还在，一旦将来某个用例走"存入历史"路径，`list_results`
就会读到上一次运行的残留 → 随机失败（目前实测 0 行，属**潜伏**而非已发作）；
③ CWD 只读时（某些 CI 沙箱、以只读挂载跑测试）`sqlite3.connect` 会抛
`OperationalError`，`sidebar.py:115-117` 虽有 try 兜住，但 F33 追求的
"任何环境都可复现"这个目标就不成立了。F33 的主目标（不打真实网络/不计费）
**是达成了的**，这只是它的副作用。

**建议**: 用 pytest 的 `tmp_path_factory` 给整个 session 一个真临时目录：

```python
@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch, tmp_path):
    for name in _EXTERNAL_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("app.models.image_parser.load_dotenv", lambda *a, **k: False)
    monkeypatch.setenv("CROCHET_HISTORY_DB", str(tmp_path / "history.db"))
```

`tmp_path` 是每测试独立目录，顺带把 ② 的潜伏风险一并根除。无论是否采纳，
建议把 `test-history-db-unset` 加进 `.gitignore`，并在
`tests/test_repo_hygiene.py` 加一条"跑测试不得在仓库根留下未跟踪文件"的守卫
（顺带能覆盖 `.hypothesis/`、`.codegraph/` 也未被 gitignore 的情况）。

---

```
[low] G6 — E1 的零宽/BiDi 剥离只覆盖 2/3 个出口：Markdown 导出与内联预览仍可显示欺骗
```

**位置**: `app/utils/exporters.py:14-19`（`_md_cell` 只转义 `\` `|` 换行，
**不剥离**不可见字符）· 泄漏出口 `app/ui/result_renderer.py:584-585`
（`st.markdown(md_content)` 内联预览）与 `:480-486`（下载 .md）· 对照已修好的
`result_renderer.py:34-38`（`_INVISIBLE_RE`）与 `pdf_export.py:27-33`

**类别**: bug（显示欺骗面）· **引入轮次：v2 修复引入（E1 处置不完整）**

**证据**:

```bash
.venv/bin/python - <<'PY'
import re, sys; sys.path.insert(0, '.')
from app.ui.result_renderer import _yarn_chip_html
from app.utils.exporters import _md_cell, export_markdown
BAD = "头​部‮反转"                      # 零宽空格 + RTL 覆盖符
inv = re.compile("[​-‏‪-‮⁦-⁩]")
print("  _yarn_chip_html      已剥离?", not inv.search(_yarn_chip_html(BAD)))
print("  pdf_export.esc       已剥离?  True（源码 :27-33 含 _invisible_re）")
print("  exporters._md_cell   已剥离?", not inv.search(_md_cell(BAD)))
md = export_markdown({"parts": [{"name": BAD, "type": "sphere", "color": "白色",
      "rounds": [{"row": 1, "stitches": 6, "notes": BAD}]}], "materials": []}, None)
print("  export_markdown 全文 已剥离?", not inv.search(md))
PY
```

实测输出：

```
  _yarn_chip_html      已剥离? True
  pdf_export.esc       已剥离?  True（源码 :27-33 含 _invisible_re）
  exporters._md_cell   已剥离? False
  export_markdown 全文 已剥离? False
```

**影响**: 与 E1 原文同一条威胁模型——部件名/色名/notes 是自由字符串，
**可从 LLM 输出经图片内文字的 prompt injection 进来**。E1 把胶囊 HTML 与
PDF 两个出口堵了，Markdown 这个出口留着：内联预览（`st.markdown` 会解释
BiDi 控制符）与下载的 .md（用户转发/贴进论坛时按接收端渲染）都能显示与
真实字节序不同的文本，例如把「腿部」显示成「部腿」。危害仅限视觉错序、
不影响针数，故与 E1 同级判 low；列为 bug 而非增强的理由是：E1 已被判定
"该修"并落地了，这里是同一处置的漏项，不是新提议。

**建议**: `_md_cell` 复用同一正则（与 pdf_export 同口径）：

```python
_INVISIBLE_RE = re.compile("[​-‏‪-‮⁦-⁩]")

def _md_cell(value) -> str:
    text = _INVISIBLE_RE.sub("", str(value))
    return text.replace("\\", "\\\\").replace("|", "\\|") \
               .replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
```

注意 `export_markdown` 里 notes/装配说明有几处**没走** `_md_cell`
（`:90` 走了、`:114-115` 装配步骤没走），建议一并过一次剥离；更根治的做法
是把这个正则提到 `app/utils/` 的共用模块，三个出口共享一份定义（与
`_BACKUP_KEYS` 同样的"单一事实来源"思路）。

---

```
[low] G7 — `--batch-dir` 不在 argparse 互斥组内：与 `--image` 同时给时 `--image` 被静默忽略
```

**位置**: `app/cli.py:32-34`（互斥组只含 `--image` / `--mock`）· `:50`
（`--batch-dir` 是普通参数）· `:178`（`if args.batch_dir:` 直接短路，
`args.image` 永不被读）

**类别**: bug（CLI 契约）· **引入轮次：v2 修复引入（U27/F27 批量模式）**

**证据**（§4.C 第 4 问的直接答复）:

```bash
.venv/bin/python - <<'PY'
import os, sys, tempfile; sys.path.insert(0, '.')
for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"): os.environ.pop(k, None)
from PIL import Image, ImageDraw
from app import cli
d = tempfile.mkdtemp(); ind = os.path.join(d, "in"); os.makedirs(ind)
for name, size, col in (("aaa.png",(120,300),(0,120,215)), ("bbb.jpg",(120,200),(220,50,50)),
                        ("aaa.jpg",(120,260),(50,180,80))):
    img = Image.new("RGB", size, (245,245,245)); dr = ImageDraw.Draw(img)
    dr.ellipse([40,12,80,52], fill=(230,180,150))
    dr.rounded_rectangle([45,55,75,size[1]-10], radius=8, fill=col)
    img.save(os.path.join(ind, name))
a = cli.build_parser().parse_args(["--batch-dir", ind, "--image", "/nonexistent/x.png",
                                  "--local", "--quiet"])
print("argparse 接受了两者（无 error）→ image =", a.image)
o = os.path.join(d, "out")
print("rc =", cli.main(["--batch-dir", ind, "--image", "/nonexistent/x.png",
                        "--out-dir", o, "--local", "--quiet"]))
print("产出 =", sorted(os.listdir(o)))
PY
```

实测输出：

```
argparse 接受了两者（无 error）→ image = /nonexistent/x.png
✅ aaa.jpg
✅ aaa.png
✅ bbb.jpg
批量完成 3/3
rc = 0
产出 = ['aaa_jpg.json','aaa_jpg.md','aaa_png.json','aaa_png.md','bbb.json','bbb.md']
```

`--image` 指向的路径**根本不存在**，rc 仍是 0，也没有一句 stderr 提示它被
忽略。同理 `--batch-dir` + `--mock` 会让每张图都产出同一份 mock（实测 3 张
不同尺寸的图 → `analysis` 去重后 1 种），虽然带 `vision_meta.source=mock`
水印，但"批量处理了 3 张照片"这个语义是假的。

**影响**: 脚本/CI 里把 `--image` 和 `--batch-dir` 都传上（例如从单图模板
改写成批量时忘删旧参数）会得到"看起来成功但做的不是你要的事"，且返回码
0 无从察觉。F27 修好了输出名撞名（**已验证有效**，见上方产出里的
`aaa_jpg` / `aaa_png` 消歧 ✅），这条是同一批量特性的另一个入口面。

**建议**: 把 `--batch-dir` 并入同一个互斥组（一行）：

```python
src = parser.add_mutually_exclusive_group()
src.add_argument("--image", ...)
src.add_argument("--mock", ...)
src.add_argument("--batch-dir", ...)          # ← 移进来
```

但注意 `run_batch` 内部构造 Namespace 时会同时置 `image` 与 `batch_dir=None`
——互斥组只作用于命令行解析，不影响内部复用，安全。若希望保留
`--batch-dir --mock`（批量演示确有用途），则至少在 `main()` 入口按现有
`--pdf` 的先例打一句 stderr 提示：
`print("--image 在批量模式下被忽略", file=sys.stderr)`。

---

```
[low] G9 — 文档内交叉引用与行数三处失实：handoff 缺 §14、F13–F22 处置指向错节、sidebar 行数差 22
```

**位置**: `docs/handoff-review.md`（`## 13.` 直接跳到 `## 15.`，**无 §14**）·
`docs/audit-brief-v3.md:3` 与 `docs/audit-brief-v2.md:5`（均称 F13–F22
"已处置 handoff §22"，实际在 **§20**）· `docs/audit-brief-v3.md:64`
（§3 表称 `ui/sidebar.py` 137 行，实际 **159**）

**类别**: 文档失实 · **引入轮次：混合——§14 缺号与 §22 误指一直存在（v2 起），
sidebar 行数是 v3 本文件新引入**

**证据**（§4.F 第 1/2 问的直接答复）:

```bash
.venv/bin/python - <<'PY'
import re, pathlib
hand = pathlib.Path('docs/handoff-review.md').read_text(encoding='utf-8')
secs = {int(m.group(1)): m.group(2).strip()
        for m in re.finditer(r'^## (\d+)\.\s*(.+)$', hand, re.M)}
print("实际章节号:", sorted(secs))
print("★ 缺号:", [n for n in range(max(secs)+1) if n not in secs])
for n in (20, 22, 23, 24):
    print(f"  §{n} = {secs[n]}")
PY
for f in app/ui/sidebar.py; do echo "$f 实际 $(wc -l < $f) 行（v3 §3 声称 137）"; done
```

实测输出：

```
实际章节号: [0,1,...,13,15,16,...,24]
★ 缺号: [14]
  §20 = 第十三轮（Opus 5 审查 F13–F22 处置）记录（2026-08-29）   ← F13–F22 真正在这里
  §22 = 第十五轮（Opus 5 优化建议 V/K/U 系列处置）记录（2026-08-29）  ← v2/v3 都指到这
  §23 = 第十六轮（Opus 5 审查第二部分 + V6）处置记录（2026-08-29）
  §24 = 第十七轮（Opus 5 第二次深审 F23–F36 + E 系列）处置记录（2026-08-29）
app/ui/sidebar.py 实际 159 行（v3 §3 声称 137）
```

其余 § 引用**全部正确** ✅（逐条核过 17 处：`pose.py:13`→§4、`pyproject.toml:53`
→§18（确认 §18:462 记录了 mediapipe/opencv-contrib 冲突）、v3:41/:231→§23
（确认 §23 含 U32 升 3.11 的四步方案）、v3:5→§24、audit-brief.md 的 5 处、
handoff 自引的 4 处）；§3 的 16 项行数 15 项精确相符。

**影响**: 审查者按 v3 §10 的时间预算去读"handoff §22"复习 F13–F22 的处置，
读到的是 V/K/U 系列——本轮我就是这样先读错了一节。§14 缺号让"24 个 §"
这个计数与最大编号 24 恰好巧合地一致，掩盖了缺号（实际只有 24 节但编号到
24，中间空一个）。都不影响代码，但审查任务书是本项目的**主要交接载体**，
误指会直接消耗下一位审查者的时间预算。

**建议**: ① handoff-review.md 补一节 `## 14.`（占位说明"编号预留/已合入
§15"）或整体重排编号并同步更新全部引用；② v2/v3 的 `§22` → `§20`；
③ v3 §3 的 sidebar 行数 137 → 159。另建议在 `tests/test_repo_hygiene.py`
加一条极便宜的守卫，把这类漂移自动化：

```python
def test_handoff_section_numbers_are_contiguous():
    secs = [int(m.group(1)) for m in re.finditer(r'^## (\d+)\.', text, re.M)]
    assert secs == list(range(secs[0], secs[-1] + 1)), f"章节号不连续: {secs}"
```

---

```
[low] G10 — U23 改了时长模型后遗留死常量：MINUTES_PER_ROUND 全仓零引用
```

**位置**: `app/models/crochet_params.py:28`（`MINUTES_PER_ROUND = 2.5`，注释
"锚定常数：classic 36 针圈 ≈ 2.5 分钟（历史口径）"）

**类别**: 可维护性 · **引入轮次：v2 修复引入（U23 换成针数+圈数开销模型后遗留）**

**证据**（§4.B 表最后一问"是否还有引用"的直接答复）:

```bash
grep -rn "MINUTES_PER_ROUND" app/ tests/
#   app/models/crochet_params.py:28:MINUTES_PER_ROUND = 2.5      # 锚定常数：…
#   （仅此一处 = 定义，零引用）
```

同一段里 `STITCHES_PER_CM`（:26）与 `BODY_ROUNDS_PER_CM`（:27）注释写明是
"默认 gauge 的兼容视图，新代码请直接用 Gauge"，同样零引用——但它们明确
标注了"兼容视图"的意图；`MINUTES_PER_ROUND` 的注释说自己是"锚定常数"，
读者会以为它参与计算。

**影响**: 无运行时影响。维护风险在于：`estimate_minutes`（:373-382）用的是
`SECONDS_PER_STITCH=6.5` + `SECONDS_PER_ROUND_OVERHEAD=10`，而文件顶部还
摆着一个看起来同职责的 `MINUTES_PER_ROUND=2.5`；下一位维护者调时长时可能
改错常量并困惑于"改了没反应"（§9「字符串手术静默 no-op」是同一类陷阱的
另一面）。§4.B 表把它列为待审项，答案是：**已死，可删**。

**建议**: 删掉 `:28`，把它在 U23 里的历史角色（校准锚点 classic 121≈旧 122）
留在 `:29-34` 那段注释里即可——那段已经写清楚了。若要保留作可追溯锚点，
把注释改成 `# 历史口径（U23 前），已不参与计算，仅供换算对照`。

---

### 5.D 取舍与增强（不作为 bug 上报）

**取舍 T1 — `_sanitize_secrets` 对 1–2 字符的 Key 做全文字面替换。**
`image_parser.py:48-50` 的 `text.replace(key, "***")` 无最小长度门限；用户在
侧栏误填/截断粘贴一个单字符 Key 时，异常文本里所有该字符都被替换：

```
key='x' → "Connection error: ma*** retries e***ceeded to https://api.openai.com/…"
```

判为取舍而非 bug：① 只在用户填了废 Key 的错误路径上出现，此时诊断信息本就
无用（Key 无效是唯一结论）；② 方向是"过度脱敏"而非泄漏，安全性上偏保守；
③ `key='sk'`/`'abc'`/`'sk-test'` 实测均无误伤（短串恰好不出现在报文里）。
若要修，加一行门限即可：`if key and len(key) >= 8:`。**引入轮次：一直存在（F14）**。

顺带核实 F32 的正则确实会命中中转站 URL 里的 `sk-` 路径段
（`https://gw.example.com/sk-relay/v1` → `sk-***/v1`），与 docstring 里
"不遮蔽 URL……保持可诊断性"的自述不符，但 host 与路径其余部分完整保留，
诊断性无实质损失——同判取舍。

**取舍 T2 — 历史 30 条硬上限，无分页也无"共 N 条"提示。**
`sidebar.py:114` 用 `history.list_results()` 的默认 `limit=30`
（`history.py:98`）。实测存 35 条后：

```
侧栏列出 30 条：最新 图解34 … 最旧 图解05
❌ 侧栏永远看不到：['图解00','图解01','图解02','图解03','图解04']
仅能靠搜索命中：搜 '图解00' → ['图解00']
```

记录没丢（搜索能命中、blob 完好），但用户无从知道"还有 5 条在下面"。判为
取舍：本地单人工具、且搜索是可用出路。**建议做最小增强**——在列表末尾加
一句 `st.caption(f"仅显示最近 {limit} 条，更早的请用搜索")`，条件是
`len(items) == limit`。**引入轮次：一直存在（S4）**。

**取舍 T3 — 品牌色号的 ΔE00≤10 门槛在代码里根本不存在。**
§4.E 第 3 问问"ΔE00≤10 的门槛——蓝色 113 近似的实际 ΔE 是多少"。核实：
`colors.brand_code`（`:275-277`）就是一次 `BRAND_CODES.get(name)` 字典查表，
**全仓没有任何 ΔE00 门槛**；`"蓝色": "Catona 113 (Delphinium，近似)"` 里的
"近似"是人工标注，无数值依据，也无官方 swatch RGB 可离线复算。这与 §6
"品牌色号只收录 8 个已核实 Catona 条目，未核实色名宁缺毋错"是一致的
（人工核实口径），所以不是 bug——但**任务书 §4.E 把一个不存在的机制写成
待验证项**，建议把该行从 §4.E 删掉或改写为"若将来要量化‘近似’，需先取得
官方 swatch RGB"。**引入轮次：v2 提出的未落地建议被 v3 误记为已有机制**。

**增强 E1 — 从同类项目吸取的两条（本轮论文/GitHub 对照产出）。**
本轮扫了 arXiv cs.GR 近期列表（无新的钩织/针织相关论文；最近的
`arXiv:2608.25462` TailorCoPilot 是缝纫制版，非纱线构造，范式不可直接借用）
与 GitHub 三组关键词，逐个对照后只有两项是本仓**确实缺少且值得做**的：

1. **网格单元手工改色（`jamestomasino/stitchy`，★23）**——它的核心交互是
   "`Click` on a rendered grid square to cycle its color through palette
   options"，以及上传后可 "`Rotate`, `Scale`, `Transform` the image onto the
   grid"。本仓 Tab 3 的网格一旦生成即不可改：量化把眼睛/嘴这类小面积特征
   吞掉时用户只能换参数重来。**这两条恰好也是 G3 的正解**——F28 的钳制
   之所以只能"静默压缩"，根因是没有裁剪/定位入口；给用户一个"先裁剪再
   生成"的框，比钳 300,000 行更符合"尽力生成"的产品语义。
2. **张力分析（`stassev/CrochetPARADE`，★8，本仓 validator 已借鉴其
   correctness checking 理念）**——它在 3D 布局后 "identifies overly loose
   or tight stitches"，供用户在开钩前替换针法"reducing the need for
   blocking"。本仓 `validator.py:65-69` 的 `|Δ|≤6` 是这件事的**一维粗
   代理**（只看相邻圈针数差），而 `profile_shaping.py:9-10` 已经写下了
   几何依据 `Δ = 2π·(行高/针宽) ≈ 6`。可低成本升级：把硬编码的 6 换成
   **按 gauge 计算**的 `round(2*π*gauge.row_h_cm/gauge.stitch_w_cm)`——
   classic（w/h=1.23）算出 5.1、fine（0.79）算出 7.9，也就是说现在对
   classic 偏松、对 fine 偏紧，而这正是 §8.7 记录的"classic w/h 反物理"
   取舍在门禁层的延伸。**注意**：改这个会动全部生成器的不变量（针数恒 6
   的倍数依赖 ±6），属专项而非顺手改，故列增强。

另核实三项**不值得借用**：`textiles-lab/autoknit`（★181）与
`fstwn/cockatoo`（★44）都需要 3D mesh 输入，本仓单图路径已由
`docs/3d-reconstruction-design.md` 记录了 AmiGo 范式的简化取舍，无新增量；
`kirastreet/crochetGenerator` 等一批 ★<10 的 JS 项目功能均是本仓子集。

---

### 5.E 负面结果（查过、构造了输入、确认无问题——下一轮不必重扫）

**F-1 v2 的 F25/F27/F29/F30/F31/F34/F36 七条处置全部有效。** 逐条实测：

| 修复 | 验证方式 | 结果 |
|---|---|---|
| F25 命名往返 | save→load→再 save | `'小熊·第三版'` 三步不变 ✅ |
| F27 撞名消歧 | `aaa.png`/`aaa.jpg`/`bbb.jpg` 批量 | 3 图 3 份产出：`aaa_png.*` / `aaa_jpg.*` / `bbb.*`，v2 的"2 进 1 出"不再复现 ✅ |
| F29 decode 门控 | 6000/32768 字符 zlib 炸弹 + "4MB 载荷压成 5260 字符（<6000 门）" | 三者全被拒 ✅ |
| F30 `!` 转义 | 搜 `!` / `时尚!` / `%` / `_` / `!感` / `!!` | 6/6 按字面匹配 ✅ |
| F31 坏 blob | `UPDATE patterns SET blob='{"analysis": {"body_type"'` | `load_result` 返回 None，不崩栈 ✅ |
| F34 dominant_color | `grep` 测试体 | 断言已补 ✅ |
| F36 帽子口径 | 读 `crochet_params.py:591-612` | 只计 `wall_rounds`，notes 注明"另有帽顶 N 圈径向加针盘，不计入筒深" ✅ |

F31 有一个**口径小瑕疵**（不单列为发现）：`load_result` 现在把"损坏"与
"不存在"合并到同一出口（返回 None），于是 `sidebar.py:136-137` 对损坏记录
显示的是「该记录已不存在」，V5 承诺的「该记录已损坏，无法载入（可点「删」
清除）」仍然永不出现。用户仍有"删"的出路，且不再崩栈，故只作备注。

**F-2 §4.B 表里的三个视觉常数经实测均无需改动。**
① `_FGD_FLOOR=144`——降到 120/96/64 对 G2 的失败组合**完全无效**（见 G2
反证），它不是元凶；② `_T_CEIL=96`——实测 Otsu 在这批图上给出 t=152~200，
钳到 96 后 `_fgd_t` 恒为 144，放宽上限只会**抬高** FGD 门槛使情况更差；
③ 覆盖率门槛 15%——实测条带唯一桶数 9~10、保留 1 桶（覆盖率 0.97），
"主体色占条带 7%~15% 不得成为可解释背景色"这个设计意图**正确生效**。

**F-3 `colors.py` 的 1% 长尾剔除与 CIEDE2000 向量化边界都无问题。**
① 长尾剔除：`n = max(1, min(n_colors, 30))`，`final_cover` 至多 n 项且和为
total，故最大项 ≥ total/30 = 3.3% > 1% 门槛——**均匀多色/渐变图不会被剔成
更少色**，`or [...]` 兜底分支是死码但无害；② `_srgb_to_lab_vec` 的
`np.clip(x, 1e-12, None) ** (1/3)`：x,y,z 由**全正系数**线性组合得出恒
≥0，t=0 时走的是 `7.787t + 16/116` 那支（0 < 0.008856），立方根分支不被
选中，与标量版 `t ** (1/3)` 数值一致 ✅（§4.E 第 2 问）；③ `pairwise=None`
自动判——两个调用点 `nearest_yarn_batch:246` 与 `pick_yarn_palette:323`
都显式传了 `pairwise=False`，全仓无依赖自动判的调用方 ✅（§4.E 第 1 问）。

**F-4 §4.D 的 pose 三问：SHA256/原子替换/prompt 注入格式均正确。**
① `model_path()` 的 `tmp.replace(path)`（`pose.py:84`）——`Path.replace` 走
`os.replace`，同目录内 POSIX 原子，且校验在 replace **之前**
（`:80-83`），不匹配即 `unlink` 返回 None，**不存在"先落地后校验"的竞态**
✅；② `format_span_hints`（`:195-206`）产出的是带【几何参考】前缀的中文
纯文本、数值为 `0.07–0.30` 形态，**不含 JSON/花括号**，不会被 strict
`response_format=ImageAnalysis` 路径误解析 ✅；③ `_MIN_VISIBILITY=0.5` 是
MediaPipe `visibility` 字段的中点取值，无官方推荐值可引，属合理默认。
另查 `measured_spans` 的 `max(wrist or hip, hip)`（`:179`）看似有 falsy
陷阱（wrist=0.0 时 `or` 落到 hip），**实测无可观测差异**——外层
`max(…, hip)` 已把结果下限钳在 hip，wrist<hip 时两种写法同值，故不上报。

**F-5 CLI 批量并发无共享可变状态。** AST 扫描全部 `app/**/*.py` 的模块级
可变对象：`PART_SPAN`/`YARN_COLORS`/`_YARN_LAB`/`BRAND_CODES`/`PRESETS`/
`_CANONICAL_PARTS` 六个只读常量 + 唯一被写的 `ring_chart._HEX_CACHE`
（`:98-107`，幂等填充、GIL 下 `dict.__setitem__` 原子、且不在 CLI 路径上）。
`estimate_minutes` / `bridge_rounds` / `validate_pattern` 全是**对入参的纯
函数**，无模块级状态 → **线程安全** ✅（§4.C 第 2 问）。

**F-6 F35 的 filterwarnings 不影响子集运行。** §2 的顾虑不成立：

```
tests/test_colors.py               51 passed          tests/test_round14.py       15 passed, 5 warnings
tests/test_grid_pattern.py         19 passed          tests/test_image_parser.py  41 passed, 1 warning
tests/test_local_vision.py         17 passed, 4 warn  tests/test_invariants_property.py  2 passed
tests/test_app_smoke.py            24 passed
```

残余告警全部是 Pillow 的 `DeprecationWarning`（`image_parser.py:100` 的
`Image.fromarray(mode=…)`，Pillow 13 将移除），**不是 UserWarning**，故不被
`error::UserWarning` 拦。顺带：这处 `mode` 参数在 Pillow 13（2026-10-15）
移除后会报错，建议在依赖上界或代码上择一处置——不算本轮发现，仅提示。

**F-7 conftest 与显式 setenv 的用例互不干扰**（§4.A 第 6 问）。autouse
fixture 先 `delenv`，用例体内的 `monkeypatch.setenv` 后执行故生效；
`test_app_smoke.py:163/176/194`（`sk-ant-test-only` / `sk-test-only`）
单独跑 6 passed ✅。另核实这两个假 Key 不会被 `test_repo_hygiene` 的
`sk-[A-Za-z0-9_\-]{32,}` 误伤（长度不足）✅。

**F-8 结果页每次 rerun 的四份序列化开销可忽略。** `render_results` 每次
rerun 做 `serializable_params`（:448）+ `export_markdown`（:459）+
`backup_json`（:491）+ `encode_result`（:532，含 zlib level 9）四次全量
序列化。实测：

```
默认 classic 9/18          83 圈 → 合计   1.9ms   （token 3216 字符）
大玩偶 fine 20/50         265 圈 → 合计   4.8ms   （token 4460）
schema 上限 50/200 max密度 2287 圈 → 合计  41.7ms  （token None，>6000 门控生效）
```

即使在 schema 上限（头 50cm / 高 200cm / 40×50 密度）也只有 42ms，勾一个
checkbox 的 rerun 完全无感 ✅。F23 的分享入口对每次 rerun 的额外成本
（zlib level 9）实测 0.4–8.8ms，无需改成"点按钮才生成"。

**F-9 `--batch-dir` 的失败隔离、`--pdf` 逐图导出、CLI 非 `--quiet` 路径均正常。**
`cli.py:211` 的 `p.rows` 依赖 `CrochetPart.rows` **property**
（`schemas.py:36-39`），非 `--quiet` 路径实测 `✅ 标准 · 头 9.0cm · 4 部件 ·
49 圈` rc=0 ✅（§2 的基线命令带 `--quiet`，恰好绕过这一行，值得一提但无 bug）。
`--pdf` 在批量下已按 `{stem}.pdf` 逐图导出且有 stderr 提示（`:179-180`），
v2 的附带项已修 ✅。

---

### 5.F §4 各问的逐条答复

| 任务书问题 | 答复 | 依据 |
|---|---|---|
| §4.A F36 旧备份 height_cm 与新部件混排是否自洽？ | **自洽**——`refresh_derived` 不改 part.height_cm，而"调尺寸"整份重算，两条路径都不混排新旧口径 | F-1 |
| §4.A U23 旧备份 estimated_time_minutes 会跳变吗？ | 会跳变，但**方向正确**——`_rebuild_params`→`refresh_derived`（:393）用当前模型重算，是"就新"而非"打架" | F-1 |
| §4.A F30 搜索含 `!` 的标题按字面匹配吗？ | **是**，6/6 用例正确 | F-1 |
| §4.A F28 clamped_from 是否被 share/备份序列化？ | 它**不在** result dict 里（只在 Tab 3 的 GridPattern），无需序列化；真问题是 **UI 从不读到它** | **G3** |
| §4.A F32 正则会误伤 URL 里的 `sk-` 路径段吗？ | 会（`/sk-relay/`→`/sk-***/`），但 host/其余路径保留，诊断性无实质损失 | T1 |
| §4.A F33 conftest 会影响显式 setenv 的用例吗？ | 不会（顺序正确）；但它把历史库指到了**相对路径** | F-7 / **G5** |
| §4.B SECONDS_PER_STITCH 6.5 / ROUND_OVERHEAD 10 有实证数据吗？ | 无，§6 已如实署名"经验估算"，本轮不重复报 | §6 |
| §4.B FGD 下限 144 对深肤色/深背景够吗？ | **它不是瓶颈**——降到 64 也修不了失败组合；真问题是缺区域级 sanity check | **G2** / F-2 |
| §4.B Otsu 钳位上限 96 是否该放宽？ | **不该**——放宽只会抬高 `_fgd_t = max(1.5·t_seed, 144)`，使情况更差 | F-2 |
| §4.B 覆盖率门槛 15%：7%~15% 的主体色会怎样？ | 不被收为背景色（设计意图正确生效） | F-2 |
| §4.B MIN_SUBJECT_FRAC：主体占 3% 的远景图被拒合理？ | 合理——实测 scale=0.3 时占比落到门槛外，回退启发式，无崩溃无异常值 | F-2 |
| §4.B 1% 长尾剔除会把渐变图剔成几色？ | 一色都不剔（n≤30 ⇒ 最大项 ≥3.3%） | F-3 |
| §4.B 品牌色号下限 5g/色是否误导？ | 轻微高估但方向保守（少买不如多买），§6 已列刻意设计 | §6 |
| §4.B MINUTES_PER_ROUND 还有引用吗？ | **零引用，已死** | **G10** |
| §4.B HAT_DEPTH_RATIO 0.6 / BODY_HEAD_RATIO 1.0 / LIMB 0.33 来源？ | 均为 Q 版比例假设，§6 已署名；本轮未发现几何矛盾（F36 后帽子口径自洽） | F-1 |
| §4.B history title 长度无限制？ | 确认无限制（`save_result` 只 `.strip()`）；v2 §5.F-5 已测 5MB 字符串"只是慢不崩"，不重复报 | v2 §5.F-5 |
| §4.B 历史上限 30 够用？ | 记录不丢但**侧栏永久看不到第 31 条起**，无提示 | T2 |
| §4.C 4 worker 并发跑 GrabCut 会竞争吗？ | 未观察到；且无共享可变状态 | F-5 |
| §4.C estimate_minutes/bridge_rounds/validate_pattern 线程安全吗？ | **是**（纯函数，AST 扫描确认零模块级可变状态） | F-5 |
| §4.C 批量 `--out` 缺省打印到 stdout 会混杂 6 份 JSON 吗？ | **不会**——`run_batch` 为每图强制 `out=<stem>.json`（`:142`），stdout 分支不可达 | F-9 |
| §4.C `--batch-dir` 与 `--image` 同给时 argparse 处理正确吗？ | **不正确**——两者不互斥，`--image` 被静默忽略、rc=0 | **G7** |
| §4.D SHA256 校验正确吗？`tmp.replace` 原子吗？ | 正确、原子，且校验在 replace 之前 | F-4 |
| §4.D format_span_hints 会被 LLM 误读吗？ | 不会（纯中文文本、无 JSON 结构） | F-4 |
| §4.D _MIN_VISIBILITY=0.5 有文档依据吗？ | 无官方推荐值可引，属合理默认（visibility∈[0,1] 的中点） | F-4 |
| §4.E ciede2000_vec 的 pairwise=None 有调用方会误判吗？ | 无——两个调用点都显式传 `pairwise=False` | F-3 |
| §4.E `_srgb_to_lab_vec` 在 t=0 时与标量版一致吗？ | **一致**（t=0 走线性支，立方根分支不被选中） | F-3 |
| §4.E 品牌色号 ΔE00≤10 的实际值是多少？ | **代码里没有这个门槛**，"近似"是人工标注 | T3 |
| §4.F handoff 24 个 § 内交叉引用自洽吗？ | 缺 §14；F13–F22 处置被 v2/v3 误指 §22（实为 §20）；其余 17 处引用全部正确 | **G9** |
| §4.F 四份文档"已实现清单"一致吗？ | 一致（F23 分享入口已落地，README:23 不再是空承诺）；§3 行数 16 项中 1 项失实 | **G9** |
| §4.F README 功能清单逐条对照实现？ | `:9-27` 的 **19 条功能全部有对应实现** ✅；缺陷是**遗漏**而非失实：`:3` 徽章 URL 仍是 `OWNER` 占位符且链接目标为空 `()`；`:108-133` 项目结构树缺 13 个模块（validator/pose/subject/share/history/pdf_export/cli/ring_chart/profile_shaping/color_design/gauge/local_vision/design_system） | 见下 |

README 的两处遗漏未单列为发现（纯展示层、不误导功能判断），建议顺手修：
徽章换成真实 owner 或删掉，结构树补齐或改成"主要模块"并注明非全量。

---

### 5.G 与前两轮发现的重叠度自评

**零重复。** G1–G10 与 F1–F36、E1–E4、T1–T3、V/K/U 系列无一条重复，
§8 的 14 条历史误报一条都没重踩：

- **§8.11「帽子高度含帽顶是错的」**——我**没有**再报；F36 已统一口径，
  实读 `:591-612` 确认只计筒壁 ✅。G4 讲的是**另一对**口径
  （structure 目标高 ↔ params 标注高），与帽顶无关，且 G4 里 `params` 侧
  被明确判为**正确的一方**。
- **§8.12「时长模型按圈数不对」**——没有再报；G10 只指出旧常量已死。
- **§8.13「搜索 %/_ 当通配符」**——没有再报；F-1 实测 6/6 正确。
- **§8.14「share encode 是死代码」**——没有再报；F23 的入口
  （`result_renderer.py:530-542`）已存在且键集正确。G3 是**另一个**
  "死分支"：F28 的 UI 提示，与 share 无关。
- **§8.6「圆柱标注高度含起底盘」**——G4 显式引用该判决**已确立的原则**
  （`actual_h` 不含起底盘是对的），指出的是"预算侧没按同一边界算"。
- **§6 的刻意设计我一条都没报为 bug**：波浪摆 `allow_wide_jump`、
  `preview` 不进 token、米数经验估算、sin 球末圈 12 针、裙腰开口、
  `hem_st*2` 无上界、6.5s/针、5g/色下限——全部核过未报。

**本轮与 v2 的性质差异（一句话）**：v2 的结论是"单点逻辑很硬、**接缝**还
没有"；本轮的结论是**接缝的修补本身也有接缝**——7/10 出自 v2 修复代码，
其中 4 条是"修了一半"（G1 读侧、G3 UI 侧、G6 第三个出口、G8 断言）。
唯一真正的**新面**是 G2：前三轮所有视觉测试都在验"不崩溃/安全降级"，
从没有人验过"掩码本身是否正确"，而 `subject.py:203` 那道面积门在设计上
就看不见"面积对、区域错"。

**推荐修复顺序**（按"单位改动的止损"排序）：

1. **G8 的断言先写**（不改产品代码）——写完立刻会红，直接暴露 G1；
2. **G1**（一行 `data.get(k)`）——F24 的用户可见症状随之真正消失；
3. **G3**（一行补 `clamped_from`）+ **G5**（一行 `tmp_path`）+
   **G10**（删一行）——三条各一行，与 1/2 同一个 commit 即可；
4. **G2**（`subject.py` 加 4 行区域校验 + 把那 8 个组合固化成回归矩阵）
   ——本轮唯一需要设计判断的一条，也是唯一影响图解**内容**的一条；
5. **G4**（两处预算边界对齐 + 一条容差断言）——领域口径，需与"结构表
   是设计意图还是承诺"这个产品判断一起定；
6. **G6 / G7 / G9**（各 1–3 行）+ T2 的一句 caption——收尾。

---

## 6. 刻意设计决策（勿报为 bug——截至第十七轮的完整汇总）

**领域/几何**（v1/v2 已确立 + 本轮新增）
- 针数恒为 6 的倍数、非波浪圈 |Δ|≤6；波浪摆经 allow_wide_jump 显式
  豁免；bridge_rounds 逐步桥接（F13）
- 圆柱/帽/一体件高度只计筒壁轴向（F36 统一）；帽顶/起底盘不计高
- sin 球末圈 ≤12 针 + "勿再减针"原文工艺警告
- 一体件高度 13.8cm（ladder 默认，strip_dome 口径）
- 时长 = 针数×6.5s + 圈数×10s（校准锚点 classic 121≈旧 122；经验估算
  无标准署名——V6）；下限 30 分钟含备料收尾
- 帽子侧壁 = max(3, 0.6·直径)，帽顶径向盘不计入筒深
- 波浪摆 hem_st×2 无上界（工艺定义使然，schema le=50 已兜底）

**视觉/数据**
- CIEDE2000 标量+向量化（34 组官方数据锁定，数值一致 1.42e-14）
- GrabCut FGD 下限 144（浅肤色修复）；Otsu 钳位 [16,96]；覆盖率 15%；
  腐蚀 1px；退化 [5%,95%]；确定前景种子（防小孤立块被吞）
- 米数 320/250/200/140 为经验估算（V6 纠正，非 CYC 数据）
- 品牌色号 8 个已核实 Catona；内部占位符 skin/body 不进逐色材料
- MST 肤色标尺扩充；F30 搜索转义符用 "!" 不用反斜杠
- 网格 _MAX_CELLS=80_000、_MAX_GRID_WIDTH=200

**架构/产品**
- _BACKUP_KEYS（含 preview+usage）/ _SHARE_KEYS（=备份−preview−usage）
  单一事实来源；分享/备份/导入/调尺寸全部走共用键集
- share token 无签名（本地工具定位）；decode 对称门控 6000/2MB
- 分享载入 rid 用 uuid（V3）；历史/分享载入走 _validated_backup（V5）
- CLI 批量每图独立 orchestrator + ThreadPool；CLI 同受自检门禁 rc=2
- mock 选项只在真正无 Key 时出现；mock 带水印
- orchestrator 不用 @st.cache_resource；pose 可选 [pose] 钉 <1.0
- conftest.py hermetic（autouse 清 Key + 禁 load_dotenv）
- U32 升 3.11 回滚（zip strict= 是 3.10+ 特性，3.9 不支持）；方案
  四步已记录待专项
- filterwarnings = error::UserWarning（F35）
- CROCHET_EVAL_DIR 评测脚手架 skipif

## 7. 已知局限（只评估严重度）

1. 视觉管线验证几乎全在合成图上——最大盲区
2. 无真实 LLM API 集成测试
3. pose.py 43% 覆盖（mediapipe 正向路径全未测）
4. 旋转体假设；正面关键点测不到尾巴
5. tab_photo 上传交互无 AppTest 覆盖；PDF/环形图/符号条无目测验证
6. mediapipe 0.10.x 实机验证因网络未完成
7. 无 i18n（U9 搁置）
8. 分享 token 无签名；历史无跨设备/加密
9. crochet_params.py 908 行 / result_renderer.py 585 行（拆分搁置待专项）

## 8. 历史误报清单（勿重复——全部真实发生过；★ 为新增）

1. 网格 aspect_ratio 补偿方向——误报"反了"两次
2. 减针"隔N针"——外部第一轮给了错误修法
3. "anthropic>=0.95 需升级才有 messages.parse"——实测已含
4. "sin 球末圈 12 针没收到 6"——物理必然+原文警告
5. "裙腰应闭口"——闭口圆盘套不进身体
6. "圆柱标注高度含起底盘"——会把 4.5 标成 9.4
7. "classic 密度 w/h=1.23 反物理"——已记录取舍
8. "波浪摆 48 跳变违反 |Δ|≤6"——V2 白名单已覆盖
9. "米数该有标准出处"——V6 已纠正为经验估算
10. "zip 缺 strict="——U32 回滚后不得再引入
11. ★ "帽子高度含帽顶是错的"——F36 已统一口径，不要再报
12. ★ "时长模型按圈数不对"——U23 已改按针数+圈数开销
13. ★ "搜索 %/_ 当通配符"——F30 已用 ! 转义符修复
14. ★ "share encode 是死代码"——F23 已补结果页入口

## 9. 审查者陷阱（工具/框架/环境）

- **AppTest**：session_state 可迭代无 .keys()；无 at.file_uploader；
  at.query_params 可设；radio options 换代残留值隐式重置；download_button
  不是 AppTest 一级属性（用 at.download_button 可访问）
- **Streamlit**：expander rerun 收起；st.success 后立即 rerun 消息不可见
  （session 标志必须以新 result_id 为键）；st.dataframe 需 hide_index=True
- **Python 版本**：zip(strict=) 是 3.10+；ruff target py311 激活 B905/B017
  （存量 13 处已用 strict=False/异常收窄处理，升 3.11 后可改回 strict=True）
- **pydantic v2**：默认不做赋值校验（`.rounds = [dict]` 通过但序列化
  报 UserWarning）；model_copy(update=...) 保类型
- **conftest hermetic**：monkeypatch.delenv 后 load_dotenv() 会重灌
  .env——需同时 patch load_dotenv
- **字符串手术**：多轮 .replace() 因目标不符静默 no-op（三轮踩过）——
  用 Edit 工具或 assert-guard
- **ESCAPE 转义**：SQLite ESCAPE 子句的转义字符**必须恰 1 字符**；
  Python 源 `'\\''` 与 `'\\\\'` 的区别极难目测——用变量拼接绕开
- **mediapipe**：1.0.x macOS 原生崩溃；0.10.x tasks API 同构但 import
  路径不同（`vision.PoseLandmarker` 直属）
- **uv build** 前删 build/；.venv 是 py3.9.6；opencv-headless 与
  opencv-contrib 不可共存

## 10. 时间预算建议

- 30 分钟：跑通基线（§2）+ handoff §23/§24 + 本文件 §6–§8
- 3 小时：§4.A 修复引入回归排查（每个 F23–F36 修复点逐一回验）
- 2 小时：§4.B 校准常量审视（30+ 个，挑 5 个影响最大的做边界测试）
- 2 小时：§4.C CLI 并发深入 + §4.D pose 覆盖盲区分析
- 2 小时：§4.E CIEDE2000 vec 边界 + §4.F 四份文档一致性
- 汇总：按 §0 格式 + 三档统计 + 引入轮次标注 + 推荐修复顺序

---

*整理于 2026-08-29，对应 586 tests + 1 脚手架 / 17 轮演进 /
前两轮 36 条发现已全部处置。如与代码不符，以代码为准。*
