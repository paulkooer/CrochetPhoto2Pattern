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
JSON 输出 + Streamlit UI 展示 + 用户局部修正 + 下载
```

## 代码模块

| 文件 | 职责 |
|------|------|
| `app/main.py` | Streamlit UI 入口，分步调用各阶段 |
| `app/models/image_parser.py` | Vision API 调用（OpenAI + Anthropic 双通道，Mock 降级） |
| `app/models/structure_designer.py` | 2D → 3D 结构映射 |
| `app/models/crochet_params.py` | 钩织圈数算法（球形/圆柱辅助函数） |
| `app/models/orchestrator.py` | 流水线协调器（便于单元测试） |
| `app/schemas.py` | Pydantic 数据模型（含值域校验） |
| `app/prompts/vision_parser.txt` | Vision API 提示词模板 |

## 单图局限性

- 背面厚度由常识推算，存在不确定性
- 头径/身高是估算值，建议试钩小样后调整
- 所有数值均可通过 UI 的「局部修正」JSON 编辑器手动调整

## 扩展路线图

1. **多角度输入** — 接入辅助角度照片（UI 已预留入口）
2. **Markdown 图解导出** — 除 JSON 外输出可打印的钩织图解
3. **CrewAI 多 Agent 流水线** — 专业分工提升各阶段质量
4. **针法图形化** — 生成标准钩织符号图
