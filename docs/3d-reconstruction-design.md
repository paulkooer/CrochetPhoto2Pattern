# 单图 3D 重建 → 图解管线设计（S6，未实施）

**简体中文** | [English](3d-reconstruction-design.en.md) | [文档索引 / Documentation index](README.md)

> 状态：**设计文档**。需要 GPU（TRELLIS ~16GB 显存 / TripoSR 8GB+ 或慢速
> CPU），无法在当前开发环境验证，不进默认依赖。本文记录选型结论与集成
> 设计，待有 GPU 环境时按此实施。

当前已实现的 `StructureGeometry v2` 只把模板先验变成可验证的部件图谱
（归一化位置、旋转、镜像实例、数量、连接锚点）；它没有生成 mesh，也没有
从照片恢复深度，因此不等同于本文规划的学习式单图 3D 重建。

## 1. 研究依据

- **TRELLIS**（Microsoft, arXiv:2412.01506, MIT 协议）——SLAT 结构化潜
  表示，单图→Radiance Field/3D Gaussian/**mesh**，质量当前最优。
- **TripoSR**（Stability AI + VAST-AI, arXiv:2403.02151）——A100 上
  0.5s/图，CPU 可跑（分钟级），质量较粗但够做截面。
- **AmiGo**（本仓已核实，arXiv:2211.01178）——mesh → crochet 图解的
  既有范式：按行距 w 的等距水平切片，每圈针数 = 截面周长 / 针宽。

## 2. 管线设计

```
照片 → [现有] 主体分割（GrabCut，白底化输入）→ 去背景
     → TripoSR/TRELLIS → 三角网格（GLB）
     → 体素化/按 y 等距切片（行距 = gauge.row_h_cm）
     → 每层截面 → 周长 → 针数 = 周长/针宽，量化到 6 的倍数
     → ±6 钳制 + 三点平滑（复用 profile_to_rounds 的下游约束）
     → 与现有 profile 身体件同一接口（type="profile" 的加强版）
```

关键点：
- **只替换"身体"部件的形状来源**（旋转体假设 → 真实 3D 截面），头/四肢
  仍走现有模板/比例路径——AmiGo 的全网格 crochet graph 拓扑生成不在
  本阶段范围（branching/join-as-you-go 复杂度高）。
- 切片间距用 `gauge.row_h_cm`，与"标注高度=实际钩出高度"口径一致。
- 非圆形截面（如坐姿扁平）取**等效周长**而非等效直径，这是比旋转体假设
  本质更准的地方。

## 3. 集成方式（届时）

- 新可选依赖 `pipeline3d = ["tripoSR @ git+...", "rembg"]` 或独立
  service（模型常驻避免冷启动）。
- `app/models/body3d.py`：`mesh_to_rounds(mesh, gauge) -> List[int]`，
  输入 trimesh 对象，输出与 `profile_to_rounds` 同构的筒壁序列。
- orchestrator：`use_3d=True` 且依赖可用时走 3D 路径，失败回退剖面路径
  （与 S1 pose 的可选能力模式相同）。
- 侧栏加"3D 重建（实验）"开关，标注 GPU 要求。

## 4. 风险

- 单图重建对照片外的部分（背面）是幻觉——玩偶对称性先验可缓解
  （左右镜像对称化截面）。
- 网格毛刺 → 截面周长噪声：切片前需 Laplacian 平滑或体素化（marching
  cubes 体素边长 ≈ 针宽/2）。
- 许可：TRELLIS MIT ✓；TripoSR 模型权重 MIT，代码 Apache-2.0 ✓。
