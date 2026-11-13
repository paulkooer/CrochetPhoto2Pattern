# 材料边界与输出回滚 · 2026-11-02

审查起点为干净的 `d619179447df1694d88abf89ad828cb86740c0d9`。本轮发现：线团重量
`1e-320` 可通过模型校验，却在计算购线团数时溢出；布尔值会被当成数值。普通 CLI
替换失败后虽然恢复旧内容，但会改变原文件权限和修改时间；备份旧输出时还会把整个
文件读入内存。单图输出路径为循环符号链接时会抛出未处理的异常。

材料输入现在统一校验有限值和下界，导入、编辑、Markdown/PDF 使用相同规则；旧数据
兼容及工程修复方法见[工程格式](../project-format.md#实测试片克重与来源密度)。CLI
分块备份及回滚的元数据、并发和断电边界见[图片与批量说明](../image-memory.md)。
全量逐色用线只汇总一次，材料清单和小计共享同一计算结果。

## 合成性能对照

在本机 macOS、Python 3.12.13 和既有 `.venv` 下，对同一合成输入调用 `refresh_derived`；
计时不含输入深拷贝和输出序列化。每次独立进程预热两次，再取 11 次中位数。16,000 圈
交替运行两轮，150 圈运行一轮；比较对象为起点提交与本轮工作树。每次的完整派生输出
均计算排序 JSON 的 SHA-256。

| 输入 | 原版本中位数 | 本轮中位数 | 完整输出 SHA-256 |
| --- | --- | --- | --- |
| 3 部件、150 圈 | 0.333 ms | 0.257 ms | `05b29d683e03e76a3725c28e52668324d6e5fb247bec0b846bf6a78d3bf76e89` |
| 8 部件、16,000 圈 | 29.567 / 29.665 ms | 22.296 / 22.247 ms | `8ee170c06c85068a46331289a17bdfdeee6daae755901202f8c1a82f9ce3a6e5` |

16,000 圈案例约降低 25%，该输入达到当前总圈数上限，不能代表常规图解、完整生成管线或
其他机器的加速幅度；150 圈的亚毫秒测量也容易受系统调度影响。哈希一致只覆盖这两组
合成输入，并不证明物理用量准确。

复现时在仓库根目录执行：

```sh
task_review_dir=$(mktemp -d)
git archive d619179447df1694d88abf89ad828cb86740c0d9 app | tar -x -C "$task_review_dir"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/benchmark_material_refresh.py --source-root "$task_review_dir" --parts 8 --rounds-per-part 2000
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/benchmark_material_refresh.py --parts 8 --rounds-per-part 2000
```

脚本输出 Python 版本、两份源码文件的 SHA、计时和完整输出 SHA；不使用私人资料。

## 验证与边界

- 修改前全量 **2298 passed、2 skipped，84.98s**；修改后 **2320 passed、2 skipped，83.75s**。
- 全仓 Ruff、mypy app/tests（188 文件）、Schema 同步及差异检查通过。新增回归覆盖材料
  非法值及页面重试、旧导出缓存、分块复制和注入的备份/回滚失败。
- 两项跳过仍为授权真实照片目录和可选 MediaPipe 缺失。本轮未运行真实浏览器、远程 CI、
  独立验收或实体试钩，不能把软件测试或性能对照当成 G3/G4 通过证据；项目仍为 Beta。
