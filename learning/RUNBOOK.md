# 本地网店与 Jenkins 操作手册

本机使用 Apple Silicon、16 GiB 内存，Docker Desktop 6 核 / 8 GiB。所有学习资源位于 `retail-lab` 集群、`retail` 命名空间或 `retail-*` Docker 容器。现有 timescaledb 属于另一项目，生命周期脚本不会操作它。

## 入口与凭据

- 网店：http://127.0.0.1:8888
- Jenkins：http://127.0.0.1:8080，作业 `retail-local`，账户 `learner`。
- Jenkins 密码：仓库 `env/jenkins-secrets/admin-password`，仅本地保存。
- 发布配置：`env/release.kubeconfig`，显式指定后才运行流水线。
- 管理员操作：显式使用 `--context kind-retail-lab` 与原管理员 kubeconfig。
- 不把 `env/`、`learning/k8s/.secrets/`、完整渲染后的 Secret 清单提交到 Git。

这些端口只监听本机。原生 Agent 与用户同一个 macOS 身份且能访问 Docker，因此发布 RBAC 用于防误操作，不提供对恶意仓库代码的强隔离。仅信任自己的 main 分支。

## 日常发布

在 fork 的 main 提交并推送源码；Jenkins 每两分钟轮询。流程为配置检查、恢复中断状态、按 lastGood.sourceSha 判断是否有构建变更、五个服务串行测试和构建、按 digest 依次部署、真实下单和订单读回、写入 lastGood。

构建顺序与部署顺序都是 Orders → Checkout → Carts → Catalog → UI。文档及架构图改动可以跳过，但会先检查配置与恢复状态；流水线、脚本和清单改动不会按文档跳过。基础设施配置需要管理员应用并重建验证基线，发布身份不能应用整个目录。

Jenkins 显示 aborted、Agent 掉线或机器休眠后：恢复 Docker 和 Agent，手工 Build with Parameters → `ACTION=reconcile`。没有新提交时轮询不会自动替你恢复。`release-state` 保留 pending，恢复依据是 lastGood，不是混合状态的镜像快照。

控制台之外还应查看构建归档：测试结果、`smoke.json` 的订单标识、`release.json`、`image-evidence.json`、内存采样、Docker OOM 事件。出现测试数量为零、配置漂移、镜像摘要不存在、真实下单失败均不能标记成功。

## 本机工具与构建取舍

`learning/scripts/environment.sh` 显式选择 JDK 21、仓库 env 下的 Node 22.23.4、Go 自动工具链、新版 kubectl、Docker context socket；路径可按另一台 Mac 调整。Yarn 直接运行仓库内固定的 4.11.0 脚本，不依赖 Node 是否附带 Corepack。测试包含 Carts DynamoDB、Orders PostgreSQL、Catalog MySQL、Checkout Redis 的 Testcontainers。

Docker Desktop 24.0.6 的 API 上限是 1.43；Java 测试通过 `-Dapi.version` 使用 daemon 报告的兼容版本。测试使用虚构的本地 AWS 凭据，绝不依赖个人 AWS 账户。后台 Agent 不继承交互终端代理；需要时将代理配置保存在忽略的 `env/network.sh`（权限 600），环境脚本会显式加载。

本地学习镜像使用 `learning/docker/`：先在原生 Agent 测试和编译，再打包产物；Go 交叉编译 Linux ARM64，Java jar 跨平台。Checkout 只携带生产依赖。上游 Dockerfile 保留，未来迁移 AWS 的多架构镜像构建另行学习。这样减少 Docker VM 内重复 Maven 编译的峰值，但原生构建仍占 Mac 内存。

Maven 学习配置只使用 Maven Central，避免上游 Spring milestone 仓库在当前网络挂起。版本由服务 pom 和锁文件确定。

## 初始化顺序

已建立的本地环境不需要重复初始化。重建时：

1. 准备 Docker Desktop、JDK 21、Node 22、Go、kind v0.33.0、kubectl v1.37.0、Python/PyYAML 6.0.3；工具与虚拟环境放入忽略的 `env/`。
2. 创建带持久卷、仅监听 127.0.0.1:5001 的 `retail-registry`；创建 `learning/kind.yaml` 定义的集群。
3. 运行 `learning/scripts/node-config.sh` 配置 containerd Registry 与 NO_PROXY、kubelet 内存预留。kind 重建后必须重跑；另外执行 `docker update --restart unless-stopped retail-lab-control-plane`，使运行中的节点随 Docker 恢复。节点继承宿主机 127.0.0.1 代理时，公共拉取会失败；本方案依赖镜像也缓存在本地 Registry。
4. 管理员执行 `dependencies.py` 准备五个依赖、`base-images.py` 缓存固定摘要的构建基础镜像；审阅生成的本地 digest。
5. 各服务运行 `test-build.sh <service>` 和 `image.sh <service> <tag>`，产生 `reports/<service>-image.json`。生产依赖与测试报告必须完整，不能拿上游购物车镜像替代修复版。
6. 管理员使用 `bootstrap.py`：初始化本地随机密码，部署清单，生成受限发布配置。再次执行会保留 release-state，但会滚动基础设施配置；先审阅变更。
7. 使用发布环境运行 `release.py bootstrap` 完成真实冒烟并记录首个基线。源码有未提交改动时 sourceSha 为空，后续 Jenkins 必须重新构建，不把未经追溯的 SHA 当成功版本。
8. 构建 `learning/jenkins/Dockerfile`，挂载 Jenkins 持久卷与本地凭据目录启动控制器；`agent.sh` 用 WebSocket 连接。控制器执行器为零，Agent 单执行器。

## 停止、启动与重置

`bash learning/scripts/lifecycle.sh stop` 会检查没有正在执行的作业，使 Jenkins 停接新作业，再停止这三个实验容器；不删除容器、卷、命名空间或 PVC。

`bash learning/scripts/lifecycle.sh start` 启动原来的容器。Agent 通过本机 LaunchAgent 或手动运行 `agent.sh` 连接。启动后检查 Node、Pod 和网店下单；端口开放不代表业务可用。

`reset` 会明确提示并要求输入确认字符串，再删除 kind 集群。**Retain 也救不了被删除的 kind 节点文件系统。** 需要的数据先导出；没有导出就不要 reset。Retain 只保护 PVC 删除后的卷回收，重新绑定 Released PV 是管理员任务。

自动验证期间用 `caffeinate -i` 防止空闲休眠，不要合盖。Mac 或 Docker Desktop 重启会影响其他项目，需安排时间进行验收；普通 stop/start 不能冒充整机重启验收。

## 数据与资源边界

MySQL、PostgreSQL、DynamoDB Local 使用 Retain PVC。DynamoDB 为单副本 StatefulSet，使用 sharedDb/dbPath，正常删 Pod 必须等待结束，不能 force delete。`createTable=true` 已改变为缺表才建、存在时检查主键与 GSI，不再删除表。

Redis 会话允许丢失。RabbitMQ 示例队列不是持久队列，本阶段只验证重连和继续下单，不承诺消息恢复。冒烟订单是虚构数据，会逐次积累；不依赖 Cart 上游的数量/删除边界行为。

kubeReserved 2 GiB 和 evictionHard 500 MiB 只影响节点调度/驱逐，不是 Jenkins 的内存隔离。Jenkins 容器上限 1 GiB、堆 512 MiB，Registry 上限 192 MiB。测量全网店空闲与真实构建峰值后再决定是否提高 Docker 配额，不因为 requests 能相加就认定安全。
