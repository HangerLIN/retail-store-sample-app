# 实施与实测记录

时间：2026-11-03，Apple Silicon Mac，16 GiB RAM，Docker Desktop 6 CPU / 8 GiB。

## 已完成的本地基线

- 5 个应用和 5 个依赖运行于 kind `retail-lab` 的 `retail` 命名空间。
- Jenkins 2.580.2 控制器、Registry 位于 Docker Desktop；原生 Mac Agent 通过 WebSocket 连接，单执行器，登录时通过 LaunchAgent 启动。
- 60 项真实测试通过：Carts 16、Orders 6、UI 11、Catalog 15（含子测试）、Checkout 12。每个服务均断言实际测试数量非零。
- Carts 初始化改为幂等创建，覆盖空表、重启保留数据、GSI 缺失拒绝破坏、并发初始化。
- 所有应用、依赖和构建基础镜像使用本地 Registry digest。应用 spec、Registry 和 Pod imageID 已交叉验证。
- 使用受限发布身份走完首页、商品、加购、配送、模拟支付、Orders 读回。首笔实测订单：`f999e6c6-0413-42a5-9850-b9b23dbb4183`。
- `pods/exec` create、Secret get、PVC delete 均返回 no；真实 port-forward 和点名 Deployment rollout 成功。
- 初始整体空闲快照：kind 约 2.54 GiB，Jenkins 332 MiB，Registry 65 MiB，既有 timescaledb 91 MiB，总计约 3.01 GiB。低于设计中的约 5 GiB 判断线，暂保留 Docker 8 GiB；完整构建已观测峰值约 3.55 GiB，Docker OOM 事件为 0；控制器 StartedAt / RestartCount 在构建和 Agent 中断前后保持一致。

- 连续加购期间重建 DynamoDB：32 次已确认写入全部保留，观测最多 1 个 DynamoDB Pod，无 database is locked。重建期间有 1 次临时请求错误，该请求可能已落库，因此读回 33 条；不把重启描述为零中断或恰好一次处理。
- MySQL 插入独立验证标记，Pod 重建后标记仍在；测试专用表已清理。Carts / PostgreSQL / RabbitMQ 重启后的完整下单也通过。

## 对 v3 设计的具体落实

1. 本地构建先在 Agent 测试、编译，再将产物装入 `learning/docker` 镜像，减少 VM 内重复编译；保留上游 Dockerfile。
2. Secret 使用固定名称与显式 key 引用；非敏感 ConfigMap 使用 `<service>-config-<hash>`。避免 ConfigMap 与 Deployment 同名造成 Kustomize 错误改写 Role.resourceNames。密码变更由管理员协调重启和数据库更新，不视为普通发布。
3. `configMapGenerator` 直接生成配置。已发现并处理 replace 上游静态 ConfigMap 没有生成哈希的实际行为。
4. 镜像依赖也缓存到 Registry，避免节点继承 127.0.0.1 代理或公共 ECR 限流阻塞恢复。`node-config.sh` 重建后配置 containerd hosts.toml、Registry NO_PROXY、kubeReserved 与 evictionHard。
5. Java Testcontainers 使用 daemon API 1.43；Node 固定 22.23.4，Yarn 固定 4.11.0；Maven Central 显式配置避免 Spring milestone 网络挂起。
6. Jenkins 支持 ACTION=deploy/reconcile，先恢复 pending/漂移再发布；基础权限/配置错误直接停下，业务恢复失败允许完整测试后的修复候选继续，并在发布记录中标记 recoveryFailed。
7. 构建插件版本记录于 `jenkins/plugins.txt`，运行镜像基础摘要已固定。生产多架构构建、数据库迁移回滚、AWS 部署仍不属于本期。

## 尚需完成或单独安排的验证

请以 CHECKLIST.md 的勾选和 Jenkins 实际结果为准。Docker Desktop 重启已在用户确认后验收通过，详见下节。Mac 整机重启尚未执行，保留为人工安排的验收项。

## 发布中断演练

Jenkins 构建 #3 在五个服务测试和镜像推送完成后，Orders 已更新、其他四个应用尚未更新时，停止 Agent 并终止发布子进程，构建以 137 失败。集群同时保存原 lastGood 与 pending，实测仅 Orders 镜像发生变化。恢复 Agent 后手动执行 #4（ACTION=reconcile）成功，五个镜像恢复到 lastGood，完整下单通过，pending 清空。

每次作业开始清理本次报告目录，恢复/文档跳过作业不复用旧测试报告；Java clean package 与每服务测试数量断言进一步防止陈旧产物误报。

## 自动发布与停止/启动

- Jenkins #5 由 `Started by an SCM change` 自动触发，提交 `2c9886e3b48a41c7c8f5d07d6c34aa6c54427e9d`，结果 SUCCESS。60 项测试通过，按 digest 发布、订单持久化读回、lastGood 记录全部完成。
- #5 的五个镜像、运行 imageID、提交 SHA 和虚构订单证据见该构建的归档。Docker OOM 事件为 0，构建期间控制器未重启。
- 实验容器 stop/start 后三个容器 ID 不变；原订单 `eb65df38-c4c0-411f-a184-f514b95eef9e` 和 33 条购物车数据保留，新订单 `4d7503b6-cd3c-464c-9f9d-4a9d2d37794e` 创建成功，Agent 自动连接。
- 全部依赖同时启动时有约一分钟恢复窗口，Orders 在依赖尚未可用时额外重启一次后自愈；这是本地单节点环境，未承诺零停机。
- kind 节点、Jenkins、Registry 均配置 unless-stopped。Docker Desktop 重启已完成单独验收；Mac 整机重启仍未执行，不将普通容器或 Docker 虚拟机重启冒充整机验收。

#5 构建的 Docker 总占用采样峰值约 3.65 GiB，保留 8 GiB 配额。采样间隔约 5 秒，短于采样间隔的瞬时峰值可能未捕获；同时使用 OOM 事件与重启状态佐证。

纯文档提交 `2b18d79f3f7b727650e7057c0a6a83f40b47ea4a` 自动触发 Jenkins #6，结果 SUCCESS；Test and build / Deploy, verify and record 均明确跳过，未复用旧测试报告。lastGood.sourceSha 仍指向已发布的 `2c9886e3b48a41c7c8f5d07d6c34aa6c54427e9d`。

## Docker Desktop 重启验收（2026-11-03）

经用户确认影响范围后，从 Docker Desktop 的 Troubleshoot → Restart 执行重启，没有删除或重建容器，也没有手工启动实验容器。重启前暂停 Jenkins 接收新作业；验收后恢复。

- Docker VM 的 boot ID 已变化，Mac 启动时间未变化，确认覆盖了 Docker Desktop 重启。
- kind、Registry、Jenkins 及既有 TimescaleDB 的容器 ID 均未变，启动时间均更新；均自动启动，TimescaleDB 恢复 healthy。
- Jenkins 的原生 Mac Agent 自动重连；10 个 Pod 全部就绪。
- Carts、Orders 在依赖尚未就绪时各额外重试一次，约一分钟后恢复。这是启动顺序导致的短暂不可用，不是零停机。
- 重启前订单 `100b57ab-a0c5-4c0f-b052-0392a36d38e9` 仍可读取，购物车全部 33 条记录逐项比对一致；重启后新增订单 `b6d43eb3-c6be-4bb8-b238-f1fd674e39aa` 成功。
- 本机详细前后快照及验证日志保存在忽略的 `env/reports/desktop-restart/`；快照不包含 Secret 值。

## 架构评审补充（2026-11-03）

本节区分真实集群验收和脚本回归测试。#12 已完成 Verify 异常自动回滚，#14 已完成 recoveryFailed 后修复候选发布；不以 #3/#4 中断演练代替它们。Jenkins 中真实测试失败、Redis 单独重启、控制器删除重建复用卷、SCM 页面可见改动仍未单独验收。

### 构建编号与证据保留

| 构建 | 实际含义 | 触发方式 |
| --- | --- | --- |
| #1 | 初始化时缺 Jenkinsfile，失败 | SCM |
| #2 | 构建网络问题，失败；不是测试失败注入 | 手动 |
| #3 | Orders 更新后强制终止发布，失败；留下 pending | 手动 |
| #4 | ACTION=reconcile 恢复成功 | 手动 |
| #5 | 60 项应用测试、五镜像发布、真实下单成功 | SCM，API 原因为 Started by an SCM change |
| #6–#9 | 纯文档提交检查后跳过，历史结果 SUCCESS | SCM |

已对 #3、#4、#5、#6 调用 Keep forever，并读回确认 kept=true。普通构建仍保留 10 次。另保存 [build-5.json](evidence/build-5.json)，含 release、image evidence、smoke 与测试数量，避免仅依赖轮转中的链接。该文件只含本地示例业务证据，不含凭据。

#5：源码 `2c9886e3b48a41c7c8f5d07d6c34aa6c54427e9d`；Carts 16、Orders 6、UI 11、Checkout 12、Catalog 15（含子测试），共 60 项；Java 33 通过、0 失败、0 跳过，Jest 12 通过，Go 15 通过，Docker OOM 事件 0。五个完整镜像摘要如下：

| 服务 | Registry 镜像引用 |
| --- | --- |
| orders | `localhost:5001/retail/orders@sha256:3b20a8cfd6ac4c99c852ef98e51525854423cdf51cfa41d60ed1b840bc3029b0` |
| checkout | `localhost:5001/retail/checkout@sha256:6718398f6f59ca006496fdee65ae5ea5e94d5a5f9278fe8d7ddef151171ee782` |
| carts | `localhost:5001/retail/carts@sha256:56c14a0e5c55ce7c4d582c1c7908363516175e4efc41c7834d612ba8d5f9daf8` |
| catalog | `localhost:5001/retail/catalog@sha256:6b634ffa77a3219c0da73106895d95a463642b093a53d9de13d1c92e7c51b2db` |
| ui | `localhost:5001/retail/ui@sha256:679eebffb5f962187a95ff32ee56e7ff2a13cee89f50151b4e3e1cb42c59c23d` |

### 本轮验证

- 新增 22 项脚本测试，含 needed 的 recoveryFailed/docs 组合、pending/镜像漂移组合、失败回滚、回滚失败、Record 前后中断、CAS 冲突、配置接纳拒绝和 HTTP 连接中断。测试使用假外部命令，不冒充真实故障注入。
- 实际运行 ci.sh 的隔离编排测试逐一让五个服务测试失败，确认均无 image.sh 调用；成功时五个 test 调用全在第一个 push 前。
- 严格订单匹配已用受限发布身份真实下单通过：`d1d14cd2-0c42-4373-b455-fbdbecddd0ab`。
- adopt-config 演练：临时向 UI ConfigMap 加入无业务影响键，未应用时因新 ConfigMap 不存在被拒绝；应用并 rollout 后因基线指纹不同被拒绝；管理员接纳时下单 `7e0f9fbb-4c9b-4d04-b41b-8876d5cdf13f` 成功。恢复原配置并再次接纳，下单 `b7caca6e-e94f-4eb5-92e1-59132ffc9453` 成功；images/sourceSha/verifiedAt 始终不变，最终 state 内容与演练前一致。日志在本机 env/reports/config-adoption/。
- 演练辅助断言首次只匹配“配置漂移”文本，遗漏了“新哈希 ConfigMap 不存在”的预期拒绝，因此第一次辅助脚本失败；finally 已恢复配置，补齐辅助断言后完整演练通过。未将该次辅助失败算作应用故障。
- 当前 #5 Checkout 生产镜像 `/app/node_modules` 中 `.node` 数量为 0；开发依赖中存在 darwin 原生模块，不能用开发目录的扫描结果代表生产包。新增检查限定生产打包目录。
- Catalog 实际工具链 `go1.25.0 darwin/arm64`。本轮增加工具链报告、Mac memory_pressure/swap、Pod 前后状态采样；历史 #5 不因此获得原本没有采集的 Mac 内存证据。
- 配置演练后 MySQL Pod RESTARTS=2，最近终止原因 Unknown；十个 Pod 均 Ready，当前可见的最近终止记录无 OOMKilled。这些重启包含此前 Docker 重启，不应重写为“从未重启”或“历史从未 OOM”。
- 购物车 32/33 的差异保留不确定性：32 个请求已收到成功，另一个返回临时错误的请求可能已经落库；没有足够证据认定为重试落地，也不能称其为预置数据。

### 本轮 Jenkins #10 自动发布

源码 `89540a95a737a9ac9da27398ee24388514c132c7`，SCM 自动触发，SUCCESS，description=`deployed 89540a95a737`。60 项应用测试和 21 项脚本测试通过，严格订单匹配、镜像核对、lastGood 记录成功，订单 `00a1d3a6-b93c-4fc7-972f-5b8d2d0e76ac`。#10 已 Keep forever。

Docker 用量采样峰值 3.286 GiB，OOM 事件 0；构建阶段 pods-before/pods-after 对应原有 Pod 的重启计数一致。Mac memory_pressure free percentage 45–58%，swap used 在各次采样均为 1731.06 MiB；这是既有 swap，不能由此推断是本次构建产生。报告仍可能漏掉采样间隙的瞬时峰值。工具版本、内存与 Pod 快照均已归档。

### 真实失败恢复演练 #12–#14

- #12（SCM）提交 `1bfc897` 将 UI 成功页 `Order ID` 临时改为 `Order reference`。五个候选镜像完成推送和 rollout，Pod readiness 正常，但完整结账在成功页提取订单 ID 时失败。构建为 FAILURE，发布脚本自动恢复 #10 的五个 digest；随后实测五个 Deployment 与原 lastGood 全部一致、pending 不存在、lastGood.sourceSha/verifiedAt 不变、真实下单成功。候选 UI `sha256:4a1f3a4932fa8d046af17ebbe10a815abdf39154fd4ba6a45e203565eca5de8c` 仍由 Registry HEAD 返回，未被清理。
- #13（SCM）在模拟镜像漂移且 UI 副本为 0 时，恢复 lastGood 后的首页请求抛出 `http.client.RemoteDisconnected`。旧代码只将 URLError 和 AssertionError 归为业务不健康，导致 FAILURE 而没有 top-level recoveryFailed。这是演练发现的实际缺陷，不计为恢复路径已验证。
- 提交 `5e79c55` 将 HTTPException、OSError 和 TimeoutError 归入 UnhealthyRelease，并增加针对 RemoteDisconnected 的回归测试。
- #14（SCM）重复同类恢复失败后，prepare 写入 top-level recoveryFailed=true，needed 强制进入完整构建。在候选发布前将 UI 副本恢复为 1；候选成功发布并完成真实下单 `c1a44542-b88b-4f40-8aba-b8f3823a0e14` 和五镜像核对。最终 lastGood 为 `5e79c55547d13186de177affaab03b310681b464`，lastGood.recoveryFailed=true 记录历史，顶层 recoveryFailed 和 pending 均不存在。#12、#13、#14 均已 Keep forever。

完整的可审计字段见 [failure-recovery-12-14.json](evidence/failure-recovery-12-14.json)。这覆盖 Verify 失败和连接中断恢复两种路径；不代表 rollout 超时、镜像拉取失败、数据库迁移失败已被演练。

当前五镜像（历史 #5 摘要保留在前表）：

| 服务 | #10 Registry 镜像引用 |
| --- | --- |
| orders | `localhost:5001/retail/orders@sha256:e959352586845bd14b9ac01f2af6a82b331ebda2120e38940571c98a04f0dfc4` |
| checkout | `localhost:5001/retail/checkout@sha256:6718398f6f59ca006496fdee65ae5ea5e94d5a5f9278fe8d7ddef151171ee782` |
| carts | `localhost:5001/retail/carts@sha256:65b0cf9c78886af23953d33a065a707bd6c9c89bc8fc2e5f38779838aa9624af` |
| catalog | `localhost:5001/retail/catalog@sha256:6b634ffa77a3219c0da73106895d95a463642b093a53d9de13d1c92e7c51b2db` |
| ui | `localhost:5001/retail/ui@sha256:6d217ce4c5701ba034555aa5e4297ac49855ca9653bfca09576f39e86fa6d29d` |
