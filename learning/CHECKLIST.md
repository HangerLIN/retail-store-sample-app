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
- [x] Jenkins 从 GitHub 拉取、测试、构建、发布成功。
- [x] 中断留下 pending 后能恢复 lastGood。
- [x] 构建期间记录总体内存、Docker OOM、Pod 重启信息。
- [x] 文档提交按 lastGood.sourceSha 判定跳过（Jenkins #6）。
- [x] stop/start 同一批容器后数据仍在。
- [x] Docker Desktop 重启验收（2026-11-03，经确认执行；原数据保留、Agent 自动重连）。
- [ ] Mac 重启验收（需安排重启窗口）。

## 评审后补充的边界与验证

- [x] #3–#6 构建永久保留；#5 关键证据导出到 Git。
- [x] 发布、冒烟和 CI 编排 22 项回归测试通过（包含表驱动子场景和 HTTP 连接中断）。
- [x] 管理员 adopt-config 在真实集群完成配置变更、接纳、恢复原配置闭环。
- [x] 冒烟按同一订单对象校验标记，限制 JSON 响应大小。
- [x] 当前 Checkout 生产镜像无 .node 文件，打包阶段新增检查。
- [ ] Jenkins 真实测试故障提交：集群与 Registry 不变（隔离 shell 编排测试已覆盖）。
- [x] Verify 失败后的真实集群自动回滚（#12：候选保留、lastGood 不变、pending 清除、回滚后下单）。
- [x] recoveryFailed 后修复候选真实发布（#14：恢复失败标记、完整构建、成功记录历史标记）。
- [ ] SCM 提交后刻意可见的页面改动验收（SCM 触发本身已确认）。
- [ ] Redis 单独重启后重新结账。
- [ ] 控制器容器删除重建后复用原卷。

- [x] 修订流水线的真实 SCM 自动发布（#10）：60 项应用测试 + 21 项脚本测试、严格冒烟、deployed 描述、新采样报告归档；#10 永久保留。
