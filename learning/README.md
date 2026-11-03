# AWS / Kubernetes / Jenkins 本地学习实验

先在 Mac 上跑完整网店和真实流水线；本期不创建 AWS 资源。

- [当前完整架构与现状](ARCHITECTURE.md)
- [历史设计与评审快照](DESIGN.md)
- [运行手册](RUNBOOK.md)
- [验收清单](CHECKLIST.md)
- [最新实现与实测记录](IMPLEMENTATION.md)
- [架构图 Mermaid 源文件](architecture.mmd)
- [Kubernetes 清单](k8s/)
- [流水线入口](../Jenkinsfile)

网店：<http://127.0.0.1:8888>，Jenkins：<http://127.0.0.1:8080/job/retail-local/>。

本地 Secret、kubeconfig、Jenkins 登录凭据只在忽略目录中，不随仓库分发。学习顺序：先读服务调用链，再用 kubectl 观察部署和存储，最后用一次源码提交追踪完整 Jenkins 发布与恢复。
