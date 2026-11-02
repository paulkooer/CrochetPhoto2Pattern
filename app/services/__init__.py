"""Application services: regeneration, import and progress logic shared by UI, CLI and tools.

不依赖 Streamlit，也不导入 ``app.ui``；界面层调用这里的函数并负责展示与会话状态。
"""
