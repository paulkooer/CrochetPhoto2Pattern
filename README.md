# 🧶 CrochetPhoto2Pattern

> AI 驱动的 Amigurumi 立体人物钩织图解生成器：从一张照片自动生成完整钩织方法。

## ✨ 功能

- 📷 上传照片（正面为主，侧面辅助照片规划中）
- 🤖 AI 视觉解析人物特征（支持 OpenAI GPT-4o / Anthropic Claude）
- 🧊 自动设计 3D 立体结构
- 🧶 生成完整钩织参数（针数、加减针、逐圈步骤）
- 📝 结构化输出（JSON + 可视化表格）
- ✏️ 支持局部修正和重新生成
- 🟦 2D 像素网格图案（Tapestry / C2C / 十字绣）
- ✅ 逐圈钩织进度追踪

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

> 💡 不设置 API Key 也可以运行，将使用 Mock 数据演示

### 运行

```bash
streamlit run app/main.py
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
│   │   └── exporters.py           # Markdown 导出
│   └── prompts/             # LLM 提示词模板
├── tests/                   # 自动化测试
├── docs/                    # 文档
└── pyproject.toml           # 项目配置（依赖单一来源）
```

## 📄 License

MIT
