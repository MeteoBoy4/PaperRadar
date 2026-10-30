# T07 调用隔离独立映射

本表只覆盖 boundary/value 调用描述、工厂与现有管道机制。doctor 的只读诊断证据独立保存，不能替代 T07。新增模块不改变 A8 或其他历史测试分母。

| T07 子项 | 公共接口与测试节点 | 证明边界／承接 |
| --- | --- | --- |
| 单次调用新会话、队列清空、取消与句柄回收 | `run_call`；`test_a8_rpc_protocol.py`、`test_a8_rpc_lifecycle.py`、`test_a8_rpc_pipes.py` | 已有合成工厂和本机测试管道；Pi/Cwd/Live 负责真实进程隔离 |
| boundary 不含 topics；两个阶段载荷键封闭 | `build_call` / `render_request`；新增 `test_t07_call_isolation.py::test_stage_payload_has_closed_keys_and_only_value_has_topics` | 只断言 boundary/value 当前协议 |
| 修正说明不跨论文、阶段或 attempt 泄漏 | `ScreeningTasks.run_once` → `run_call`；新增 `test_t07_call_isolation.py::test_correction_is_scoped_to_one_paper_stage_and_attempt`；已有 `test_a8_rpc_value.py::test_protocol_failure_does_not_contaminate_another_paper_session` | 相同工厂反复使用仍创建不同会话；不证明真实 Pi/OS 隔离 |
| 预算首次冻结语义；其他历史 Profile 不混入 | `ScreeningTasks.load_input` / `build_call`；`test_a8_call_description.py::test_receipt_audit_upgrade_keeps_first_semantics_and_same_budget`、新增 `test_t07_call_isolation.py::test_other_profile_does_not_replace_first_frozen_semantics` | 本次预算的历史 Profile 正是合法输入；禁止其他快照／论文的 Profile，不替换为当前 Profile |
| 当前支持范围外的 reuse/Read 调用受控拒绝 | `build_call`；新增 `test_t07_call_isolation.py::test_reuse_and_read_are_invalid_context` | reuse 使用公开 builder；Read 尚无 StageInput builder，仅探测 unsupported stage 早期拒绝；D/G/Body 另验真实消费者、map/reduce |
| 隐藏结果、正文与自动资源不进入 boundary/value | `test_a8_request_vectors.py::test_exact_request_bytes_preserve_only_bound_semantics`、封闭键集与独立 Profile 测试 | 当前请求载荷；生产启动器资源发现、个人设置与 cwd 权限由 Pi/Cwd/Live 验收 |

依据：#124、#120 最终 D1–D7；沿用 ADR-0026、ADR-0031 的冻结预算和执行审计分离。`build_call` 的支持范围保持 boundary/value，未新增生产消费者或执行来源。
