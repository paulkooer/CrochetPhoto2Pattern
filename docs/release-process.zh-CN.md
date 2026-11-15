# 发布候选证据流程

[English](release-process.md) | [系统状态](system-status.zh-CN.md)

日常合并查看各自的 CI。`release-evidence.json` 是一个已选定候选的收据，仅在准备下一个
发布候选时重新生成。在此之前保留旧收据作为历史证据，不把它描述成当前 `main` 的验证结果。

选定候选之前，按[片段说明](../changelog.d/README.md)运行
`python scripts/changelog_fragments.py collect --date YYYY-MM-DD --write`，一起提交两份
日志和片段删除记录。新收据使用 schema 3，除 13 个必需检查外，还要求
`full-validation (CI)`、`full-validation (extras)`、`full-validation (browser)` 和
`full-validation (security)` 全部通过。纯文档 PR 的占位成功不含这些标记，不能作为
发布覆盖证据；主分支 push、手动和定时运行仍全量验证。旧 schema-2 收据继续按确切
历史绑定读取，本次迁移不改写旧证据。

1. 选定一个已提交的候选，记录完整 SHA，按 `.github/required-checks.json` 核查该提交
   最新的远端检查。
2. 找到成功的 pip-audit 提交。候选本身运行了审计时直接使用它；否则审计提交必须与候选
   的 Git 树完全一致。仅依赖版本相同或应用代码相似不够。如果没有同树审计，先取得审计
   再生成证据，不能借用旧收据填补。
3. 显式指定两个 SHA 生成收据：

   ```bash
   python scripts/bind_release_evidence.py --commit <candidate-sha> --audit-commit <audit-sha>
   ```

   生成器拒绝缺失、未完成或未成功的最新检查，也拒绝不同的审计树。核对结果中的
   `commit`、`tree`、`checks_completed_at` 和 `run_refs`。
   生成器同时写入 `release-evidence.sha256`，两个文件须一起提交。
4. 离线只读核对绑定：

   ```bash
   python scripts/bind_release_evidence.py --status --commit <candidate-sha>
   ```

   退出码 0 要求提交与树同时匹配、收据校验和正确、检查组通过、审计树匹配，且
   `covers_later_commits` 为 false；1 表示未满足这些条件。离线检查只验证本地一致性，
   不认证 GitHub 运行来源，也不重新查询远端检查状态。这里只比较已提交的身份，不验证工作区
   未提交内容。后续记录收据的提交与候选提交不同，核对和审阅时仍指定候选 SHA。
5. 按[真实照片评测](evaluation.md)与[实体试钩](physical-trials.md)规范分别核对 G3、G4。
   G1/G2 绑定匹配不等于这些门禁通过；G1–G4 全部通过前不创建正式发布标签。

[状态页](system-status.zh-CN.md)只链接证据文件与本流程，不复制候选/审计哈希、运行数量或
运行编号。下一次更新收据不应再要求手改状态页或测试里的历史常量。

## 工程 Beta 预发布

维护者明确授权的工程 Beta 可以在 G3/G4 完成前预发布。一起更新 PEP 440 Beta 版本与锁文件，
同步双语入口并汇总 changelog，通过正常受保护分支 PR 流程合并。选定的确切候选须取得全部
必需检查与完整验证标记后，才能生成其 G1/G2 收据。此例外只允许预发布，不能作为稳定版
发布，也不能声称 G3/G4 已通过。

Beta 标签指向该已检查候选，GitHub Release 标记为 `prerelease`，不设为最新稳定版。
说明中列出尚未达标的照片/实体证据，链接候选检查，并随发行包摘要附上匹配收据与校验和。
后续文档提交可以把该收据记录到 main，但不是打标签的候选。源码归档内可能仍含旧的历史
收据；独立附件中的新收据必须准确绑定标签所指 SHA。

发行包必须由选定的已提交源码构建并核对内容。私人原图、文件名、逐图清单/报告和本机恢复包
不得进入 Git 或任何发行附件。实体试钩启动包只使用手动生成图解和真实制作者身份；
草稿及软件检查均不构成实体试钩通过证据。
