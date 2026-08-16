# 🧶 CrochetPhoto2Pattern

> AI 驱动的 Amigurumi 立体人物钩织图解生成器：从一张照片自动生成完整钩织方法。

## ✨ 功能

- 📷 上传照片（正面为主，侧面辅助照片规划中）
- 🧮 无 LLM 模式：本地人脸检测推算头身比例 + 轮廓识别（下摆展开自动加裙子），零 API 成本
- 🎨 照片配色设计：纵向色带映射到逐圈毛线色，自动生成换线说明；AI 模式识别发色/上衣/下装直达部件配色\n- 🖩 网格缩放算法可选：照片平滑（LANCZOS）/ 像素画锐利（NEAREST）
- 🤖 AI 视觉解析人物特征（支持 OpenAI GPT-4o / Anthropic Claude）
- 🧊 自动设计 3D 立体结构
- 🧶 生成完整钩织参数（针数、加减针、逐圈步骤）
- 📝 结构化输出（JSON + 可视化表格）
- ✏️ 支持局部修正和重新生成
- 🟦 2D 像素网格图案（Tapestry / C2C / 十字绣）
- ✅ 逐圈钩织进度追踪
- 💾 完整结果备份/导入（JSON，跨会话恢复）
- 🖼️ EXIF 方向自动修正（手机竖拍照片直出正确比例）

## 🛠 技术栈

- Python 3.9+
- Streamlit（交互 UI）
- OpenAI / Anthropic API（Vision + Reasoning）
- Pydantic v2（数据验证）

## 🚀 快速开始

### 安装

```bash
cd CrochetPhoto2Pattern
pip install -e .
```

### 配置

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY 或 ANTHROPIC_API_KEY
```

Key 优先级：**侧栏输入框 > `.env`**。在侧栏输入框中清空内容即可停用对应
Key（下次运行自动回退到 `.env` 或 Mock 模式）。模型名也可用环境变量覆盖：
`ANTHROPIC_VISION_MODEL`（默认 claude-sonnet-5）、`OPENAI_VISION_MODEL`（默认 gpt-4o）。

> 💡 不设置 API Key 也可以运行：照片 Tab 可选「本地视觉估算」（OpenCV 人脸检测推算比例，头径按 9cm 锚定）或 Mock 演示；手动/网格 Tab 本就无需 Key。
> ⚠️ 请勿在多人共享的 Streamlit 部署上输入 API Key。

### 运行

```bash
streamlit run app/main.py
```

### Docker（可选）

```bash
docker build -t crochet-photo2pattern .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=sk-ant-... crochet-photo2pattern
```

### 测试

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## 📐 处理流程

```
照片上传 → Vision 解析 → 3D 结构设计 → 钩织参数生成 → 结构化输出 → 用户修正
```

详见 [docs/flow.md](docs/flow.md)

## 📁 项目结构

```
CrochetPhoto2Pattern/
├── app/
│   ├── main.py              # Streamlit 入口（薄壳：配置 + Tab 分发）
│   ├── schemas.py           # Pydantic 数据模型
│   ├── models/
│   │   ├── image_parser.py  # Vision API 图像解析
│   │   ├── structure_designer.py  # 3D 结构设计
│   │   ├── crochet_params.py      # 钩织参数生成
│   │   ├── grid_pattern.py        # 2D 像素网格图案
│   │   ├── colors.py              # 共享毛线色表 + Lab 感知色距
│   │   └── orchestrator.py        # 流水线编排
│   ├── ui/
│   │   ├── sidebar.py             # API Key 配置
│   │   ├── tab_photo.py           # 照片识别 Tab
│   │   ├── tab_manual.py          # 手动输入 Tab
│   │   ├── tab_grid.py            # 2D 网格 Tab
│   │   └── result_renderer.py     # 结果渲染（进度/修正/导出）
│   ├── utils/
│   │   ├── exporters.py           # Markdown 导出
│   │   └── images.py              # 上传图片安全加载（容错/大小限制）
│   └── prompts/             # LLM 提示词模板
├── tests/                   # 自动化测试
├── docs/                    # 文档
└── pyproject.toml           # 项目配置（依赖单一来源）
```

## 📄 License

MIT
