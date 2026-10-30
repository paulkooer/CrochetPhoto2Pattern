# 浏览器流程回归 / Browser workflow regression

[文档索引 / Documentation index](README.md)

This optional Playwright suite opens the actual Streamlit app in Chromium. It uses
synthetic input and a separate single-user history database. It verifies UI interaction,
downloaded bytes and project restoration; it does not validate photo recognition or
physical crochet results. CI runs it separately from Python tests and AppTest.

## 本地运行

Python 使用仓库锁定的 dev+pdf 环境；Node 工具单独安装，不进入应用依赖。

```sh
uv sync --locked --extra dev --extra pdf
npm ci --prefix scripts/browser
scripts/browser/node_modules/.bin/playwright install chromium
```

在一个终端启动隔离测试服务。下面的临时目录专用于本轮测试，勿指向日常历史库。

```sh
task_browser_dir=$(mktemp -d)
printf '%s\n' "$task_browser_dir"
CROCHET_HISTORY_MODE=single_user \
CROCHET_HISTORY_DB="$task_browser_dir/history.sqlite" \
CROCHET_POSE_MODEL="$task_browser_dir/unconfigured-pose.task" \
.venv/bin/python -m streamlit run app/main.py \
  --server.address=127.0.0.1 --server.port=18502 \
  --server.headless=true --browser.gatherUsageStats=false
```

另一个终端在仓库根目录运行；输出放在另一个临时目录，路径写入脚本日志。

```sh
CROCHET_PLAYWRIGHT_MODULE="$PWD/scripts/browser/node_modules/playwright" \
node scripts/check_mask_canvas.cjs
node scripts/check_browser_workflow.cjs
```

可用 `CROCHET_BROWSER_URL` 指定其他本机端口，用 `CROCHET_BROWSER_OUTPUT` 指定证据目录。
脚本拒绝非本机地址；请先核对该端口确实对应隔离服务。若使用现有浏览器，两个脚本
都支持 `CROCHET_CHROME_EXECUTABLE`，例如 macOS 的
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`。
结束后在服务终端按 Ctrl-C。修改 Python 业务模块后应重启测试服务，避免旧导入留在进程中。

## 验证内容

| 流程 | 检查依据 |
|---|---|
| 上传合成 PNG 并准备照片复核 | 实际文件上传控件、准备按钮与复核页面 |
| 应用内主体画布 | 增补、擦除、撤销、重置及传回 Streamlit 的组件消息 |
| 照片完整人工确认 | 主体选择、比例修改、生成与已确认来源提示 |
| 备份、参数、Markdown、PDF 下载 | 下载事件、JSON 内容对照、部件名称、PDF 文件头；备份不携带修正遮罩 |
| 命名历史首次保存、撤销、再保存 | 原名称仍可检索，载入按钮仍指向同一记录 |
| 工程保存 | 下载文件包含当前完成圈次与个人备注 |
| 手动页保存后载入照片页 | 展示 ID 不同，进度和备注分别保留 |
| 独立浏览器上下文恢复 | 重新上传工程、恢复勾选与备注，重导出核对参数、进度与备注 |
| 无效文件导入 | 显示导入失败，并保留当前图解、进度与备注 |

独立画布脚本另检查连续拖动笔画。页面断言会等待实际控件更新，避免把 WebSocket
刷新尚未结束当成保存错误。Python 的 `test_history_title_lifecycle.py` 进一步覆盖
旧预览应用、撤销/重做、未保存名称草稿、显式清空名称，以及数据库列和序列化内容一致。

## 证据和边界

`report.json` 记录代码提交、脚本 SHA-256、工作树是否干净、浏览器版本、各检查结果、
页面异常和被拦截的外部请求。文件目录还保留合成输入、下载结果与截图；失败时增加
页面 HTML 和截图。跨上下文恢复不共享浏览器会话，但两者访问同一隔离测试服务。

[browser 工作流](../.github/workflows/browser.yml) 安装锁定的 Playwright 与其 Chromium，
运行独立画布及完整应用流程；合成证据和服务日志保留 7 天。PR 运行记录同时保留头提交
和实际检出提交，不能把旧 SHA 的成功结果算作新 SHA 通过。

本套覆盖桌面 Chromium 的上述合成路径；Safari、Firefox、移动端、真实照片交互、
大文件与低内存压力测试仍需另行验证。它不改变 G3/G4，也不证明尺寸、耗线或实物效果。

`Downloads/gz` 的本地参考图解诊断单独放在忽略的 `eval_outputs/` 下。原图片、PDF、
裁剪和私人报告不进入本工作流、公开仓库或上传证据。

Playwright 原始文档：[下载事件](https://playwright.dev/docs/downloads)、
[隔离上下文](https://playwright.dev/docs/browser-contexts)、[CI](https://playwright.dev/docs/ci)。
