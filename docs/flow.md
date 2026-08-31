# 系统处理流程

## 五步流水线

```
照片上传
   ↓
1. 图像预处理（PIL 缩放 + RGB 转换）
   ↓
2. 图像观测（与模型服务商解耦）+ 人物语义解析
   geometry 输出：版本化宽度剖面、flare、置信度、单视图限制
   semantic 输出：体型、部件列表、关键特征、姿态、相对头身比例、难度
   ↓
3. 目标尺寸变换（sizing）
   单图不推断绝对厘米：保留照片头身比例，按用户目标高度计算设计尺寸
   ↓
4. 部件结构设计（StructureDesigner，模板骨架而非完整 3D 重建）
   输出：StructureGeometry v2 部件图谱
   - 兼容字段：基本形状 + 比例（sphere / cylinder / cup）
   - 显式假设：归一化位置、欧拉旋转、实体实例、镜像组、连接锚点
   - 制作语义：逻辑部件数量（双臂/双腿/双耳各 2 个）
   - 可信度：template_inferred + 低置信度，避免伪装成照片三维测量
   ↓
5. 钩织参数生成（CrochetParamsGenerator）
   输出：每个逻辑部件的圈数序列、针数、加减针、材料、装配说明
   塑形：连续变化率 ΔN=2π·行高/针宽，再向上量化到六等分针法；
   每圈还受 V/A 源针数量约束，保证输出说明可实际执行
   总针数、材料、工时和进度按实体数量计算；旧结构缺数量时按 1 兼容
   StructureGeometry v2 的 attachment 会投影成 assembly_plan 并驱动装配说明；
   旧结构没有连接图时才使用部件名兼容规则
   ↓
JSON 输出 + Streamlit UI 展示 + 用户局部修正 + 下载 + 完整结果备份/导入
```

## 代码模块

| 文件 | 职责 |
|------|------|
| `app/main.py` | Streamlit 入口（薄壳：全局配置 + Tab 分发） |
| `app/ui/` | 界面组件：侧栏、三个 Tab、结果渲染（进度追踪 / 局部修正 / 下载） |
| `app/utils/exporters.py` | Markdown 图解导出 |
| `app/utils/images.py` | 上传图片安全加载（损坏文件/超限大小的友好错误、EXIF 方向转置、透明 PNG 合成白底） |
| `app/models/image_parser.py` | Vision 调用（Anthropic structured outputs 优先 → 失败降级 OpenAI → 无 key 时 Mock）；`parse_image_local` 为无 LLM 路径入口 |
| `app/models/local_vision.py` | 无 LLM 本地视觉估算（人脸检测 → 头身比例；轮廓剖面 → 下摆展开自动加裙子） |
| `app/models/sizing.py` | 单图相对比例 → 用户目标成品尺寸；记录尺寸来源、比例限制与变换元数据 |
| `app/models/geometry.py` | 几何契约：AI/本地共用的单图观测 IR，以及 StructureGeometry v2 部件/实例/连接图谱 |
| `app/models/color_design.py` | 照片纵向色带 → 部件逐圈配色 + 换线说明（换线由照片颜色驱动） |
| `app/models/structure_designer.py` | 语义部件 → 版本化模板结构图谱（位置、旋转、镜像数量、连接锚点） |
| `app/models/gauge.py` | 小样密度、针目几何与动态塑形上限的单一事实来源 |
| `app/models/crochet_params.py` | 钩织圈数算法（球形/圆柱、剖面与六等分塑形桥接） |
| `app/models/grid_pattern.py` | 2D 像素网格图案（安全裁剪、轻量编辑载荷、单格/矩形修色、版本化工程导入导出、Tapestry / C2C / 十字绣） |
| `app/models/colors.py` | 共享毛线色表 + CIEDE2000 感知色差（官方 34 组测试数据锁定） |
| `app/models/subject.py` | GrabCut 主体分割（色带/剖面/色板共用的主体掩码；失败回退背景阈值启发式） |
| `app/models/pose.py` | 姿态关键点实测部件分段（可选依赖 [pose]；回退 PART_SPAN 先验） |
| `app/models/validator.py` | 图解自检（逐圈针数代数 + 当前密度塑形上限，结果页徽章） |
| `app/models/ring_chart.py` | 环形圈数图 SVG（部件顶视图，物理半径配色环） |
| `app/utils/history.py` | 图解历史持久化（SQLite 单文件，跨会话载回） |
| `app/utils/pdf_export.py` | PDF 图解导出（可选依赖 [pdf]，中文 CID 字体） |
| `app/models/orchestrator.py` | 流水线协调器（便于单元测试） |
| `app/schemas.py` | Pydantic 数据模型（含值域校验；`PART_NAMES` 为规范部件名单一来源） |
| `app/prompts/vision_parser.txt` | Vision API 提示词模板（随 wheel 打包，见 pyproject package-data） |
| `app/data/external-trial-evidence.json` | 精选网络试钩上下文（带来源与复用边界，随 wheel 打包且禁止参与自动校准） |

## 单图局限性

- 背面厚度由常识推算，存在不确定性
- 当前结构层虽显式记录旋转、归一化三维位置和连接节点，但这些字段来自
  模板先验，不是单张照片恢复出的深度测量或完整三维网格
- 单张照片无法测得绝对头径/身高；系统只取相对比例，厘米目标由用户选择
- 所有数值均可通过 UI 的「局部修正」JSON 编辑器手动调整
- 结果页「调整部件结构（高级）」可校验并修改结构 v2，随后在本地重新生成
  针法与装配说明，不会再次调用 AI

## 已实现（曾列于路线图）

- ~~PDF 打印导出~~（`utils/pdf_export.py`，reportlab，`pip install .[pdf]`）
- ~~图解历史记录~~（`utils/history.py`，SQLite 本机持久化）

## 扩展路线图

1. **多角度输入** — 接入侧面/背面照片辅助 3D 结构推理（单图 3D 重建设计见 `docs/3d-reconstruction-design.md`）
2. **预设模板库** — 常见体型快速原型
3. **针法类型扩展** — hdc / dc 切换、螺旋织 vs 圈织
4. **服务端同步 / 跨设备迁移** — 历史记录当前仅本机
5. **针法图形化** — 生成标准钩织符号图（现有环形图为顶视图近似）
