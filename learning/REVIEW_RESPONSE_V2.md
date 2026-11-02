# Claude CR 回应与源码证据

日期：2026-11-03。对应设计修订版 v2。此次只修改文档和图，未修改源码、部署清单或运行中的集群。所有运行验收仍待实施；“已核实”仅表示从当前基线代码确认的行为或配置。

离线包基线：`d7a380b843e0759e58754f74188ea18252a51415`，上游 1.6.3。包内有完整基线源码、构建文件、测试和当前 `learning/`。先阅读 DESIGN.md，再对照下列文件，不必推测缺失源码。

## 优先问题的处理

| CR 条目 | 处理 | 已核实依据与设计变化 |
| --- | --- | --- |
| 1 冒烟权限冲突 | 采纳 | Orders 的 `/orders` GET 可查询订单；设计允许发布身份在 retail 创建 pods/portforward，查询接口而非数据库。仍禁止 exec/Secret 读取。port-forward 是 namespace 级较宽能力，不假称只可转发 Orders。 |
| 2 所有 provider | 采纳并补证据 | 基线明确指定 mysql/dynamodb/postgres/rabbitmq/redis 和 UI 四个 endpoint；设计列出完整预期表，验证有效 env 的覆盖顺序，并用跨 Pod 重建的业务数据验证持久性。 |
| 3 DynamoDB 双写与参数 | 采纳，并发现额外阻塞 | 当前是 Deployment，无显式 strategy、args、PVC。目标 Recreate、dbPath/sharedDb、文件权限与 PVC。更严重的是 Carts init 主动 deleteTable，当前 CREATE_TABLE=true；必须先修源码，不然磁盘参数再正确也会清空数据。 |
| 4 回滚基线和死锁 | 采纳并明确恢复分支 | 预建 release-state，保存 lastGood/pending；Verify 成功才更新 lastGood。中断靠 pending 恢复；业务健康不是修复发布硬门槛；恢复失败可用显式 RECOVERY 模式继续修复，不把坏的现场快照当回滚点。初始网店验证后建立首个基线。 |
| 5 digest | 采纳 | 从 Registry/push 读取摘要，记录 index 与平台子 manifest 对应关系；hosts.toml 进入重建脚本。禁用 provenance 可简化，但不是摘要恒等的保证。 |
| 6 VM 内存 | 采纳问题，修正机制描述 | 全局 docker stats、构建和 Testcontainers 峰值、其他项目容器均入预算。预留约 2 GiB 仅是初值；kubeReserved 不会替 Jenkins 建立隔离内存池，也不能替代外层资源控制。 |
| 7 Agent 测试环境 | 采纳并扩大核实范围 | Carts/Orders/Checkout 都存在 Testcontainers 测试；显式工具与 Docker 环境，真实 Agent 预检，五服务实际执行测试数均须大于零。Checkout 默认 test 也是 exit 0。 |
| 8 删除和重启边界 | 采纳 | 区分 stop/start/reset，删除前确认与导出提示；restart unless-stopped 用于控制器/Registry。Mac 和 Docker 重启测试需用户配合，恢复流程与无人值守自启动分开验收。 |
| 9 RabbitMQ | 采纳缩减承诺，修正“没有队列”的可能推测 | 已有 queue/exchange/binding，queue 为非持久化；主源码未发现业务消费者。第一版只承诺重连及继续下单，移除 RabbitMQ PVC 和消息恢复承诺。 |

## 源码导航

以下链接均可在解压包内按相对路径找到。

- [当前 kind 配置](kind.yaml)：已经监听 `127.0.0.1`，此项无需修改配置。
- [当前 overlay](k8s/kustomization.yaml)：目前只做 namespace 与 UI NodePort，设计中的其他 overlay 尚不存在。
- [完整基线清单](k8s/base/retail.yaml)：五应用 provider/endpoint、envFrom、readinessProbe、数据库 emptyDir 和 DynamoDB Deployment。
- [Carts 初始化](../src/cart/src/main/java/com/amazon/sample/carts/services/DynamoDBCartService.java)：`init()` 在 createTable=true 分支执行 deleteTable→createTable。待修成幂等建表；仅将开关设 false 会让全新数据库缺表，不是完整修复。
- [Carts 默认配置](../src/cart/src/main/resources/application.yml)：默认 in-memory。
- [Catalog 默认配置](../src/catalog/config/config.go)：默认 in-memory。
- [Orders 默认配置](../src/orders/src/main/resources/application.yml)：持久化和消息 provider 默认 in-memory。
- [Checkout 配置](../src/checkout/src/config/configuration.ts)及[后端选择](../src/checkout/src/checkout/checkout.module.ts)：根据 orders endpoint 选择真实或 mock Orders 服务。
- [Orders HTTP 接口](../src/orders/src/main/java/com/amazon/sample/orders/web/OrderController.java)：POST/GET `/orders`，冒烟可按本次订单标识检索读回结果。
- [RabbitMQ 配置](../src/orders/src/main/java/com/amazon/sample/orders/config/messaging/RabbitMQMessagingConfig.java)：`new Queue(ORDERS_ORDERS_QUEUE, false)`，声明 exchange/binding。
- [RabbitMQ 发布实现](../src/orders/src/main/java/com/amazon/sample/orders/messaging/rabbitmq/RabbitMQMessagingProvider.java)：发布到 orders exchange；本身不证明消费或可靠投递。
- [Catalog 项目目标](../src/catalog/project.json)及[测试初始化](../src/catalog/test/main_test.go)：test/lint 占位；MySQL Testcontainers 与 localhost 地址构造。
- [Carts 集成测试](../src/cart/src/test/java/com/amazon/sample/carts/services/DynamoDBCartServiceIntegrationTest.java)：DynamoDB Testcontainers。
- [Orders 集成测试](../src/orders/src/test/java/com/amazon/sample/orders/services/OrderServicePostgresTests.java)：PostgreSQL Testcontainers，integration tag。
- [Checkout 脚本](../src/checkout/package.json)及[集成测试](../src/checkout/test/app.e2e-spec.ts)：test=exit 0；真实集成测试使用 Redis Testcontainers。
- [UI 测试目标](../src/ui/project.json)：Maven 单元/集成测试 tag 划分，后续须确认实际执行数。

## 其他意见

- 图已改为 Jenkins 主动拉取 GitHub，控制器/Registry/kind/构建容器位于 Docker Desktop 内；containerd 拉取镜像，Agent 经 API Server 发布；补充 Orders port-forward 和按服务拆分的数据依赖。
- 只改文档时跳过交付；使用文档路径的明确 allowlist，不只检查 src/k8s 两个目录，防止遗漏 Jenkinsfile、根级依赖和 learning 下真实部署脚本。
- 逐应用等待 rollout 后才更新下一个；五个 readinessProbe 已在清单确认，但实际业务可用仍需测试。
- 采用本地专用长期 token 简化演示，显式发布 KUBECONFIG、缺失即失败，写明撤销方式及个人可信环境边界。
- 增加 caffeinate/休眠说明；不以只设置 restart 策略就声称 Mac 重启后所有组件自动恢复。

## 请继续审查

优先复核：Carts 幂等建表的最小修复方案、release-state 中断恢复与 RECOVERY 分支、RBAC 是否足以支撑真实 kubectl 客户端、provider 断言是否漏掉覆盖来源、资源预留与 Docker VM 的实际关系。

本包没有声称任何新增验收已经通过。请继续以“源码已核实 / 待实现 / 待运行验证”区分结论，不因文档存在就认定功能完成。
