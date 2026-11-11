# #184 退役恢复 policy marker 严格认证覆盖

本台账记录失败准备退役公开接缝的独立 D1 开发回归，不扩大既有验收组成员、固定分母或 required 集合，不改写旧台账、回执、ADR 或历史向量。[现状契约](../contracts/live-evidence.md#封印放置策略生命周期)维护详细阶段规则，[ADR-0065](../adr/0065-retire-authenticated-failed-placement-preparation.md)继续作为既有决定。

## 接缝与拒绝保证

`FailedPreparationRetirement.check/prepare` 在委托旧、新 policy 生命周期及完成交接前，按退休阶段认证两份 marker 的完整封印身份、严格整数版本和规范 raw bytes。初始、removing、removed、preparing、prepared 各阶段的允许状态独立限定，包含 old.remove 与 new.prepare 内部已耐久提交的合法中断窗口。`prepared` 交接后保留新 policy 原生命周期四种阶段及显式恢复；无 descriptor 的普通生命周期和历史 reader 保持原字节。

新增 `tests/test_failed_preparation_policy_metadata.py` 共 **80 个节点**：原问题的布尔/浮点版本 2 个；旧 removing、新 preparing/prepared 与最终交接窗口的非对象、非整数版本、非法 phase、外来身份、额外字段及非规范字节 55 个；合法耐久中断续行 8 个；已知 phase 出现在错误窗口 8 个；交接后原生命周期四种阶段 4 个；必需 marker 缺失的精确路径/ENOENT 3 个。负例同时运行公开 check/prepare 或 prepare，绑定受控 reason 或具体缺失路径；比较完整账本文件集、原 bytes、模式、mtime/ctime 和 OS policy writes，拒绝先于 idle/preflight 回调及任何写入。原 history、业务状态、epoch 与失败快照仍保留。

原 `tests/test_failed_preparation_retirement.py` 仍为 44 个节点；其 missing 负例额外断言 `FileNotFoundError.errno == ENOENT` 且 `filename == str(model.old.journal)`，保留原失败类别、其余原因断言与零写断言。

## 当前源码与历史保护

新增 `pi-admission-v21` 与 `live-admission-source-guard-v21.json`，仍为原显式 **84 个源码成员**，仅 `preparation_retirement.py` 和 `current_binding.py` 的源码摘要变化。新向量字面量 pin 为 `9077b96b324e3f3a90b68741f6ce59184cfadd784c02e23fa3684acb8fccbef5`。当前 guard、bundle 与 epoch guard 消费节点指向 v21，归档参数追加 v20。

v1–v20 JSON 与原 20 个 pin 逐字保持；v20 pin 仍为 `d0638d3fdf1b9c36d7f87fb2ebbfe28c8bb5e18aaec2fc482f1605f354e6cc2e`。`PlacementPolicyLifecycle` 历史解析实现、ADR-0064/0065 正文、`uv.lock` 保持原字节；launch v10、placement v2、isolation v1、protocol v1 不变。没有新增生产模块或 marker writer，也不迁移旧证据。

## 相关验证

所有 Python 命令均通过 `uv run --offline --locked …` 执行。

| 模块或节点选择 | 实际收集节点数 |
| --- | ---: |
| `tests/test_failed_preparation_policy_metadata.py` | 80 |
| `tests/test_failed_preparation_retirement.py` | 44 |
| `tests/test_failed_preparation_descriptor.py` | 6 |
| `tests/test_failed_preparation_host.py` | 4 |
| `tests/test_failed_preparation_install.py` | 2 |
| `tests/test_preflight_system_bus.py` | 28 |
| `tests/test_live_apparmor_lifecycle.py` | 44 |
| `tests/test_live_admission_source_guard.py` | 23 |
| `tests/test_failed_preparation_sealing.py` | 8 |
| `tests/test_live_bundle.py::test_build_refuses_unreviewed_source_guard_before_freezing_or_output` | 1 |
| `tests/test_live_epoch_upgrade.py::test_changed_source_copy_refuses_stale_guard` | 1 |
| 合计（去重） | 241 |

修复前布尔/浮点两个公开回归均以 `DID NOT RAISE` 得到 RED；修复后同两节点 **2 passed / 4.26s**。恢复矩阵首批 73 节点与原 retirement 44 节点共 **117 passed / 216.53s**，新增交接/缺失路径 7 节点 **7 passed / 12.89s**。最终完整新 D1 模块 **80 passed / 157.58s**，其余消费者 **117 passed / 147.44s**，均退出 0。去重后的相关选择 241 个节点全部通过，无 skip、deselect 或 incomplete。

本次 7 个修改 Python 文件的 Ruff、格式和 mypy 均通过；历史字节与新向量实际源码逐成员核对通过。默认 pytest 临时目录出现既有残留清理告警，未清理其来源；最终 D1 使用独立临时目录。相关测试是开发回归，不是完整离线门禁或现场资格。

## 未验证边界与承接

仅使用普通离线 OS 模型和本地测试进程；没有访问真实受保护 runtime，未执行真实 AppArmor load/remove、namespace/mount、scope、认证、网络、模型、receive/activate、sudo、push 或 main 合并。真实系统 bus 私有挂载、canonical true exec-stop、root 预检、真实生命周期及最终包所有者审阅仍未验证。

合并树 compatibility、Schema/静态/固定范围审计、独立增量复审与最终完整离线门禁由 #177/#184 收口承接。本台账不替代旧 299 节点结果，不发布新包执行资格，不记录正式 run_id。
