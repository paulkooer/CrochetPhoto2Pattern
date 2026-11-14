# 浏览器流程回归 / Browser workflow regression

[文档索引 / Documentation index](README.md)

This optional Playwright suite opens the actual Streamlit app in Chromium. It uses
synthetic SVG/PNG, a CLI-generated manual garment pattern, and a separate single-user history database. It verifies UI interaction,
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
node --test scripts/browser/workflow_helpers.test.cjs
node scripts/browser/check_upload_mutations.cjs
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
| 平面网格全图换色 | 上传合成网格工程，替换已有色板颜色；核对下载的工程与 Markdown、未使用色的零格图例以及撤销/重做后的工程内容；见[合成截图](images/grid-recolor-synthetic.png) |
| 应用内主体画布 | 增补、擦除、撤销、重置及传回 Streamlit 的组件消息；检查 iframe 实际接收外层主题 |
| 照片完整人工确认 | 主体选择、比例修改、生成与已确认来源提示；「来源与限制」默认折叠，结构表不含开发者坐标列，并说明当前基础色与原始结构色，坐标说明随「查看结构 JSON」 |
| 图解纸选中与进度状态 | Tab 键盘焦点、Tab/Radio 选中颜色；连续勾选三圈后面板仍展开、进度正确、勾选行整行高亮 |
| 备份、参数、Markdown、PDF 下载 | 下载事件、JSON 内容对照、部件名称、PDF 文件头；备份不携带修正遮罩 |
| 待选颜色与备份 | 手动图解显示待选肤色，Markdown 写出中文待选标签，备份仍保存 `skin` / `body` |
| 旧结构自定义部件编号 | 合成旧备份含字典或列表型 `part_id`；实际导入后结果页正常渲染，重新下载的结构保持一致，截图随 CI 工件保存 |
| 无法识别的复核记录 | 合成备份含字符串复核标记和无效头部框；结果页提示重新核对，Markdown 不声称已确认，备份保留原字段 |
| 命名历史首次保存、撤销、再保存 | 原名称仍可检索，载入按钮仍指向同一记录 |
| 工程保存 | 下载文件包含当前完成圈次与个人备注 |
| 手动页保存后载入照片页 | 展示 ID 不同，进度和备注分别保留 |
| 独立浏览器上下文恢复 | 重新上传工程、恢复勾选与备注，重导出核对参数、进度与备注 |
| 无效文件导入 | 显示导入失败，并保留当前图解、进度与备注 |
| 独立头部留口 | 预览尚未应用时备份保持闭合；应用 16 针开口、保存工程、新上下文恢复后设置仍为 16；再次关闭后导出恢复闭合模板 |
| 帽子独立密度 | 默认 30×32、帽子 26×28；预览不替换当前结果，应用后其他部件圈序不变、头部进度保留、帽子进度清除；实际下载含部件密度，新上下文恢复设置和进度，单小样试钩入口禁用 |
| 称重试片来源密度 | 录入 30×32 称重试片并固定帽子 30×32；保存合成试钩小样 26×28 后预览应用默认密度重算，帽子、实测依据及进度保留；实际下载的材料按实测/经验分别加总，新上下文恢复仍保留原试片密度 |
| 材料预览与重复提交 | 预览线标变化并实际下载核对当前备份未变，取消后再次预览、应用、撤销；材料及尺寸原样提交保留展示 ID、尺寸来源和重做，重做后下载与已应用材料一致，进度、备注和试片来源保留 |
| 旧实体进度冲突 | 旧工程须先选择恢复无歧义进度，保留其他部件和备注；重新勾选第二份、实际下载工程并在新上下文恢复后，两份进度保持隔离；见[合成截图](images/progress-collision-recovery-synthetic.png) |
| 390 px 窄视口 | 标题单行、头栏不透明且无 Deploy 按钮；打开侧栏抽屉后滑入到位，顺序与桌面一致；保留合成截图 |
| 侧栏信息架构 | 桌面与 390 px 抽屉中的顺序均为：编织密度 → 塑形选项 → 打开已有工作（打开备份图解、打开试钩包、我的图解（历史））；保留两种视口的侧栏截图 |
| 局部修正的分层与 JSON 草稿 | 「高级编辑（JSON）」默认折叠，备份/JSON/Markdown 下载不在任何折叠面板内；两段编辑器由「启用 JSON 编辑器」按钮按需挂载，未启用时页面上没有对应 text_area；填入 JSON 草稿后预览尺寸修改、取消预览，草稿与两处提示保留且下载 JSON 仍为已应用图解；重新生成后下载包含修改 |
| 部件级选色 | 预览列出受影响圈次且显示「已钩出的旧颜色不会因为图解改色而改变」；取消后下载 JSON 仍为原图解；应用后记录 `color_origin`、逐圈针数不变、已完成圈次保留；撤销回到原色、重做恢复新色；逐份选色经 JSON 编辑应用后，Markdown 与 CrochetPARADE 导出按份体现，并在新上下文恢复逐份颜色与进度；390 px 视口下选色面板无横向溢出 |
| 自定义显示色 | 选择「自定义颜色名…」，填写名称并在取色器中设定显示色；应用后备份同时保存名称与 `display_colors`，Markdown 写出屏幕示意说明，PDF 以 `%PDF-` 开头，Parade 写出 `COLOR:` 和「不是品牌色号」注释，且不把 `skin`/`body` 示意色写成 `COLOR:`；撤销去掉显示色，重做恢复；工程在新上下文恢复后名称与显示色仍在 |
| 切换自定义名称 | 切到新名称时预览中性灰，切回已有名称时不改写其原有显示色；修改已有显示色时，预览展示变化及同名共享说明，取消预览不改变图解 |

独立画布脚本另检查连续拖动笔画。页面断言会等待实际控件更新，避免把 WebSocket
刷新尚未结束当成保存错误。Python 的 `test_history_title_lifecycle.py` 进一步覆盖
旧预览应用、撤销/重做、未保存名称草稿、显式清空名称，以及数据库列和序列化内容一致。
完整应用脚本共 30 条流程；独立密度用例的输入由当前锁定环境中的 `app.cli` 生成，
不读取私人参考资料，不代表照片识别或实体试钩。密度输入按数值含义核对，兼容控件的小数显示格式。
称重与试钩表单中的测量值均为合成软件输入，不代表做过实物测量。

## 证据和边界

`report.json` 记录代码提交、脚本 SHA-256、工作树是否干净、浏览器版本、各检查结果、
页面异常和被拦截的外部请求。文件目录还保留合成输入、下载结果与截图；失败时增加
页面 HTML 和截图。跨上下文恢复不共享浏览器会话，但两者访问同一隔离测试服务。

[browser 工作流](../.github/workflows/browser.yml) 安装锁定的 Playwright 与其 Chromium，
运行独立画布及完整应用流程；合成证据和服务日志保留 7 天。PR 运行记录同时保留头提交
和实际检出提交，不能把旧 SHA 的成功结果算作新 SHA 通过。

### 异步同步与失败诊断

运行提示的显示属于界面表现，不能据此判定 Python 已完成。同步 helper 核对连接状态、
脚本 `notRunning` 状态及骨架元素消失；状态字段来自
[Streamlit 1.67 的应用根节点](https://github.com/streamlit/streamlit/blob/1.67.0/frontend/app/src/App.tsx#L2878-L2887)。
`notRunning` 仅用于检查当前界面空闲，不再用瞬时的 DOM `running` 变化识别上传刷新。
每页在导航前注册 WebSocket 监听，15 处上传按下面的消息顺序等待：成功的上传响应给出
文件 ID → 客户端 `rerun_script` 包含该 ID → 随后的完整运行 `new_session` → 同运行 ID 的
成功 `script_finished`。旧请求、不同文件/运行的结束消息及被中断的运行不能放行。
消息字段见 [Streamlit 1.67 协议](https://github.com/streamlit/streamlit/blob/1.67.0/proto/streamlit/proto/ForwardMsg.proto)。

协议描述从实际安装的 Streamlit 提取，浏览器工具使用锁定的 protobuf.js 解码；它只增加
Node 测试依赖，不改变应用依赖。这个适配面服务于当前锁定的 Streamlit 1.67 和顺序执行的
单文件上传流程，前提是**上传前无未决重跑请求**。关联只能识别请求之后开始的完整运行，
不能证明该运行消费了该请求；较早排队的请求可能在上传请求之后才开始并被接受。
上传前的 `settle()` 观察界面空闲，不能证明服务端队列为空；这条残余竞态尚未实跑坐实。
升级框架须重新验证消息格式，不能把它当成任意并发/自动刷新的通用保证。
服务端完成消息后再让出两个绘制帧并检查界面。原 300 ms 防抖不变；上传响应、运行完成、
绘制及各界面条件分别有 45 秒上限，工作流整体仍为 15 分钟，不保证整条流程只需 45 秒。

WebSocket 关闭会让当前页的监听记录持续失败，即使已重连也不恢复上传。继续操作需要
新建页面并在导航前注册监听；本 helper 尚不支持同页重连后恢复。
发送/接收消息的解码或断言异常、页面关闭也会置位同一错误记录，使该页持续失败关闭。
关闭事件报错中的 `during upload` 不保证故障发生在上传期间，也可能是在上传开始前。

下载在点击前监听事件，同时为点击和事件等待安装拒绝处理。点击失败时，后续关闭浏览器
不会用未处理的下载等待异常覆盖原始点击错误；所有下载内容断言仍保留。
事件监听顺序遵循 [Playwright 下载说明](https://playwright.dev/docs/downloads)。

七项回归包含：上传响应后仍未开始运行的受控窗口、慢运行尾部、无延迟夹具在正常及
8 倍 CPU 降速下的首次/替换上传、HTTP 失败、运行标识匹配及下载错误传播。
上传返回后用同步 DOM 读取断言末尾标记，不用会自行等待的定位器断言掩盖早返回。
CI 还分别删除“运行完成等待”和改成“只等上传响应”，要求两种变异都由该末尾断言杀掉。
这些检查在完整 30 条流程前执行，均不设置失败重试。完整报告保留 `harness_sha256`，
`harness_files_sha256` 覆盖入口、helper、协议监听及描述提取脚本，并记录 Streamlit 协议版本。

本套覆盖桌面 Chromium 的上述合成路径及 390 px 窄视口检查；Safari、Firefox、真实移动设备、真实照片交互、
大文件与低内存压力测试仍需另行验证。它不改变 G3/G4，也不证明尺寸、耗线或实物效果。

`Downloads/gz` 的本地参考图解诊断单独放在忽略的 `eval_outputs/` 下。原图片、PDF、
裁剪和私人报告不进入本工作流、公开仓库或上传证据。

Playwright 原始文档：[下载事件](https://playwright.dev/docs/downloads)、
[隔离上下文](https://playwright.dev/docs/browser-contexts)、[CI](https://playwright.dev/docs/ci)。
