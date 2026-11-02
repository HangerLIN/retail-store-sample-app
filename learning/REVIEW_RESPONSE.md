# Claude 第二轮 CR 回应

日期：2026-11-03。对应 DESIGN.md v3；历史回应保留于 [REVIEW_RESPONSE_V2.md](REVIEW_RESPONSE_V2.md)。本轮只修改设计和图，源码修复与清单部署仍待实施，不把下面的计划当成完成结果。

## 优先事项

| 条目 | 本轮处理 |
| --- | --- |
| DynamoDB Recreate 不足 | 采纳：改为单副本 StatefulSet + governing Service + PVC。移除旧 Deployment，禁止 force delete。验收允许瞬时不可用，但要求成功写入可恢复、无实例重叠和库锁错误。 |
| Carts 幂等 init | 采纳最小改动。保持开关名，明确语义变为缺表创建；竞争和新建路径也在 waiter 后重读校验 GSI，检查 waiter 失败。已有无 GSI 表必须报错且保留数据。示意代码未编译，本轮未实施。 |
| provider 校验 | 删除覆盖优先级解析器。采用渲染/live spec 比对、管理员 Secret key allowlist 与密码字面量扫描、后端 topology 运行时证据。配置使用带 hash 的 ConfigMap，最后仍做跨重启数据验证。 |
| release-state 边界 | 增加 ACTION=reconcile 手动处理无新提交时的中断；diff 基线改 lastGood.sourceSha；部署前 HEAD 验证 lastGood 镜像可取。首次五服务镜像统一本地构建并验证，不引入复制公共镜像且承诺 digest 不变的步骤。 |
| RBAC 客户端行为 | 逐个点名 Deployment；按 v1.37 实际 rollout/port-forward 验证 list/watch/field selector 和 WebSocket 子资源权限。管理员检查 deploy/sts/pod 中无密码字面量，不能用禁读 Secret 掩盖 spec 暴露。 |
| 内存决策 | 本机已测 16 GiB；空集群约 569 MiB、其他 timescaledb 约 95 MiB，完整网店/Jenkins 未启动。完整基线接近 5 GiB 时先核实宿主机余量再评估 10 GiB Docker，不直接默认分配 12 GiB。加入持续 Docker OOM 事件采集。 |

## 新核实的源码事实

- [Checkout package](../src/checkout/package.json) 声明 Yarn 4.11.0，test=exit 0。当前 `src/` 下无 `*.spec.ts`；真实测试在 [test/app.e2e-spec.ts](../src/checkout/test/app.e2e-spec.ts) 和 [test/chaos.e2e-spec.ts](../src/checkout/test/chaos.e2e-spec.ts)。非零断言针对实际存在的测试集合，不要求不存在的单元测试集合假通过。
- [.yarnrc.yml](../.yarnrc.yml) 已指定仓库内 [.yarn/releases/yarn-4.11.0.cjs](../.yarn/releases/yarn-4.11.0.cjs)。Agent 可直接用 Node 调用固定 Yarn 文件并执行 immutable 安装，避免额外依赖 Corepack。若采用 Corepack 则单独固定并验证。
- [Catalog topology](../src/catalog/main.go) 读取启动时加载的 `config.Database`；[Carts topology](../src/cart/src/main/java/com/amazon/sample/carts/web/TopologyController.java) 和 [Orders topology](../src/orders/src/main/java/com/amazon/sample/orders/web/TopologyController.java) 使用 Spring 注入属性；[Checkout topology](../src/checkout/src/app.controller.ts) 使用 ConfigService。它们是生效配置的证据，但不是数据库读写成功的证明。
- Checkout topology 不返回 Orders endpoint；[UI topology](../src/ui/src/main/java/com/amazon/sample/ui/web/TopologyController.java) 是聚合 HTML。设计不承诺所有字段都能从单个 JSON 接口读到，缺失字段以 spec 与业务链路交叉验证。
- [OrderController](../src/orders/src/main/java/com/amazon/sample/orders/web/OrderController.java) GET `/orders` 返回全部列表，[OrderService](../src/orders/src/main/java/com/amazon/sample/orders/services/OrderService.java) 使用 findAll，无分页。使用本次响应 ID 精确匹配，不假设服务端过滤；短期允许虚构测试数据累积。
- [DynamoDBCartService](../src/cart/src/main/java/com/amazon/sample/carts/services/DynamoDBCartService.java) 新条目数量固定 1、Optional.of 可能处理不了不存在的条目，均与评审一致。本期不修这两点，冒烟不依赖多件新增或删除不存在条目成功。

## 简化与保留边界

- 采纳取消 RECOVERY 参数；ACTION=deploy 下，仅应用健康/rollout 恢复失败、其他结构性前提都满足时，允许候选继续。API/权限/PVC/配置指纹/镜像可达性故障仍停止。不能无条件承诺继续发布“不会更糟”。ACTION=reconcile 失败不自动转为 deploy。
- 保留低成本 resourceVersion 更新，不增加专门的并发验收工程。
- 固定部署顺序 Orders→Checkout→Carts→Catalog→UI，逐个 rollout。缩短窗口但不声称解决新旧版本兼容性。
- stop 明确停止并保留现有项目容器与节点；start 恢复同一容器，reset 才删除。新增 Retain StorageClass 用于三个数据库，Released PV 需人工恢复绑定；kind 节点删除仍丢数据。
- Testcontainers/Ryuk 在预检验证。socket override 只在核实映射问题后显式设置，不关闭清理机制绕过失败。
- 给现有 kind 容器加内存硬上限不是默认修复；可能打到 kubelet/containerd，只作为单独实测的兜底实验。
- 配置采用 hash 后，lastGood 增加非镜像配置指纹。管理员改配置需重新验证基线；第一版回滚只恢复镜像，不暗示能自动回退数据库配置或 schema。

## 给下一次评审的说明

完整基线源码、当前清单、设计 v3 和历史回应在同一离线包中。`learning/kind.yaml` 和 `learning/k8s/` 仍是实施前状态，未把设计里计划的 StatefulSet、generator、RBAC 等写进去；故这轮应审设计可执行性，不应把 YAML 与目标不同误读为已部署失败或已完成修复。

下一步进入实施时，先修 Carts 并运行真实回归，再做持久化/配置 overlay 和资源基线测量。所有未运行的验证都继续标为未验证。
