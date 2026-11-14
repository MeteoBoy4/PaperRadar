# #189 主机内存仅披露裁决跟进

本次跟进依据所有者 2026-11-14 主会话明确答复“仅披露”，代录于
[#185 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/185#issuecomment-6869017674)
和 [#189 跟进](https://github.com/MeteoBoy4/PaperRadar/issues/189#issuecomment-6869018082)。
本台账独立记录本轮变化，不改写此前待裁决实现的按次证据。

## 范围与政策

工作基线为 `integration/185-stage-b@91aec6c`，已合入 #190 的首张 B migration；
本轮不新增 migration，不修改 head、Schema、预算、授权链或其余必要闸门。
删除主机可用内存下限及未设政策阻断，不提供可注入的默认 8 GiB 主机阈值。

MemAvailable 采集成功输出 `passed/host_memory_observed` 与实测字节，`required=False`，
明确只是采集事实，不判断容量足够；缺失、不可读或格式异常输出
`not_assessed/host_memory_unknown`，明确 unknown，仍为非必需披露。
低于 8 GiB 或未知均不单独影响预检退出码。cwd、隔离、授权、cgroup 能力、模型临时
快照磁盘等必要项继续独立阻断；提取时 ≤8 GiB/swap=0 的约束未改变。

规格 §11 B/§14、B 工作流 Contract、CLI 帮助与 README 已同步该裁决，无新增 ADR。
这是 B 的可调执行政策，不建立 F 的通用阈值，也不构成现场资源验收。

## TDD 与 D1 变化

仍以临时根内真实 CLI 为主接缝，外部依赖维持既有合成供给、HTTP/Pi/Docling/时钟及
主机文件替身；未执行真实 preflight，不访问真实实验根或读取凭据。

新增 6 项参数化组合：1 KiB 实测值、测量文件缺失、测量格式异常，分别组合 cwd 必要项
通过／缺失。旧实现下先 **6 failed**，验证低值与未知被独立阻断、状态披露不符；
实现仅披露后 **6 passed**，既证明披露项不独立阻断，也证明必要失败仍拒绝。
原未冻结主机阈值用例改为“低内存实测仍披露并通过”，移除测试夹具注入的 8 GiB
主机政策。未删减历史组或成员；本独立 D1 从 35 例变为 **41 例**。

本票完整 D1：**41 passed**（26.76s）；补强缺项用例的临时主机文件替身后，
最终再次 **41 passed**（27.41s）。本轮其余组合与静态检查结果如下。

## 验证范围

- 默认 follow-imports 的严格 mypy，显式 `MYPYPATH=src`，覆盖本 D1 测试、整个
  `src/paper_radar/experiment`、`doctor/pi_exec.py`、`runtime_logging/schema.py`，
  **12 个文件通过**，没有 silent/skip、ignore、cast 或宽泛 Any 注解。
- B/doctor 相关组合 **152 passed**（150.90s），选择本 D1、实验 Feed、候选、选样、
  doctor pi-exec、doctor readonly 和 doctor docling-runtime 七个模块。
- `./scripts/check-compatibility cli` **59 passed**（79.06s）。
- 定向 Ruff、格式检查、`git diff --check` 通过。
- 不运行完整离线门禁；真实 Feed、认证、Pi/Docling、现场隔离与实际提取均未验证。

只读 scope 审计以 `91aec6c` 为 base、`integration/185-stage-b` 为 target，退出 1，
仅登记已有 baseline source/support 漂移：`backup/service.py`、`cli.py`、
`storage/artifact_contract.py`、`storage/schema.py`。本轮不机械重绑，既有 migration
敏感确认和集成最终树审计仍由 B 收口承接，不能将本次相对基线审计解释为其已通过。
