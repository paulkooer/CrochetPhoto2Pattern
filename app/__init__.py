"""CrochetPhoto2Pattern — AI-powered amigurumi pattern generator.

产品显示名的单一来源：UI（页面标题/hero/页脚）与导出（Markdown/PDF）
统一从这里读取，避免仓库/包名与展示名各说各话（fable5.1 审核意见）。
"""
PRODUCT_NAME = "CrochetPhoto2Pattern"


def software_version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("crochet-photo2pattern")
    except PackageNotFoundError:
        return "source-tree"
