# 实施与实测记录

时间：2026-11-03，Apple Silicon Mac，16 GiB RAM，Docker Desktop 6 CPU / 8 GiB。

## 已完成的本地基线

- 5 个应用和 5 个依赖运行于 kind `retail-lab` 的 `retail` 命名空间。
- Jenkins 2.580.2 控制器、Registry 位于 Docker Desktop；原生 Mac Agent 通过 WebSocket 连接，单执行器，登录时通过 LaunchAgent 启动。
- 60 项真实测试通过：Carts 16、Orders 6、UI 11、Catalog 15（含子测试）、Checkout 12。每个服务均断言实际测试数量非零。
- Carts 初始化改为幂等创建，覆盖空表、重启保留数据、GSI 缺失拒绝破坏、并发初始化。
- 所有应用及依赖使用本地 Registry digest。应用 spec、Registry 和 Pod imageID 已交叉验证。
- 使用受限发布身份走完首页、商品、加购、配送、模拟支付、Orders 读回。首笔实测订单：`f999e6c6-0413-42a5-9850-b9b23dbb4183`。
- `pods/exec` create、Secret get、PVC delete 均返回 no；真实 port-forward 和点名 Deployment rollout 成功。
- 初始整体空闲快照：kind 约 2.54 GiB，Jenkins 332 MiB，Registry 65 MiB，既有 timescaledb 91 MiB，总计约 3.01 GiB。低于设计中的约 5 GiB 判断线，暂保留 Docker 8 GiB；构建峰值仍需实测。

## 对 v3 设计的具体落实

1. 本地构建先在 Agent 测试、编译，再将产物装入 `learning/docker` 镜像，减少 VM 内重复编译；保留上游 Dockerfile。
2. Secret 使用固定名称与显式 key 引用；非敏感 ConfigMap 使用 `<service>-config-<hash>`。避免 ConfigMap 与 Deployment 同名造成 Kustomize 错误改写 Role.resourceNames。密码变更由管理员协调重启和数据库更新，不视为普通发布。
3. `configMapGenerator` 直接生成配置。已发现并处理 replace 上游静态 ConfigMap 没有生成哈希的实际行为。
4. 镜像依赖也缓存到 Registry，避免节点继承 127.0.0.1 代理或公共 ECR 限流阻塞恢复。`node-config.sh` 重建后配置 containerd hosts.toml、Registry NO_PROXY、kubeReserved 与 evictionHard。
5. Java Testcontainers 使用 daemon API 1.43；Node 固定 22.23.4，Yarn 固定 4.11.0；Maven Central 显式配置避免 Spring milestone 网络挂起。
6. Jenkins 支持 ACTION=deploy/reconcile，先恢复 pending/漂移再发布；基础权限/配置错误直接停下，业务恢复失败允许完整测试后的修复候选继续，并在发布记录中标记 recoveryFailed。
7. 构建插件版本记录于 `jenkins/plugins.txt`，运行镜像基础摘要已固定。生产多架构构建、数据库迁移回滚、AWS 部署仍不属于本期。

## 尚需完成或单独安排的验证

请以 CHECKLIST.md 的勾选和 Jenkins 实际结果为准。Docker Desktop 与整机重启会影响其他项目，不在无人值守流程中执行；保留为明确的人工验收项。
