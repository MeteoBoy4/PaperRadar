# Issue #142：pi_rpc 成功来源覆盖台账

依据：[#142](https://github.com/MeteoBoy4/PaperRadar/issues/142)、
[#140 最终 C/D 确认](https://github.com/MeteoBoy4/PaperRadar/issues/140#issuecomment-6559284609)。
这是 Pi 模块 S2 的合成离线工程证据，不是实际 Pi/供应商执行或兼容验收。

## 范围与公共边界

测试使用临时 SQLite、合成固定供给和执行候选，通过 `ScreeningTasks.run_once/submit`、
`load_success/query_successes/validate_all`、`create_backup/verify_backup/restore_backup`
观察 boundary/value 接收和恢复。测试 seam 已由父票确认。

`PiRpcAudit` 是持久审计格式 2 的唯一 Schema；test 审计、submission_digest 与既有材料
保持原字节和含义。没有 migration、证据表、config/models、启动器、Feed 消费或 doctor 改动。
一致性校验不是输出真实性证明；只有合成候选通过本票正向接收。

## D1 独立新增分母

| 独立测试模块 | 节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_pi_rpc_source.py` | 23 | boundary 重启回查；value 幂等及五种执行身份冲突；来源闭集、空模型观察、模型/业务权威；伪造引用拒绝；预算首次与本次回执审计 snapshot 区分 |
| `tests/test_pi_rpc_source_backup.py` | 21 | 混合 test/pi_rpc 冷进程隔离恢复；供给、安装、版本、格式、缺字段、类型、来源与隐私字段损坏的 load/validate_all/backup verify 拒绝 |
| 合计 | 44 | 不进入任何 A1–A10 历史组分母 |

支撑为 `tests/pi_rpc_source_support.py`，合成供给只替代下载器与程序边界，使用真实登记与文件。
备份恢复正例移走原根，冷进程审计钩子拒绝访问原根、原安装和备份目录后仍可查询校验。
首次新来源用例在现有仅 test 接收上失败，再实现审计与权威接收；后续非法来源形状和
身份冲突顺序也分别保留 red→green 修正。

## 开发期验证

- `uv run --offline --locked pytest -q tests/test_pi_rpc_source.py tests/test_pi_rpc_source_backup.py tests/test_a7_boundary_success.py tests/test_a7_value_success.py tests/test_a7_success_applicability.py tests/test_a7_success_integrity.py tests/test_a7_value_integrity.py tests/test_a7_success_backup.py tests/test_a7_value_backup.py tests/test_a8_rpc_value.py tests/test_a8_rpc_history.py tests/test_a8_rpc_backup.py`：156 passed，99.08s。包含上述 44 新节点和 112 既有行为回归；既有测试及 A7/A8 支撑未修改。
- 相关 Ruff check/format：通过；全库 `uv run --offline --locked mypy`：717 files 通过。
- `./scripts/check-compatibility cli`：59 passed，63.35s；组合入口退出 0，实测总耗时 63.60s。
- 本票没有运行完整离线门禁，没有正式验收回执，也没有 live、网络、真实认证或模型调用。

## 材料漂移与集成承接

实际修改的既有固定源码为 `screening_tasks/{__init__,success,success_models,success_rules,success_integrity}.py`；
新增 `screening_tasks/pi_rpc_audit.py`、`success_references.py`、上述测试/支撑和本台账。
README、GLOSSARY、screening-tasks/pi-rpc Contract 原地更新现状，不扩展历史证明范围。
S4 在集成树审阅实际 diff、按唯一固定范围规则登记新增材料与必要精确重绑；S2 不重绑 scope。

历史 A7/A8 冻结测试、计数、fixture、DERIVED 来源、旧审计与历史备份材料均保持不变。
S3 接入受控执行链并重新检查当前准入，恢复历史成功不授予执行许可；
S4 汇总集成与门禁；Cwd/Live 仍负责现场权限、实际 1.4.0、认证、模型/参数与报告用量兼容。
生产来源、根用途和质量资格继续分别判断，B 实验产物不会因非 test 来源获得正常消费资格。
