# 实体进度身份与旧工程恢复 · 2026-11-02

基于工作树上一轮材料和输出修复，继续审查工程恢复。结构中第一份头部的实例 ID 为
`copy2`、图解数量为 2 时，旧实现也为第二份生成 `copy2`：只勾选第二份第 1 圈并保存，
恢复后两份均显示已完成。另一风险是结构 ID 改名后，旧 ID 被额外副本重新使用，导致
完成状态转移到另一份实物。

当前实现先为结构实体保留 ID，再为额外副本分配不冲突的编号；编辑时区分结构实体 ID
与额外副本的序号。旧工程如果保存了有歧义的完成圈次，系统不会猜测；用户可以明确选择
只恢复其他进度和备注，随后对照实物重新勾选。旧撤销快照也按此保守处理。
格式兼容与操作说明见[工程格式](../project-format.md#名称相似的部件与进度隔离)。

合成旧工程及其[来源记录](../../tests/fixtures/progress_instance_collision/provenance.json)
在修复前生成：源文件 SHA 与 `d619179447df1694d88abf89ad828cb86740c0d9` 对应，
实际选择了第二份头部第 1 圈与帽子第 1 圈。文件只记录了重复身份，不能从中推断头部
选择；测试在确认恢复后保留帽子和备注，不替两份头部任意一份补勾选。
导入提示见[合成浏览器截图](../images/progress-collision-recovery-synthetic.png)。

另在独立解释器复核时发现，先导入 `app.schemas` 或 `app.utils.project` 会因包初始化
顺序产生循环导入。密度边界现由独立的共享常量模块提供，保留既有模型包导出；新进程
导入回归和离线构建的 wheel 均检查了这两个入口。

## 大工程进度预览

保留进度按已完成的圈次和实体身份映射，避免为每份未完成实物逐圈计算身份；预览的
保留/清除数量使用同一次映射结果。本机 macOS、Python 3.12.13，对直接构造的合成
输入运行 `progress_impact`：8 个部件、每个 2,000 圈、每件 20 份，共 320,000 个
实体圈次。每次独立进程预热 1 次，取 3 次中位数，交替执行两轮；计时不含构造输入。

| 已完成圈次 | 起点提交 | 当前工作树 | 预览报告 SHA-256 |
| --- | --- | --- | --- |
| 1 | 521.240 / 512.635 ms | 15.596 / 17.949 ms | `a82fbc2976d3d043f7885780618fd9f2618480c2565b34a6b3e4a93db78f1ac4` |
| 全部 320,000 | 1191.918 / 1204.721 ms | 1080.433 / 1086.437 ms | `c989f41bb264953064ba23aed88e40bcdb16fb5ed8d8f901b144abfef0ebcb68` |

这只比较进度预览报告，不包含文件导入、完整页面、图解生成或照片处理；高数量案例
接近当前圈数和数量上限，不能代表常见图解或其他机器。复现：

```sh
task_progress_dir=$(mktemp -d)
git archive d619179447df1694d88abf89ad828cb86740c0d9 app | tar -x -C "$task_progress_dir"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/benchmark_progress_impact.py --source-root "$task_progress_dir" --parts 8 --rounds-per-part 2000 --copies 20
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/benchmark_progress_impact.py --parts 8 --rounds-per-part 2000 --copies 20
```

两条命令均可加 `--completed all`；脚本输出源码 SHA、Python 版本、计时与报告 SHA，
不使用私人资料。完整测试及浏览器验证状态以[系统状态](../system-status.zh-CN.md)为准。

## 验证范围

- 全量 **2346 passed、2 skipped，97.09s**；全仓 Ruff、mypy（191 文件）、Schema 和
  差异检查通过。跳过项为授权照片目录与可选 MediaPipe 缺失。
- 合成旧文件、身份属性测试、分页、撤销重做及失败后确认恢复均有回归。实际旧源码
  读取对照中，无冲突工程可读取，带新版身份标记的冲突工程被旧版明确拒绝。
- 本地 Chrome 156.0.8078.74 的 **14 条合成流程通过**，包括冲突恢复、下载并在新
  上下文重新打开；离线 wheel 包含共享密度约束，新进程导入通过。验证时工作树有未提交改动。
- 未运行远端 CI、独立复核或实体试钩；不据此改变 Beta 定位或 G3/G4 门禁。
