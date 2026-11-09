# #168 / #170：回执与独立准入账本覆盖

本台账只覆盖版本回执、受保护接收、批准计划与只读查询的公开边界。
新增测试独立未绑定，不扩大历史 required 集合、组回执或固定分母。
本票不改既有 scope 或 `scripts/verification_scope_materials.py` 的成员／哈希；
新增消费闭包与文档分类由 #176 明确审阅收口。历史回执、#167 证据及旧 Frozen Contract 原字节保持。

## 公共 seams 与覆盖

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_live_evidence_receipt.py` | 14 | Pydantic 格式／完整绑定、计划／零预算、失败一致性、原时点、供应商主张隔离与依据冲突 |
| `tests/test_live_evidence_ledger.py` | 15 | 可信接收／幂等／只读回查、信任拒绝、接收原子审计、首失败停止、批准计划与独立账本 Schema |
| `tests/test_live_evidence_contract.py` | 2 | 权威 Schema／新快照一致性与显式选择、旧历史集合不扩张 |
| `tests/test_live_evidence_cli.py` | 4 | 三处冷帮助禁外部 I/O、新契约错误指引与旧完整句兼容 |
| 合计 | 35 | 独立未绑定新增覆盖 |

`tests/live_evidence_ledger_support.py` 仅提供合成计划／回执与临时目录。
OS fixture 显式替换可信 uid 与锚，模拟独立产品 uid；不使用 sudo、不写真实账本，
不构成真实 root 权限、sudoers、collector 来源完备性或部署行为证明。
产品 CLI 不提供这些 fixture 策略覆盖选项，默认只信 root 所有的固定路径与全部祖先。

Schema 一致性节点 `test_ledger_schema_is_separate_and_newer_version_is_never_written`
独立断言必需表列、DELETE journal、schema 1 与更高版本读写拒绝且原字节不变。
新回执由 `test_receipt_frozen_contract_matches_authority_and_committed_snapshot`
对照唯一 Pydantic 权威与提交快照；原五份快照及业务 Alembic revision 均未改变。

## 开发验证与预期漂移

TDD 的回执、接收／查询、beta 禁止供应商授予、Frozen Contract／冷帮助、批准计划回查、
verified 与 not_observed 冲突均记录失败后最小实现转绿。
旧契约 CLI 最初因新增选项改变完整错误句而有 2 failed；修复保留旧完整句并追加新选项，
原测试不改，相关旧契约与账本组合随后 51 passed。独立模块收集核对为 35 节点。
局部 Ruff／格式与 mypy，以及旧 Frozen Contract 相关回归与 CLI compatibility 均作为开发验证，
不发布 A1–A10 或正式完整门禁结论。最终六模块实测为 83 passed（新增 35＋既有契约 48），退出 0；
CLI compatibility 为 59 passed，入口退出 0；Ruff、17 文件格式检查与 mypy 17 文件均通过，
新 Frozen Contract check 与 git diff --check 通过。不写 run_id。

`src/paper_radar/contracts/schema.py` 与 `src/paper_radar/cli.py` 的实现字节必然产生既有
source/support 哈希漂移：前者直接涉及 A9/A10；后者直接涉及 A2-01／完整A2／A3／A4／A6／A9／A10，
下游显式 scope DAG 的语义核对交 #176。新回执快照、源码、测试、支撑、ADR0055 与本台账
均作为新固定材料交收口登记；不以当前全量 pytest 的退出约束冒充进入旧回执。
新 Contract 的精确分类也交 #176，不自动解除固定材料约束。
基于 integration tip 的开发期只读审计退出 1，issues 与 baseline_issues 均为空，
仅上述两个 source_support 路径产生 current_change/mechanical 漂移，按流程留收口处理；
这不构成正式最终树 scope 结论。

## 后继与未验 live

#171 复用 `receipt.canonical_bytes`／`content_sha256`／`EvidenceReceipt.receipt_id` 的 ID 规则，
以及 `EvidenceLedger.connection(writable=...)` 的受保护连接边界和 show／show_plan 查询。
账本 schema 版本与回执格式分别演进，不自动假定读写兼容；激活／撤销／恢复与时钟水位线由 #171 完成。
#172 提供 root 冻结部署、collector 与保护入口，只能由所有者审阅后部署；本票没有实际安装、
认证、网络／模型采集、历史导入或证据激活。产品 loader 仍返回 None，未新增执行放行路径。

接收只核可信来源、完整性与内部一致性，不证明没有遗漏失败，后者仍由 collector 与 sudoers 负责。
单独备份／恢复及恢复后所有激活失效的决策见 ADR0055，实际恢复执行服务由 #171 承接；
产品不得自行恢复 journal 或重建信任根。完整离线门禁留 #176 冻结最终树并获授权后执行。
