# #184 双失败准备作废与无策略回滚（D1）

本台账覆盖显式 `failed_preparation_void` 新协议，不绑定既有 A1–A10 分母或历史回执，也不重写 ADR-0064–0066、v1–v23 封包或守卫。

| 独立测试模块 | 用例数 | 主要覆盖 |
| --- | ---: | --- |
| `tests/test_preparation_void.py` | 22 | 原字节归档与保全、失败回滚、显式恢复、六耐久检查点、四 kernel 中断、rollback_failed、回滚过程断电、未知/partial/原日志/.new 拒绝、候选 marker 严格版本 |
| `tests/test_preparation_void_descriptor.py` | 2 | 封闭 Schema、严格整数版本、明确双来源选择、规范序列化恢复 |
| `tests/test_preparation_void_install.py` | 5 | 聚合报告先于任何 kernel/归档/业务写入，FAIL/BLOCKED/未知 pending 拒绝，业务首写失败保留 prepared 责任边界、成功重入与 epoch 连续性 |
| `tests/test_preparation_void_baseline.py` | 5 | 候选 strict/negative 批准、零调用取消轮和 inbox 事实拒绝，四份非候选历史回执保留 |

共 34 项新增 D1 用例。合成 OS 模型通过公开 `describe_preparation_void`、`FailedPreparationVoid.check/prepare` 和 `LiveDeployment.install` 接缝验证；模型明确替代宿主身份与 kernel I/O，不把模型加载字节当真实 AppArmor、scope、manager、ptrace 或 true 执行的证明。

开发期间的源码守卫版本由集成者统一推进；私有 `/tmp` 开发入口暂时替代旧守卫检查，仅帮助验证上述行为，不构成正式守卫或完整离线门禁结论。最终封印守卫更新后必须直接通过锁定离线 pytest 重跑本表四个模块，连同 Schema/restore 一致性与受影响 CLI/旧恢复兼容检查。没有运行完整离线门禁，没有真实 root 策略、认证、网络、模型、receive 或 activate 操作。

相关：[生命周期契约](../contracts/live-evidence.md#封印放置策略生命周期)、[ADR-0067](../adr/0067-void-explicit-zero-operation-failed-preparations.md)。
