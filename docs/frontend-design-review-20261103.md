# 前端设计审视 · 2026-11-03

[文档索引 / Documentation index](README.md)

对 Streamlit 界面做了一轮"设计主管式"审视：先通读令牌与注入 CSS，再把应用跑起来用真实浏览器看，
最后用 DOM 探测核实每一条视觉判断。结论先行：**「图解纸」概念本身成立**——纸面/墨色/记号扣黄的
三色系统、宋体圈行、指标条、hero 环标都已落地；但有 3 处承载概念的实现在 Streamlit 1.60 上
**静默失效**，1 处核心交互有缺陷，另有 1 处与概念直接冲突的通用模板痕迹。本轮已修复这些，
其余为建议，列在末尾。

## 范围与方法

- 对象：`app/main.py`、`app/ui/*`、`.streamlit/config.toml`、`app/ui/mask_canvas/`。
- 工具：系统 Chrome + 仓库自带 Playwright（`scripts/browser/`），合成输入与
  `scripts/check_browser_workflow.cjs` 同源；1440 px 与 390 px 两个视口；Streamlit 主区域是
  内部滚动容器，整页截图改用 6500 px 高视口。
- 核实方式：对 Tab、Radio、指标、圈行读取 DOM 结构与计算样式；勾选圈次后读取
  `<details open>` 状态；所有截图与探测脚本可按 [浏览器回归](browser-regression.md) 的启动方式重放。

## 已确认并修复

| # | 问题 | 证据 | 修复 |
|---|---|---|---|
| 1 | 勾选任意一圈，该部件的折叠面板立即收起；"边钩边勾选"每勾一圈就要重新展开 | 探测日志 `after tick 0: expander open = false` | `st.expander` 没有 key，元素 id 由标签派生；标签里的"已完成 n/N"每次勾选都变，面板随之重新挂载为折叠态。标签改为稳定，完成数由面板内进度条承载。修后三次勾选均 `open = true`。 |
| 2 | 激活 Tab 没有记号扣黄，只剩 Streamlit 默认下划线；Tab 键盘焦点环同样失效 | DOM：Tab 已是 `div[data-testid=stTab][role=tab]`，`data-baseweb=tab-list` / `button[role=tab]` 不存在 | 选择器改为 `[role=tablist]` / `[role=tab]`，隐藏 `.react-aria-SelectionIndicator`。修后激活 Tab 背景 `#ffe14d`。 |
| 3 | 选中的 Radio 没有淡黄高亮 | DOM：`label[data-testid=stRadioOption][data-selected=true]`，无 `data-baseweb=radio` | 选择器更新；修后背景 `#fff4b8`。 |
| 4 | 圈行的记号扣扫过与下划线只覆盖文字宽度，像一个个标签而不是纸上的一行 | 截图 | 复选框容器与 label 拉满整行。 |
| 5 | 手机端：固定头栏透明，滚动后 "Deploy"/菜单压在正文上；标题 `CrochetPhoto2Pattern` 被硬折行 | 390 px 截图 | 头栏改纸色；`client.toolbarMode = "minimal"` 去掉 Deploy；标题规则提高特异性（之前被 Streamlit 的 markdown `h1` 规则压过）并在 ≤ 640 px 用 1.25rem。 |
| 6 | 主体修正画布（iframe）用 `system-ui`、`#aaa` 边框、5 px 圆角、蓝色原生滑块，与页面不是一套 | 截图 | Python 把 `theme.py` 令牌作为组件参数传入，`editor.js` 写成 CSS 变量；`index.html` 保留同源回退值，由 `tests/test_theme_tokens.py` 守护。 |
| 7 | 部件面板显示内部枚举 `形状: sphere` | 截图 | 复用结构表的中文形状名（球形/圆柱/开口杯形/照片轮廓/头身一体）。 |
| 8 | Tab、章节标题、侧栏标题、折叠面板标题、按钮上约 60 处彩色 emoji | 截图 | 概念明言"记号扣黄是唯一高亮色，毛线色是页面上仅有的其他颜色"；彩色 emoji 与之冲突，也是最强的通用 Streamlit 痕迹。按显式映射表移除，测试/浏览器脚本/README 同步；消息正文与说明中的 ✓/⚠️/📏 未动。 |

顺带：页脚的 `— ` 连接改为冒号；手动页的成功提示去掉 ✅ 与感叹号；结果页引导句改为描述顺序
（先核对比例与结构，再逐圈勾选，需要时修正并备份），不再与成功提示重复。

## 保持不变、经核实有效

- 字体：标题/圈行/指标走 Charter → 宋体回落，正文与控件走系统黑体；数字等宽内衬。
- 指标条：2 px 墨色上边线、无卡片；alert 为白纸 + 状态色左线。
- hero 环标描线动画与 `prefers-reduced-motion` 降级；打印样式。
- 结果页 1–5 的编号章节：内容确实是顺序（比例 → 结构 → 参数 → 装配 → 修正），编号有信息量。

## 建议（本轮未改）

1. **侧栏信息架构**：标题"创作设置"下先出现两个"打开…"面板，再是驱动一切尺寸的密度。建议密度上移到最前，
   "打开备份图解 / 打开试钩包"合并为一个"打开已有工作"面板放底部，并减少分隔线造成的大段空白。
2. **第 5 章"局部修正"**：JSON 文本域、6 个折叠面板、三组按钮平铺在一起。建议分两层——常用
   （尺寸 / 部件 / 材料）直接可见，高级（JSON / 结构 JSON）收进一个折叠面板。
3. **颜色名 `skin` / `body`**：来自手动流程的占位色，会出现在"颜色:"与 3D 预览；应在生成层映射为色表名
   （数据层，不在 UI 修）。
4. **进度两按钮**"重置进度 / 全部完成"用 `st.columns(2)` 拉得很开；并排靠左或放到面板标题行更紧凑。
5. **说明段落密度**：照片页 3 段、第 3 章 6 段 `st.caption`，首次使用有价值，之后是噪音；可收进"说明"折叠或用
   控件 help。
6. **结构表的"位置 / 旋转"列**是开发者坐标串，对用户几乎不可读，建议默认只在"查看结构 JSON"里出现。
7. **升级防线**：Streamlit 小版本会改 `data-testid` / baseweb 钩子而不报错。建议把本轮的 DOM 探测
   （激活 Tab 背景色、选中 Radio 背景色、勾选后 `details[open]`）加进 `check_browser_workflow.cjs`，
   让"记号扣"这类概念性样式失效时 CI 能发现。

## 验证

- `pytest`：全量 2546 passed / 2 skipped；受影响模块重跑 76 passed。`ruff check app tests scripts` 与
  `mypy app tests` 通过。
- 浏览器：Tab/Radio 计算样式、勾选后面板状态、圈行宽度、1440/390 px 截图均在修后复核；
  `scripts/check_browser_workflow.cjs` 同步了新标签（Tab 名、"重置进度"），并对隔离测试服务
  （`CROCHET_HISTORY_MODE=single_user` + 临时 DB）跑完 16 条流程：全部通过，report status `pass`，
  无页面错误、无外部请求。
- 本轮未做实物试钩，也不涉及识别准确率；仅界面与交互。
