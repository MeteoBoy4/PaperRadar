# #184 preflight 最终源码向量与真实消费者覆盖

本台账记录系统 bus 与固定 true/失败准备退役修复合并后的独立开发验证，不扩大旧验收组成员、固定分母或 required 集合，不修改历史回执、Schema 或旧覆盖台账。功能覆盖分别见[系统 bus D1](issue-184-preflight-system-bus.md)和[失败准备退役 D1](issue-184-preparation-retirement.md)。

## 版本与保护边界

`pi-admission-v20` 的新向量显式包含原 83 个源码成员与新增的 `src/paper_radar/live_evidence/preparation_retirement.py`，共 84 个；其中既有 `collection.py` 包含只读停止事实查询。向量从两项修复合并后的实际源码逐成员计算，SHA-256 为 `d0638d3fdf1b9c36d7f87fb2ebbfe28c8bb5e18aaec2fc482f1605f354e6cc2e`，作为新字面量 pin 加入开发守卫。

v1–v19 JSON 与原 19 个 pin 保留原字节；v19 的原 pin 为 `dd418bdaff59b9845be32642daa7afea412569511f5d1b0f6298a1ab9cc449a6`。原归档参数追加 v19，当前 source guard、bundle 和 epoch 的向量路径改指 v20。原负例断言及拒绝行为保持。`pi-launch-1.4.0-v10`、`pi-placement-v2`、`pi-landlock-v1` 与 `pi-rpc-1.4.0-v1` 不变。旧源码向量不重绑，不迁移旧证据。

## 实际收集的相关消费者

| 模块或节点选择 | 节点数 | 本次消费边界 |
| --- | ---: | --- |
| `tests/test_preflight_system_bus.py` | 28 | 合并后的真实 fork/manager 控制流与离线 OS adapter |
| `tests/test_fixed_true_policy.py` | 6 | 真实 renderer、compile-only parser 与静态 native 编译 |
| `tests/test_failed_preparation_descriptor.py` | 6 | 有限 descriptor 严格解析 |
| `tests/test_failed_preparation_host.py` | 4 | 只读 idle 检查与 anchor 身份 |
| `tests/test_failed_preparation_retirement.py` | 44 | 真实封印、marker、epoch/祖先与 raw bytes 认证和有限恢复 |
| `tests/test_failed_preparation_sealing.py` | 8 | 当前真实 source guard 与公开 builder 封印 |
| `tests/test_failed_preparation_install.py` | 2 | installer/recovery 与新预检先于业务写入 |
| `tests/test_live_apparmor_lifecycle.py` | 44 | 原生命周期、恢复、退役与原始内核字节验证 |
| `tests/test_live_apparmor_attachment_readback.py` | 31 | 原 attachment 完整读回及拒绝 |
| `tests/test_live_admission_source_guard.py` | 22 | 当前 84 成员、原归档和同版本改源码/重绑拒绝 |
| `tests/test_live_bundle.py` | 11 | 当前真实 builder 与错误 source guard 拒绝 |
| `tests/test_live_epoch_upgrade.py` | 42 | 当前完整源码、epoch/祖先连续性与旧业务状态保护 |
| `tests/test_live_install_review_recovery.py` | 26 | 原审阅、安装与恢复接线 |
| `tests/test_live_collection_v2.py` | 22 | 原累计域、停止事实与采集规则回归 |
| `tests/test_live_admission_review_fixes.py::test_disk_source_change_is_rejected_by_a_cold_guard_process` | 2 | 冷进程拒绝同版本改源码及向量重绑 |
| `tests/test_live_admission_review_fixes.py::test_source_guard_explicitly_covers_resume_and_grant_authority` | 1 | 原恢复与授予权威显式闭包 |
| 合计 | 299 | 同一最终实际源码上的相关选择 |

计数来自实际 `--collect-only`，参数化按完整节点计数；前七个独立新 D1 模块为 28 + 70，其他消费者不因此进入新旧组回执。先前临时未来源码副本的模型结果不转移为本次生产向量或当前工作树结论。

同一实际源码上的完整相关选择实测为 **299 passed / 592.38s**，退出 0，无 skip、deselect 或 incomplete。四个改动 Python 文件的 Ruff、格式和 mypy 检查均通过；v1–v19 向量及 pin、锁文件和其余策略常量逐字保护检查通过。本次结果是开发期相关回归，不是正式完整门禁。

## 未验证边界与承接

本次仅运行普通离线开发测试和静态检查，不访问真实受保护 sealed runtime，不执行实际 AppArmor load/remove、namespace/mount、scope、认证、网络、模型、receive 或 activate，也不产生 root-positive 或执行资格。真实 root 元数据读取用于普通离线测试，执行用户仍为 UID1000。

合并树兼容组合、Schema/静态/固定范围审计、独立审阅与所有者对最终归档字节的审阅由 #177/#184 收口承接。完整离线门禁仍须在 #184 review closure 后由唯一执行者按用户明确授权运行；本台账不记录正式 run_id 或宣称现场预检成功。
