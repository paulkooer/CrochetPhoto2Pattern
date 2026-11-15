# 发布候选证据流程

[English](release-process.md) | [系统状态](system-status.zh-CN.md)

日常合并查看各自的 CI。`release-evidence.json` 是一个已选定候选的收据，仅在准备下一个
发布候选时重新生成。在此之前保留旧收据作为历史证据，不把它描述成当前 `main` 的验证结果。

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
