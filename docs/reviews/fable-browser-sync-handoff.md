# Fable 5.2 复审修正交接

Fable 此前复审确认，旧版瞬时 `running` 依赖与即时末尾断言缺口均已修正，未发现阻断 #86 合并的缺陷。但其复审因权限分类器不可用而未完成，不能记为全部独立验证通过。此交接保留已验证结果及下面的适用前提；#86、#87 均未合并。

## 固定范围

- 复审基线：`d0d5a38237d78fa36ed169a898e126b496b74641`；旧交接为 `60f4fe5a97328d33c7ad3d71e78fdda0afecccac`。
- 新实现：[PR #86](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/86)，提交 `d93e5b528d1569f4549ba31e51866f737244b01c`。本轮相对基线变更 13 个文件。
- `app/`、既有 Python 测试、`pyproject.toml`、`uv.lock`、发布收据及校验和没有变化。Node 浏览器工具新增锁定的 `protobufjs@7.6.6`；协议字段描述由实际安装的 Streamlit 提取。
- [验证清单](fable-browser-sync-checks.json)只绑定新实现提交；后续交接提交只改文档，不把旧 CI 或后来文档的提交冒充本次代码验证。
- #86 保持 Fable 已复核的 `d93e5b5` 不变；关联测试补强单独见 [#88](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/88)，提交 `adeabbffd5086657cc1ab360c2439e7e1a091ae4`，尚未并入 #86/#87。#87 相对 #86 仅有五份文档/导航文件变化。

## 两项问题如何修正

上传不再观察 DOM 的瞬时 `running`。每页先注册 WebSocket 监听，再导航到应用；每次上传按顺序匹配：HTTP 上传响应中的文件 ID、包含该 ID 的客户端 `rerun_script`、随后完整运行的 `new_session` 标识，以及相同运行 ID 的成功 `script_finished`。旧请求、错误文件、其他运行的完成消息及被中断运行不能放行。

服务端完成后，再让出两个有超时限制的绘制帧并检查连接、`notRunning`、骨架与异常。这个适配面针对当前锁定的 Streamlit 1.67、Chromium、同页顺序单文件操作，且要求**上传前无未决重跑请求**；没有承诺任意并发或自动刷新链已完全静止。各等待阶段仍有 45 秒上限，原 300 ms 防抖与工作流 15 分钟总上限不变。

当前协议关联的是上传请求之后开始的完整运行，不证明该运行消费了上传请求。若较早排队的请求尚未开始，其运行可能在上传请求之后才发 `new_session` 并成功结束，从而被接受。上传前的 `settle()` 只能观察界面空闲，不能证明服务端请求队列为空。此竞态目前仅有 Fable 的源码推断，未实跑坐实，也未在本轮修复。

WebSocket 一旦关闭，该页监听记录会持续报错，即使随后重连，后续上传也会失败关闭。需要继续时应重新创建页面，在导航前注册监听；当前 helper 不支持同页重连后恢复上传。

发送/接收消息的解码异常、消息处理中的断言异常，以及页面关闭，也会把同一 `log.error` 置位，使该页后续上传持续失败关闭。关闭事件的报错包含 `during upload`，但事件也可能发生在上传开始前；文案不能用来判断故障发生的时点。本轮只补充说明，不改已复核的错误处理或文案。

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

## 最新独立复审与测试补强

Fable 在 `200c108` 实跑 7/7 回归、24/24 无延迟上传（正常/8 倍下 DOM 未出现 `running` 为 0/8 次）、2/2 早返回变异，并向 GitHub 核对 #86 的 13/13。完整 30 条流程、真实应用 8 倍探针、#87 的检查和运行次数，以及 CI 的 DOM 缺失计数，均未被其独立复核；上表仍是工程侧验证记录。

2026-11-14 的增量复审只读完 `822c79d` 的说明与五份相关源码，未发现表述与源码不符；没有实跑。Fable 的 Bash 权限分类器持续限流，本地又未检出 #88，因此 `adeabbf` 的改动完全未被独立审到。“五份文档变化”和全部验证数字也未被本轮独立核实；不能将本轮记为独立复审通过。

后续 [#88](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/88) 增加两个关联事件序列：完整运行在上传请求前开始，以及请求之后仅有片段运行完成。它们都必须保持等待，直到后续完整运行结束。变异驱动实际放宽请求时序和移除片段过滤，并要求退出码 1 且出现各自指定的断言文本；原两种早返回变异仍执行。本地为 9/9、快速上传 24/24、四种变异 4/4 被杀。新增测试不证明上述排队竞态已被解决；其 CI 查看固定头提交 `adeabbf` 的 [PR 检查](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/88/checks)，不混入 `d93e5b5` 的验证数量。

无需 Bash 的只读入口：固定提交 [adeabbf](https://github.com/paulkooer/CrochetPhoto2Pattern/commit/adeabbffd5086657cc1ab360c2439e7e1a091ae4) 的完整差异，以及[两个新增事件序列](https://github.com/paulkooer/CrochetPhoto2Pattern/blob/adeabbffd5086657cc1ab360c2439e7e1a091ae4/scripts/browser/workflow_helpers.test.cjs#L217)、[四种变异驱动](https://github.com/paulkooer/CrochetPhoto2Pattern/blob/adeabbffd5086657cc1ab360c2439e7e1a091ae4/scripts/browser/check_upload_mutations.cjs)、[CI 步骤](https://github.com/paulkooer/CrochetPhoto2Pattern/blob/adeabbffd5086657cc1ab360c2439e7e1a091ae4/.github/workflows/browser.yml)。GitHub 连接器可读取提交、工作流元数据与作业日志；读取资料不等于独立重跑测试。

工程侧于 2026-11-14 重新向 GitHub 核对 `822c79d` 与 `adeabbf`：各四条流水线、13/13，头提交和 `run_attempt=1` 均匹配。检查清单的 `review_access_verification` 给出固定运行 ID；这些是现有运行的重新读取，不是本轮新跑的 CI，也不是 Fable 的验证结果。

## 再审入口

```sh
uv sync --locked --extra dev --extra pdf
npm ci --prefix scripts/browser
scripts/browser/node_modules/.bin/playwright install chromium
node --test scripts/browser/workflow_helpers.test.cjs
node scripts/browser/check_upload_mutations.cjs
```

上述命令在 #86/#87 上仍执行七项回归与两种变异；检出 #88 的 `adeabbf` 后为九项回归与四种变异。

完整应用运行见[浏览器说明](../browser-regression.md)。外部探针使用上传 helper 时，需要在 `page.goto` 前调用 `observeRuns(page)`（来自 `scripts/browser/streamlit_protocol.cjs`）；仓库主流程和回归夹具已注册。消息监听、协议提取及入口/helper 四份脚本的哈希与 Streamlit 版本均进入完整浏览器报告。

建议重点核对：文件 ID 到运行 ID 的关联、错误/中断运行不会放行、快速刷新不依赖 DOM 状态，以及两个早返回变异是否由即时末尾断言失败。#74–#85 仍按[第二轮交接](fable-round2-handoff.md)单独审查；本次没有获得它们的独立通过结论。

G3 授权真实照片与 G4 实体校准/独立验证仍阻断，#15 等待贡献者拆分；没有生成新发布证据或正式版本。
