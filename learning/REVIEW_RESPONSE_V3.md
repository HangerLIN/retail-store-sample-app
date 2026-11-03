# 现状架构评审回应

日期：2026-11-03。本文回应 ARCHITECTURE 第一版的评审，代码与证据已分开标注。

## 优先项处理

| 评审项 | 处理 | 验证边界 |
| --- | --- | --- |
| 1. 验收表缺失败主路径 | ARCHITECTURE、CHECKLIST、IMPLEMENTATION 补齐构建含义；#12 真实 Verify 失败回滚，#14 真实 recoveryFailed→修复候选发布 | 仍未覆盖 rollout 超时、镜像拉取、数据库迁移等失败模式；不借中断演练概括所有恢复 |
| 2. 证据轮转 | #3–#6 已 Keep forever；导出 #5 经过检查的 JSON 到 Git，IMPLEMENTATION 摘录完整五个 digest 和 60 项计数 | 保护普通构建轮转，不保护整个 Jenkins 卷丢失 |
| 3. 配置接纳 | 新增管理员 adopt-config；无 pending/recoveryFailed、镜像不漂移、rollout、完整 Verify、配置二次检查、resourceVersion 更新；只改指纹 | 临时无害配置已在真实集群完成拒绝→apply/rollout→adopt→恢复原配置→adopt，最终原状态内容不变 |
| 4. 作业标记 | description 区分部署、跳过、恢复、失败；跳过 NOT_BUILT；ACTION 判断统一，空值按 deploy | Jenkinsfile 已通过控制器校验；历史 #6–#9 不倒改成新规则 |
| 5. 状态测试 | recoveryFailed 原本就强制 needed=true；新增 22 项回归测试，包含多个表驱动场景、HTTP 连接中断和实际 shell 编排 | 外部 kubectl/Docker 使用替身；与真实集群验证分别记账 |
| 6. 冒烟过宽 | 精确匹配唯一订单对象中的 id、shippingAddress.firstName/email；JSON 25 秒超时、5 MiB 上限 | 已真实下单读回；跨订单标记、缺失/重复订单、响应超限有负例测试 |
| 7. macOS 生产依赖 | 现有生产镜像无 `.node`；生产打包目录新增检查，有原生 addon 即停止 | 开发依赖有 `.node` 不等于生产包含；其他平台特定行为仍需 Linux CI 验证，AWS 不直接复用本机构建路径 |
| 8. RBAC | 权限表明确 Deployment patch 可间接挂载 Secret；说明未授予 pods/log/events，由管理员诊断 | 本期不加入可选 AdmissionPolicy，不宣称强隔离 |
| 9. Mac 内存 | 构建采样增加 memory_pressure 与 swap；保留 Docker 用量、OOM 事件、Pod 前后重启和最近终止状态 | 不把新采样追认到历史 #5，不宣称单次样本代表容量上限 |

补充：所有应用测试现改为全部通过后再推送镜像。此前“测一个、推一个”的顺序不能保证后续服务测试失败时 Registry 不变。新隔离测试逐个让五个服务失败，确认没有任何推送调用；真实 Jenkins 中“测试失败不发布”仍标未验证。

Go 版本写入工具报告（本机 Catalog 为 go1.25.0 darwin/arm64）；node-config.sh 每次配置节点都会设置 unless-stopped。旧 Docker/JDK 不在此次升级，运行手册要求升级前后预检。MySQL 的重启历史和 OOMKilled 可见状态已补充，购物车第 33 条来源仍保留不确定性。

## 直接源码与证据链接

以下是完整地址，不依赖 GitHub 目录页或相对链接解析。若网页阅读受限，可使用右侧 raw 地址。

| 内容 | GitHub | Raw |
| --- | --- | --- |
| 流水线 | [Jenkinsfile](https://github.com/HangerLIN/retail-store-sample-app/blob/main/Jenkinsfile) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/Jenkinsfile) |
| 发布状态、恢复、配置接纳 | [release.py](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/scripts/release.py) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/scripts/release.py) |
| 冒烟 | [smoke.py](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/scripts/smoke.py) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/scripts/smoke.py) |
| CI 编排 | [ci.sh](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/scripts/ci.sh) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/scripts/ci.sh) |
| 配置清单 | [kustomization.yaml](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/k8s/kustomization.yaml) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/k8s/kustomization.yaml) |
| 发布权限 | [release-rbac.yaml](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/k8s/release-rbac.yaml) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/k8s/release-rbac.yaml) |
| 状态回归测试 | [test_release.py](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/tests/test_release.py) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/tests/test_release.py) |
| 冒烟回归测试 | [test_smoke.py](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/tests/test_smoke.py) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/tests/test_smoke.py) |
| CI 编排回归测试 | [test_ci.py](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/tests/test_ci.py) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/tests/test_ci.py) |
| #5 固定证据 | [build-5.json](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/evidence/build-5.json) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/evidence/build-5.json) |
| 当前架构 | [ARCHITECTURE.md](https://github.com/HangerLIN/retail-store-sample-app/blob/main/learning/ARCHITECTURE.md) | [raw](https://raw.githubusercontent.com/HangerLIN/retail-store-sample-app/main/learning/ARCHITECTURE.md) |

可本地重复的脚本验证：

```bash
env/python/bin/python -m unittest discover -s learning/tests -v
```

这些测试不需要运行 Docker 或 Kubernetes；执行实际 CI shell 的测试使用临时目录和假外部命令，不接触当前实验集群。

## 修改后的真实流水线结果

Jenkins #10 由 SCM 自动触发，源码 89540a95a737a9ac9da27398ee24388514c132c7，SUCCESS；构建描述为 deployed 89540a95a737。60 项应用测试、21 项脚本测试、生产依赖检查、完整下单及五个运行镜像核对均通过。#10 已永久保留，摘要与完整镜像引用补入 IMPLEMENTATION。

这验证的是正常发布路径及本次修改，未将其扩写为真实故障注入成功。

## 真实失败恢复补充

本轮随后完成 #12–#14 演练，完整证据和构建语义在 [IMPLEMENTATION.md](IMPLEMENTATION.md) 及 [failure-recovery-12-14.json](evidence/failure-recovery-12-14.json)。#12 验证 Verify 失败后自动回滚；#13 暴露并保留一个连接中断分类缺陷；#14 修复后验证 recoveryFailed 标记、强制完整构建和修复候选发布。三次均由 SCM 轮询触发、永久保留。
