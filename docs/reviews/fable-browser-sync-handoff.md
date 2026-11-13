# Fable 5.2 复审修正交接

Fable 指出的两点成立：旧版对瞬时 `running` 的依赖会漏检，原三项回归也未保护“本轮完成后才返回”。这两项保证已撤回并改为下面可验证的范围。此记录是修改与验证交接，等待 Fable 再审；#86、#87 均未合并。

## 固定范围

- 复审基线：`d0d5a38237d78fa36ed169a898e126b496b74641`；旧交接为 `60f4fe5a97328d33c7ad3d71e78fdda0afecccac`。
- 新实现：[PR #86](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/86)，提交 `d93e5b528d1569f4549ba31e51866f737244b01c`。本轮相对基线变更 13 个文件。
- `app/`、既有 Python 测试、`pyproject.toml`、`uv.lock`、发布收据及校验和没有变化。Node 浏览器工具新增锁定的 `protobufjs@7.6.6`；协议字段描述由实际安装的 Streamlit 提取。
- [验证清单](fable-browser-sync-checks.json)只绑定新实现提交；后续交接提交只改文档，不把旧 CI 或后来文档的提交冒充本次代码验证。

## 两项问题如何修正

上传不再观察 DOM 的瞬时 `running`。每页先注册 WebSocket 监听，再导航到应用；每次上传按顺序匹配：HTTP 上传响应中的文件 ID、包含该 ID 的客户端 `rerun_script`、随后完整运行的 `new_session` 标识，以及相同运行 ID 的成功 `script_finished`。旧请求、错误文件、其他运行的完成消息及被中断运行不能放行。

服务端完成后，再让出两个有超时限制的绘制帧并检查连接、`notRunning`、骨架与异常。这个适配面针对当前锁定的 Streamlit 1.67、Chromium、同页顺序单文件操作；没有承诺任意并发或自动刷新链已完全静止。各等待阶段仍有 45 秒上限，原 300 ms 防抖与工作流 15 分钟总上限不变。

回归夹具增加了“上传响应已返回、刷新请求尚未执行”的受控窗口，以及运行末尾才输出的标记。`upload()` 返回后，测试先用同步 `page.evaluate` 读取末尾标记；没有定位器自动等待、后续点击或第二次 `settle` 替它补等。

CI 还实际执行两种变异：删除运行完成等待、仅等待上传响应。两者必须因为上述即时末尾断言失败才算被杀掉，模块加载或其他错误不算。没有宣称穷尽所有 helper 防御分支的变异覆盖。

## 验证结果

| 项目 | 结果 |
| --- | --- |
| 回归套件 | 本地与 CI 均 7/7；含真实浏览器流程及运行标识关联单测 |
| 无延迟夹具 | 正常速度及 8 倍 CPU 降速各 12 次首次/替换上传，共 24/24；每次返回即读末尾标记 |
| DOM 未出现 running | 本地正常/8 倍分别 0/8 次，CI 分别 2/4 次，均成功；这些计数是观测结果，不是跨环境固定断言 |
| 核心早返回变异 | 本地与 CI 均 2/2 被即时末尾断言杀掉，已作为 CI 必经步骤 |
| 完整应用流程 | 新提交的干净本地运行 30/30，远端 30/30；原场景段和内容断言与旧版逐字节一致 |
| 真实应用侧边栏 | 适配 Fable 探针后，8 倍 CPU 降速 10 次、漏检 0 次；属于负载近似，不是 CI 负载证明 |
| 新提交远端检查 | 四条流水线 13/13，全部 `run_attempt=1`，头提交均为 `d93e5b5` |
| Python 3.12 默认 dev | 远端 2966 passed、23 skipped，93.53%；PDF 在独立可选依赖作业验证 |
| 本地其他检查 | 仓库卫生 14 passed；Ruff、mypy（含协议脚本/夹具）、语法与差异检查通过 |

本轮没有在本地另跑全量 Python 测试，也没有复用上一轮本地 dev+pdf 的数量冒充新结果。新提交的四版本完整测试以本轮远端记录为准。历史失败附件与旧结果保留在[旧交接提交](https://github.com/paulkooer/CrochetPhoto2Pattern/blob/60f4fe5a97328d33c7ad3d71e78fdda0afecccac/docs/reviews/fable-browser-sync-checks.json)；原始三次失败的根因仍没有被证明。

## 再审入口

```sh
uv sync --locked --extra dev --extra pdf
npm ci --prefix scripts/browser
scripts/browser/node_modules/.bin/playwright install chromium
node --test scripts/browser/workflow_helpers.test.cjs
node scripts/browser/check_upload_mutations.cjs
```

完整应用运行见[浏览器说明](../browser-regression.md)。外部探针使用上传 helper 时，需要在 `page.goto` 前调用 `observeRuns(page)`（来自 `scripts/browser/streamlit_protocol.cjs`）；仓库主流程和回归夹具已注册。消息监听、协议提取及入口/helper 四份脚本的哈希与 Streamlit 版本均进入完整浏览器报告。

建议重点核对：文件 ID 到运行 ID 的关联、错误/中断运行不会放行、快速刷新不依赖 DOM 状态，以及两个早返回变异是否由即时末尾断言失败。#74–#85 仍按[第二轮交接](fable-round2-handoff.md)单独审查；本次没有获得它们的独立通过结论。

G3 授权真实照片与 G4 实体校准/独立验证仍阻断，#15 等待贡献者拆分；没有生成新发布证据或正式版本。
