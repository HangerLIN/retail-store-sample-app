# 本地实验验收清单

状态只在实际验收后勾选。设计目标不等于已完成。

- [x] 单节点 kind 与仅监听本机的网店端口。
- [x] Carts 初始化不再删表，新增数据保护回归测试。
- [x] Jenkins 控制器与原生 Mac Agent 连接。
- [x] 五个服务的真实测试全部通过，测试数量非零。
- [x] 全量本地镜像按 Registry digest 部署。
- [x] 受限 kubeconfig 完成网店下单与 Orders 持久化读回。
- [x] 发布身份禁止 exec、Secret 读取与 PVC 删除。
- [x] 配置漂移会被 preflight 拒绝。
- [x] Carts、DynamoDB、PostgreSQL Pod 重建保留数据。
- [x] RabbitMQ 重启后自动重连，并完成新下单。
- [ ] Jenkins 从 GitHub 拉取、测试、构建、发布成功。
- [x] 中断留下 pending 后能恢复 lastGood。
- [x] 构建期间记录总体内存、Docker OOM、Pod 重启信息。
- [ ] 文档提交按 lastGood.sourceSha 判定跳过。
- [ ] stop/start 同一批容器后数据仍在。
- [ ] Docker Desktop 重启验收（需安排重启窗口）。
- [ ] Mac 重启验收（需安排重启窗口）。
