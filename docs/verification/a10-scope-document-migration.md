# A10 活文档与覆盖依据迁移记录

依据 #126 的 S1(b)/S2(a) 与 #129 全部评论；基线 `78413e6524e0900cb7051a70adcf590fa2e01799`。
输入是已提交的 [scope-material-inventory](scope-material-inventory.json)，不反向改写该清查或既有证据。
规范逐项数据在 [迁移 JSON](a10-scope-document-migration.json)，本记录不进入任何 scope。

## 覆盖对象与修订口径

`tests/fixtures/a10_coverage.json` 的 `format_version=1` 不变，新增 `ledger_revision=2`。
693 个原 ID 的顺序、每项来源定位及原文、37 份来源全文与 SHA 均与基线逐项相同。
`methodology.scope` 明确区分固定行为/测试/冻结文档、仅作上下文的活文档和操作记录。
不放宽 `pointer_valid`；行为的公开指针与文档指针也必须指向固定集合。

2,237 条旧活文档指针逐 occurrence 记录 section、owner、field、旧路径、行为、需求 ID、
新指针和实际落点。只有从未独立承担覆盖的重复导航/背景可以 `remove_context`；
其余明确改指冻结证据或归入历史操作。混合条款的操作部分单列，产品部分保留自身代码与具体测试。

## 文档行为与处置差

- `documented_decisions` 仍为 `covered`，证明逐项核对的基线文档实际内容，涵盖类别、doiRA、主摘要、声明权威、通道及下述补齐的文档义务。
  ADR0033/0034 保持原字节；A10-101-AC-001/002 对规格、术语及具体文档内容的义务不能仅靠 ADR 存在证明，
  因而在 [冻结摘录](a10-documentation-excerpts.json) 保存实际缺口：规格 §4.3 两段、§13.1 首段、
  Fixture Audit 术语和 Contract 声明/来源规则短段。每段附基线提交、章节、原行号、整份来源 SHA、原文及摘录 SHA。
  它只保留已见内容，不另建随规格维护的规则，也不证明“文档先于代码”的时序或当前文档仍相同。
- `sampling_operational_docs` 与 `documents_and_operational_boundary` 改为 `operational`。
  #104–#106 完成/补修回帖是历史操作事实，指向原台账内嵌来源与仍冻结 history；文档存在及内容义务单独由冻结文档证明。
- 仅 `A10-104-BODY-001`、`A10-105-BODY-001`、`A10-106-BODY-001` 三个父票导航条目
  从 `covered` 改为 `operational`。它们不含独立产品 AC，原文和出处保留。
  其他具体产品条款继续由各自固定行为/测试承载；文档义务不得仅凭完成回帖继续 covered。
- `A10-100-C6405695568-CLAUSE-037` 从 `covered` 改为 `not_assessed`：基线 §8.4 未列 A10 新原因，Contract 与 GLOSSARY 两处已交付仍不足以证明三处登记全部完成。`a10_spec_reason_vocabulary` 明确记录缺口与后续词表维护责任；原文、来源与其余产品映射保持。

| 处置 | 迁移前 | 迁移后 | 差 |
| --- | ---: | ---: | ---: |
| covered | 550 | 546 | -4 |
| operational | 108 | 111 | +3 |
| not_assessed | 28 | 29 | +1 |
| superseded | 7 | 7 | 0 |
| 总计 | 693 | 693 | 0 |

## 操作与上下文的完整语义复核

`semantic_review` 固定复核输入 `7e4b732e89400fb78139c8b1f9a049bb390d2ab9`，穷尽原 `historical_operation`／`remove_context` 的 635 个指针、302 个 owner（276 个需求、15 个行为、4 个额外断言、7 个能力）。每个 owner 保留原动作、处置、内容义务判断和固定证据定位；不是只搜索两条已报告例子。原指针记录的 `behavior_ids` 保留迁移前定位，新增关联另记 `new_behavior_ids`。

其中 16 个需求含实际文档义务，原相关指针改为 `replace_frozen_evidence`：

| 需求 | 独立冻结内容 |
| --- | --- |
| A10-100-DECISION-017 | 原 backup history 中旧批次匹配程序恢复后显式升级说明 |
| A10-100-C6395756759-CLAUSE-038、A10-100-C6395889326-CLAUSE-061 | 原 Contract DOI 路由段（复用已有摘录） |
| A10-100-C6395756759-CLAUSE-071、A10-100-C6405695568-CLAUSE-049 | 原 Contract 声明目录、注册格式（复用已有摘录）；049 原 operational 处置保持 |
| A10-100-C6395756759-CLAUSE-115 | 原 Contract 路线原因与 GLOSSARY 审计词表 |
| A10-100-C6395889326-CLAUSE-083 | 原 backup Contract 的 Fixture 组合闭包与回放说明 |
| A10-100-C6405695568-CLAUSE-037 | 原 Contract／GLOSSARY 两处内容，另保留 §8.4 缺口边界；not_assessed |
| A10-100-C6405695568-CLAUSE-045 | 原规格 §13.2 ISTIC 只读预检注记 |
| A10-105-AC-010 | 原 Contract 不提供／不证明段与已保留规格 §4.3 的后续裁决边界 |
| A10-105-AC-013 | 原 Contract 中文帮助说明与固定 `audit_cli.py::HELP` 实际示例 |
| A10-105-C6411118599-CLAUSE-004 | 原 Contract A6 流键、原取得时间与 tie-break 映射 |
| A10-106-AC-010、A10-106-C6411119180-CLAUSE-001 | 原 Contract 四种操作的输入、副作用和证明范围矩阵；CLI 义务另有固定 HELP 与命令 |
| A10-106-C6411119180-CLAUSE-005 | 原 Contract commit/dirty 与 synthetic/live 证明边界 |
| A10-108-AC-004 | 原验证状态 Contract 的十四份 JSON／十二份主要文件说明 |

新增 11 段最小摘录，仍仅从固定基线 `78413e6` 逐字取回；全部 15 段附提交、整份来源 SHA、章节／原行号及原文 SHA。§8.4 摘录明确证明缺口边界，不冒充已交付。未复制整份活规范，也未把 37 份需求来源自身当作交付证据。其余 owner 为产品／测试／登记行为、导航或历史操作，原文档指针没有独立内容义务；实际固定公开指针与测试保留。`pointer_valid` 完全未改。

## 移除绑定与替代依据

先让新台账所有指针在迁移后的固定集合内闭合，再移除以下六条；逐项旧类别、SHA 和清查替代依据也原样保留于迁移 JSON。

| A10 移除路径 | 旧 SHA-256 | 原类别 |
| --- | --- | --- |
| `GLOSSARY.md` | `8864217fad4e0174398d314230155e145ee9b82185c0af5cf2769e38c88fc4d7` | live_document |
| `README.md` | `182b43f5d62898f8aa0261d20f80d3c1e0068d1b0f8a53c786f7c266f2d9a277` | live_document |
| `docs/contracts/backup-restore.md` | `accd5a6e259eac637dcb834b34288e1efe4914915ba66c7ef88d5aaf486dcc6a` | live_document |
| `docs/contracts/fixture-audit.md` | `535e23b9f1e83ce86cb1f58150cf86fd7c291e8983518b2e3deb82fcfaa48138` | live_document |
| `docs/contracts/verification-status.md` | `f485b6b6ebad3cf7791f69834fa0a00617b108a35ead4e74894100e7f0b826e8` | live_document |
| `intent/draft.md` | `1c6afa02e0bb16cb29263db3ea10d06255489aeea224eb6150bcf4c983f99f9d` | live_document |

具体文档义务由冻结摘录、既有 ADR、A10 需求台账及两份 history 承载，纯上下文删除。
新增冻结摘录进入 A10 fixture 集合；原台账、history、ADR、代码、测试、fixture、依赖身份继续绑定。
新迁移 JSON/本文仅为迁移记录，不成为覆盖证据的自引用目标。

## 冻结负例与分母

只修改 `tests/test_a10_integrity.py::test_actual_rule_support_and_coverage_bytes_are_fixed` 的一个参数：
`docs/contracts/fixture-audit.md` → `docs/adr/0032-relax-paper-acquisition-without-evading-access-controls.md`。
后者是本组仍冻结且原参数表未出现的材料；10 个参数等量，原有失败状态、scope_drift、identity_changed 和隐私断言不变。
模块 108 例、A10 的 37 模块/450 例固定分母不变。新回归在独立未绑定模块 `tests/test_a10_scope_migration.py`（18 例）和 `tests/test_a10_document_obligations.py`（17 例）；既有冻结分母不变。

## 验证与收口责任

新回归覆盖逐条保真与处置差、指针实际去向、摘录逐字回放、六份文档同时变化后的 writer，
以及旧修订、来源 SHA、需求 ID、固定集合外的公开/文档/能力指针、操作冒充覆盖、仍冻结字节损坏等拒绝。
合成 writer 在临时副本、内存中注入已审阅候选 SHA；不写正式 scope、回执或验收目录。

本票不机械传递重绑：生产树中已改 validator、覆盖 JSON、冻结测试及上游 scope 的预计漂移交 #131 统一审阅。
既有相关子集和 acceptance 兼容组合在隔离候选副本验证；副本的受控临时重绑不成为正式登记或验收结论。
完整离线门禁只由收口执行者按用户指令运行。本次没有 live、Pi RPC、模型质量、正式校准、Docling 或 NAS 验证。
