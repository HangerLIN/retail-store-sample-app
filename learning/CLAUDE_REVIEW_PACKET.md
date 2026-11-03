# Claude 评审包

本包提供可直接审阅的回应、证据与精确 diff。评审应使用固定 commit 的 raw 地址，不使用 GitHub 分支页缓存。

## 当前结论

- #12：真实 Verify 失败后，流水线为 FAILURE，五个 Deployment 回滚到原 lastGood，pending 清除，lastGood 的 sourceSha/verifiedAt 不变；回滚后完整下单成功，候选镜像仍留在 Registry。
- #13：真实恢复演练发现 `http.client.RemoteDisconnected` 未被业务不健康分类，未写 recoveryFailed；这是已修复的真实缺陷，不计入成功演练。
- #14：修复后，同类恢复失败真实写入 recoveryFailed，强制完整构建；恢复 UI 副本后候选发布成功，归档的 lastGood.recoveryFailed 为 true。
- #15：后续正常发布成功，当前 lastGood 已更新并把 recoveryFailed 回到 false；#14 的历史标记保留在归档与 Git 证据中。
- #12–#15 均由 Jenkins SCM 轮询触发；#12–#14 已 Keep forever，#15 的摘要在 IMPLEMENTATION 中。

## 审阅入口

- [完整架构现状](ARCHITECTURE.md)
- [逐条回应](REVIEW_RESPONSE_V3.md)
- [实施和验收记录](IMPLEMENTATION.md)
- [失败恢复证据](evidence/failure-recovery-12-14.json)
- [发布状态和恢复实现](scripts/release.py)
- [冒烟实现](scripts/smoke.py)
- [流水线](../Jenkinsfile)
- [状态机与 CI 回归测试](tests/test_release.py) 和 [测试编排](tests/test_ci.py)

## 复核清单

1. Jenkinsfile 的 ACTION 判断使用 `!= 'reconcile'`；部署、跳过和恢复有不同 description，跳过设为 NOT_BUILT。
2. `needed()` 在顶层 recoveryFailed 存在时强制返回 true；`learning/evidence/**` 被当作证据文档跳过，脚本、Jenkinsfile 和清单仍触发完整发布。
3. `adopt_config()` 要求管理员 context、没有 pending/recoveryFailed、线上镜像等于 lastGood、rollout 和完整 Verify 成功，并只改变 configFingerprint。
4. smoke 按同一个订单对象验证 id、firstName、email，限制 JSON 读取大小；`RemoteDisconnected` 被归为 UnhealthyRelease。
5. Checkout 生产依赖发现任何 `.node` 文件即硬失败；不会只打印警告。

精确脚本 diff 已生成到 `learning/evidence/review-diff-ac1521c-to-current.patch`。它是命令 `git diff ac1521c..HEAD -- Jenkinsfile learning/scripts/` 的可审阅输出；新提交仅添加此证据文件，不改变该 diff 的范围。
