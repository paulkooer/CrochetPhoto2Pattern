# 系统处理流程

## 四步流水线

```
照片上传
   ↓
1. 图像预处理（PIL 缩放 + RGB 转换）
   ↓
2. 人物语义解析（Vision API — OpenAI GPT-4o 或 Anthropic Claude）
   输出：体型、部件列表、关键特征、姿态、头径、身高、难度
   ↓
3. 立体结构设计（StructureDesigner）
   输出：每个部件的基本形状 + 比例（sphere / cylinder / cone）
   ↓
4. 钩织参数生成（CrochetParamsGenerator）
   输出：每个部件的圈数序列、针数、加减针、材料、装配说明
   ↓
JSON 输出 + Streamlit UI 展示 + 用户局部修正 + 下载 + 完整结果备份/导入
```

## 代码模块

| 文件 | 职责 |
|------|------|
| `app/main.py` | Streamlit 入口（薄壳：全局配置 + Tab 分发） |
| `app/ui/` | 界面组件：侧栏、三个 Tab、结果渲染（进度追踪 / 局部修正 / 下载） |
| `app/utils/exporters.py` | Markdown 图解导出 |
| `app/utils/images.py` | 上传图片安全加载（损坏文件/超限大小的友好错误） |
| `app/models/image_parser.py` | Vision 调用（Anthropic structured outputs 优先 → 失败降级 OpenAI → 无 key 时 Mock）；`parse_image_local` 为无 LLM 路径入口 |
| `app/models/local_vision.py` | 无 LLM 本地视觉估算（人脸检测 → 头身比例；轮廓剖面 → 下摆展开自动加裙子） |
| `app/models/color_design.py` | 照片纵向色带 → 部件逐圈配色 + 换线说明（换线由照片颜色驱动） |
| `app/models/structure_designer.py` | 2D → 3D 结构映射 |
| `app/models/crochet_params.py` | 钩织圈数算法（球形/圆柱辅助函数） |
| `app/models/grid_pattern.py` | 2D 像素网格图案（Tapestry / C2C / 十字绣） |
| `app/models/colors.py` | 共享毛线色表 + CIE Lab 感知色距 |
| `app/models/orchestrator.py` | 流水线协调器（便于单元测试） |
| `app/schemas.py` | Pydantic 数据模型（含值域校验；`PART_NAMES` 为规范部件名单一来源） |
| `app/prompts/vision_parser.txt` | Vision API 提示词模板（随 wheel 打包，见 pyproject package-data） |

## 单图局限性

- 背面厚度由常识推算，存在不确定性
- 头径/身高是估算值，建议试钩小样后调整
- 所有数值均可通过 UI 的「局部修正」JSON 编辑器手动调整

## 扩展路线图

1. **多角度输入** — 接入辅助角度照片（UI 已预留入口）
2. **PDF 打印导出** — 材料清单 + 分页圈数表 + 装配图示（reportlab / weasyprint）
3. **图解历史记录 / 预设模板库** — 结果持久化与常见体型快速原型
4. **针法类型扩展** — hdc / dc 切换、螺旋织 vs 圈织
5. **CrewAI 多 Agent 流水线** — 专业分工提升各阶段质量
6. **针法图形化** — 生成标准钩织符号图
