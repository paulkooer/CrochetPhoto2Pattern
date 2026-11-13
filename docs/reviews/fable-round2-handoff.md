# Fable 第二轮后续复核交接

本批工程修改已按步骤拆成独立 PR；以下记录是提交复核的证据，不是 Fable 的验收结论，也不是发布许可。除已独立认可的 #73 外，本批实现保留在待审 PR 中。

后续已针对本文披露的浏览器间歇失败提交独立修正，见[继续审核交接](fable-browser-sync-handoff.md)。下文仍保留本批原有提交与验证范围。

## 复核范围与入口

基线为 #73 合并后的 `60084d09db40d8f5d068980b99c632f736fc5de8`。所有实现的联合代码提交为 `72289b54e06cc24a32a8d48d70853fd38b5c291b`，位于 `review/fable-round2-integration-20261113`。其后的交接提交只维护本文、验证清单和文档导航；没有把这些结果写成新的发布收据。

逐项头提交、分支依赖、工作流与作业链接见[验证清单](fable-round2-checks.json)。清单固定记录核查时的提交，不自动覆盖后来修改的 PR。

| PR | 处理内容 | 对比基线 |
| --- | --- | --- |
| [#74](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/74) | OpenCV 4.14 / NumPy 2 锁定更新；修复两处数组归约类型兼容 | main |
| [#75](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/75) | 收据树、范围、结构与校验和检查；候选 SHA 示例；OpenCV ignore 依据；#15 当前待办 | main |
| [#76](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/76) | 生成器完整输出快照，只有测试和固定夹具 | main |
| [#77](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/77) | 按形状提取六个生成函数 | #76 分支 |
| [#78](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/78) | 生成器使用 PartKind 与保存名称边界解析 | #77 分支 |
| [#79](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/79) | 装配使用 PartKind | #78 分支 |
| [#80](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/80) | 单例评测、运行累积、报告汇总分离 | #79 分支 |
| [#81](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/81) | 试钩工具拆成模型、I/O、草稿、外部证据、分析和 CLI | #80 分支 |
| [#82](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/82) | 网格界面分区 | #81 分支 |
| [#83](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/83) | 样式表按现有章节拼接 | #82 分支 |
| [#84](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/84) | 当前 main 上更新三个 Actions 大版本，替代 #1、#3、#37 | main |

#76 → #83 是依次堆叠的 PR，建议按此顺序审查。#74、#75、#84 可独立审查。集成分支用于检查组合结果；各步骤仍以自己的 PR 为评审单位。若逐项 squash 合并，后续分支需要针对新 main 重新整理、定向和检查，不能把旧头提交的通过结果移用给新头提交。

## 对第二轮建议的回应

- OpenCV ignore 仍只限制 uv 生态的两个包的常规大版本；没有版本通配忽略。已核对固定版本的 Dependabot 实现及测试：安全更新路径不应用 `update-types` 限制，来源见[依赖更新口径](../dependency-updates.md)。`<5` 约束本身仍可能需要人工处理将来的安全迁移，不能声称配置保证任何未来修复都能安装。
- `--status` 继续离线只读；比较确切 commit 与候选 tree，拒绝 `covers_later_commits` 非 false、缺失/失败检查组、不同树的 audit 及无效校验和。新增 `.sha256`，原 `release-evidence.json` 字节不变。写入仍要求显式候选与 audit 提交。校验和检测单边误改，不是签名或远端真实性认证；同时篡改文件及校验和仍不在本地检查能力内。
- 中英文状态页示例改用 `<candidate-sha>`。旧收据仍是历史记录，当前候选不能借用它。测试不再固定旧日期/运行号，但真实文件的校验和会拦截只改收据的情况。
- [#15 拆分回复已发布](https://github.com/paulkooer/CrochetPhoto2Pattern/pull/15#issuecomment-6844025531)，待办从 archive 移到 [reviews/pr-15-followup.md](pr-15-followup.md)。原 PR 保持开放等待贡献者拆分，代码没有验收或合并。
- #1、#3、#37 已关闭，由 #84 接管；这表示提议被替代，不表示 Actions 更新已进入 main。#4 由 Dependabot 关闭后，现有 #74 承接图像依赖升级；其最初失败的两个类型检查已修正。
- 用户确认后删除旧 stash；删除前再次核对它的对象 ID 与备份 bundle。原本地改动、分支和工作树清理的恢复备份仍保留在本机临时目录中。

## 行为保持证据

以下函数行数按 Python AST 的函数起止行计算，不含装饰器；与人工计数口径可能略有差异。

| 入口 | 基线 → 当前 | 关键约束 |
| --- | --- | --- |
| generate_params | 381 → 142 | 六类形状 helper；准备、分派与公共后处理仍在主入口 |
| evaluate_dataset | 338 → 19 | 授权/冻结读取、失败计数、阈值和完整报告不变 |
| app.trials 文件 | 1189 → 262 | 兼容入口保留原 69 个公开名称、私有 helper 和命令入口 |
| render_tab_grid | 353 → 15 | 控件键、文案、调用顺序、缓存、异常与 rerun 边界不变 |
| build_css | 548 → 19 | 10 个原有样式章节，输出次序和空白不变 |

- 快照先于实现拆分生成，来源固定为 #73 合并代码：102 个案例覆盖三种密度、三种球形、两种一体件模式、两种裙子连接和两种裙摆模式的组合，以及留口、轮廓配色、独立密度、分派优先级、空输入错误与回退。保存完整序列化输出，不只保存摘要；后续拆分没有重生成夹具。
- 保存名称仍是原中文标签，英文 ID、英文标签和自定义旧名称没有被重新解释为规范部件。PartKind 收敛不等于完整国际化。
- 装配新旧比较 6,144 个组合均一致，含数量、留口、一体件、默认/空连接图和自定义名称。
- 评测比较 16 份完整合成报告；试钩比较 18 份完整合成报告、9 个模型 schema、26 个移动函数的 AST/签名、CLI 帮助和草稿 JSON，均一致。比较固定时钟，未使用真实照片或实体记录。
- 网格新 helper 展开后重建原完整函数 AST；87 项现有网格与状态安全测试通过。样式完整 16,410 字节及 19 个令牌/环数变体均一致。
- #74 仅改变依赖和两处等价的 NumPy 模块归约调用；203 个非空整数数组（含并列最大值）的归约结果一致，94 项相关测试及 OpenCV grabCut/Haar/cvtColor 冒烟通过。这个依赖更新与结构整理分开评审。

## 验证与局限

联合代码提交本地全量 **2987 passed、2 skipped，覆盖率 94.61%**；全部 30 个浏览器流程通过。该提交的四条远端流水线合计 **13/13** 成功，已单独验证组合结果，没有仅凭各 PR 通过推断集成通过。

具体数量、代码提交、运行环境和远端作业见[验证清单](fable-round2-checks.json)。本地联合验证使用 Python 3.12、锁定 dev+pdf、NumPy 2.5.2 与 OpenCV 4.14，包含全量 pytest、Ruff、mypy（含收据脚本）、wheel 构建及全部 30 个合成浏览器流程。

每个待审 PR 在清单所列头提交均有 13 项成功检查。#78、#80、#82 的浏览器首次运行分别在下载或恢复流程失败；读取日志后仅重跑失败作业，同一头提交成功。没有改测试、延长超时或删断言来取得通过。这说明存在浏览器流程的间歇失败，不能记成首次运行全绿；原失败尝试与重跑均可从工作流页面查看。本地联合浏览器流程一次通过。

可复核命令（输出快照测试不会写夹具）：

```bash
uv sync --locked --extra dev --extra pdf
uv run --locked --extra dev ruff check .
uv run --locked --extra dev mypy app tests scripts/bind_release_evidence.py
uv run --locked --extra dev pytest -q --cov=app --cov-report=term --cov-fail-under=80
uv build --wheel --out-dir dist/
python scripts/bind_release_evidence.py --status --commit <candidate-sha>
git diff --check
```

浏览器配置与完整命令见[浏览器回归说明](../browser-regression.md)。评测/试钩的拆分比较是一次性开发核对，不是新增真实数据证明；持久回归保护来自已提交快照及现有测试。旧审查轮次命名的测试没有另开批量改名项目。

## 仍未闭项

G3 仍按 11-12 确定的全自动评测口径，需要至少 30 个分层、逐图有版权/被摄者证据的真实照片案例并满足既定阈值；G4 仍需实体试钩的校准集与不重叠独立验证集。本批没有收集或虚构这些证据，也没有放宽门槛。#15 等待外部拆分；本批新实现等待独立复核及合并。正式发布继续阻断。
