# Actions 依赖更新复核（2026-11-13）

将陈旧 PR #1、#3、#37 的升级提议统一应用到当前工作流；替代 PR 的通过与合并状态以 GitHub 为准。关闭旧 PR 表示由替代实现接管，不表示升级已经进入 main。

| 依赖 | 更新 | 上游兼容性核查 |
| --- | --- | --- |
| docker/setup-buildx-action | v3 → v4 | [v4.0.0 发布说明](https://github.com/docker/setup-buildx-action/releases/tag/v4.0.0)：Node 24，runner ≥ 2.327.1，移除已弃用输入/输出；本仓库没有传入相关参数。 |
| docker/build-push-action | v6 → v7 | [v7.0.0 发布说明](https://github.com/docker/build-push-action/releases/tag/v7.0.0)：Node 24，移除旧摘要环境变量；本仓库没有使用这些变量。保留当前路径 context、push=false、load=true、GHA 缓存及容器冒烟。 |
| actions/upload-artifact | v5 → v7 | [v7.0.0 发布说明](https://github.com/actions/upload-artifact/releases/tag/v7.0.0)及 [action.yml](https://github.com/actions/upload-artifact/blob/v7/action.yml)：默认仍为 archive=true；单文件不打包上传是显式选项。本仓库保留多路径压缩上传、名称及 7 天保留期。 |

三个工作流均使用 GitHub 托管的 ubuntu-latest，没有自托管 runner。权限、触发条件和应用依赖不变。验证依据包括仓库卫生测试、真实 Docker 构建与容器冒烟、浏览器工作流实际上传产物；本地测试不能代替后两项远端结果。
