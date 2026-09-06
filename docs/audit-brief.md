# 审核交待（Audit Brief）——供外部 AI（GPT）审核本系统

> 给审核者：本文档是唯一指定的审核入口。读完本文你应该知道看什么、
> 怎么跑、去哪里找证据。所有结论请给出行号/文件名级证据。

## 0. 系统一句话

**CrochetPhoto2Pattern**：单张玩偶照片 → 结构推断 → 可直接钩织的
amigurumi 图解（圈层针数表 + 材料清单 + 装配说明）+ 多格式导出
（Markdown 图解纸 / CrochetPARADE DSL / PDF）。Python 3.12 +
Streamlit，uv 管理，MIT。仓库根：`/Users/baobaodaren/ZCodeProject/CrochetPhoto2Pattern`。

## 1. 运行与验证命令

```bash
uv run pytest -q        # 全量测试（以本次实际输出为准）
uv run ruff check .     # lint
uv run mypy app         # 类型
uv run streamlit run app/main.py   # 启动应用（入口是 app/main.py）
```

## 2. 核心流水线与模块地图

照片 → `ImageAnalysis` → `StructureDesigner.design_3d_structure`
（部件结构推断）→ `CrochetParamsGenerator.generate_params`（圈层针数、
材料、装配）→ `validate_pattern`（代数自检）→ 导出器。

| 模块 | 职责 | 审核关注点 |
|---|---|---|
| `app/models/crochet_params.py` | 圈层生成（增减针代数）、材料清单、装配说明 | 材料可选件门控（安全眼/定型线/配重珠）、装配两条路径（名称路径 + 装配图路径）需同步维护 |
| `app/models/validator.py` | 图解代数自检 | **硬错误 vs notes 的边界**（见 §4），是全系统领域假设的承重墙 |
| `app/models/gauge.py` | 密度估算、CYC 纱线分档（cyc_label）、克重/米数 | CYC 阈值换算（×0.984）与真实锚点（DROPS 18sc、Red Heart 13sc） |
| `app/models/stitches.py` | 针法速查表（36 个常用词条、6 分族、5 语言体系） | US↔UK 配对不变量、簇生针中性语义 |
| `app/models/grid_pattern.py` | C2C/像素网格图 | C2C 行方向（奇数行 ↙正面/偶数行 ↗反面） |
| `app/utils/exporters.py` | Markdown 图解纸（图例、钩法前言、加针错位提醒） | 图例与针法表接线（glossary_note_lines） |
| `app/utils/parade_export.py` | CrochetPARADE DSL 导出 | 超出均匀分组表达的圈"诚实跳过"逻辑与 validator notes 口径一致性 |
| `app/ui/` | Streamlit 界面（fable5 主题令牌系统） | st.html 净化器剥 `<svg>` 的教训——所有 SVG 走 st.markdown 通道 |

## 3. 审核前必读（按顺序）

1. **`docs/SOURCES.md`**（外部校准证据链）——39 个来源行：每个来源
   印证了什么、校验器五处先验修正的驱动证据、夹具映射。
   这是理解本系统"领域假设从哪来"的钥匙。
2. **`docs/system-status.md`**（状态、证据与发布门禁）。
3. **`CHANGELOG.md`**（中文全程记录）——每轮外部校准的变更都有条目。
4. **`tests/test_reference_patterns.py` 与 `test_reference_grid.py`
   的模块 docstring**——真实图解夹具的来源与结构注记（6 套语言体系、
   37 个逐字源；夹具数以 pytest collection 为准）。

## 4. 承重设计决策（重点审核对象）

**4.1 校验器语义（validator.py）**——阻断性错误只留无法形成有效图解的情形：

- 硬错误：针数代数断裂（st ≠ prev + inc − dec）、圈数为空、针数/
  加减针不是数字、针数 < 1；
- notes 分两类：**非 6 倍数圈与超平滑跳变圈正常导出**（只提示）；
  **加减速混圈与加/减针超均匀分组表达的圈由 parade 导出跳过**
  并留 warning；遇到首个不可表达圈后，该部件只导出此前的连续有效
  前缀，避免以"虚拟前圈"继续而产生针数断裂；
- 前四处降级全部由真实图解驱动（Clover 22 针腿 / 8→16 倍增 / 垂耳兔
  眼窝混圈 / granny 锁针空间加针），驱动证据链在 SOURCES.md 表中；
- **第 5 处先验降级（外部 AI 审核后落地）**：减针超纯 A 配对
  （dec > prev//2）已从硬错误降级为 notes——机械反例：4 针经一次
  sc4tog 收到 1 针（3 > 2 但完全可钩）；M 三并一/sc4tog/圈圈减针
  均为词表内真实组合减针；它不再是硬错误。

**4.2 均匀分组表达**：生成器只输出可写成 `(aX,V)×n` 或
`(aX,A)×n` 的圈；混圈/
超源圈在 parade 导出中跳过并留痕（`已跳过` 字样）。

**4.3 计数口径**：螺旋钩（不引拔不翻转）、起立锁针不计针（若图解
注明"计为 1 针"则按图解——Tiny Curl ch-3 计针 vs Motley ch-1 不计
两约定并存，导出前言已注明）。

**4.4 材料与装配输出的安全纪律**：安全眼"3 岁以下/宠物禁用，必须改刺绣眼"、
定型线"端部折环包裹、儿童玩具禁用硬质内骨架并改毛条等软质填充"、
配重珠"3 岁以下勿用"、
针塑形标"可选"（本系统塑形已内建）。全部有逐字源（SOURCES.md）。

## 5. 已知边界（有意为之，非缺陷）

- **分层圈/跨部件构造不夹注**：FLO/BLO 前后片分离圈（Spin a Yarn
  鹅）、跨部件挑钩、椭圆起链身体超出单圈聚合模型——如实记录、不生
  成该圈，边界论证见 test_reference_patterns 注释；
- C2C 像素图走 grid 模块，与圈层代数互不假设；
- 工时/克重为低置信度经验估算，UI 与导出均有免责说明；
- 校验器拦截过 4 次视觉转录错误（蜜蜂 R6、胡萝卜 R3、低缝兔省略行、
  无缝兔 dec around）——夹具注释里保留了勘误过程，可作转录质量样本。

## 6. 给审核者的具体问题（建议逐条回答）

1. **夹具抽查**：任选 `tests/test_reference_patterns.py` 或
   `tests/test_reference_grid.py` 中 3 个
   夹具，逐圈核对针数代数（st = prev + inc − dec）与注释中的来源
   断言是否自洽；
2. **先验残留**：validator 是否还有"生成器先验被当成可钩性规则"的
   候选？（重点确认 dec > prev//2 只产出 note；`allow_wide_jump` 只抑制
   跳变 note，不改变 `ok`）
3. **针法表**：`app/models/stitches.py` 的五体系对照有无事实错误？
   （CYC 常用条目 + Shelley Husband 配对链已按 2026-09 快照核对）
4. **导出一致性**：parade_export 跳过逻辑与 validator notes 措辞、
   markdown 图例三者口径是否一致；
5. **UI 通道**：全部 SVG 是否确已离开 st.html（DOMPurify 会剥整个
   `<svg>` 与 `<script>`，Streamlit 1.60 实测）；
6. **安全措辞**：§4.4 四条安全口径是否足以覆盖儿童玩具场景；
7. **测试结构**：真实图解夹具已按专题拆分（圆形玩偶主文件 +
   test_reference_grid.py 网格专题），后续新专题（跨语言/特殊拓扑/
   出版矛盾）按同一模式继续拆分；来源注记随夹具走。

## 7. 审核纪律

- 仓库内所有图解夹具**只含针数代数与结构性注记**，不含受版权保护
  的图解原文；审核复述时请保持同一纪律；
- 历史上发现的出版矛盾（3 例）与转录勘误（4 例）都保留在夹具注释
  中——这是特性不是脏东西，勿"清理"；
- 修改代码前先跑 `uv run pytest -q` 记录基线，改完必须全绿 + ruff +
  mypy 干净再交付。
