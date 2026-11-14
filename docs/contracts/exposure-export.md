# 冻结暴露清单 Contract v1

## 用途与范围

`experiment export-exposure --root ROOT` 把显式实验根内全部已暴露论文导出为不可改写、
版本化、内容寻址的私有 JSON，供 C 在保留器启用前机械排除正式校准。
SQLite 是登记与历史依据的唯一事实源；`views/exposure/EXPORT_ID.json` 是可重建投影。

## 规则

### 暴露并集与精度

只展示候选题名／摘要、普通 Feed／metadata 取得、无 prompt 模型映射探测均不计暴露。
完整历史并集包括：选样接受授权（含换下）、Screening 请求和 attempt、Read 请求和 attempt、
所有人工决定、独立 PDF 确认（即使附件失败或尚未附加）、全部 PDF 附件、持久报告成员。
报告 prepared 与 published 都计入；失败、未完成及被换下的事实不删除。

每个 Screening 请求和 attempt 使用其自身固定版本，不套用预算首版本、当前样本或今日选择。
Read attempt 使用领取时持久 metadata 的精确版本；没有 attempt 的历史 Read 登记只证明
论文级请求，内部审计明确 `read_request_precision=paper`，关联冻结时该论文已有强 DOI。
它不证明这些版本都曾发送给模型；不按墙钟或当前 PDF 推定登记瞬间版本，不回填历史请求。
已暴露精确版本缺 DOI，或论文级依据没有任何强 DOI 时，完整导出拒绝，不能静默漏项。

### 可移植字节与身份

UTF-8 JSON，键排序、紧凑 `,`／`:` 分隔符、非 ASCII 原样、无 BOM 或末尾换行。
`export_id` 是这些 payload 字节的 SHA-256；相同语义复用原登记及原字节，新语义形成新身份。
字段恰为：

| 字段 | 格式及含义 |
| --- | --- |
| domain | 固定 `paper-radar.exposure` |
| format_version | 整数 `1` |
| root_id | 原实验根的持久身份，恢复后保持 |
| papers | 按 DOI 排序的直接暴露种子；每项恰有 `doi`、`version_kind`、`categories` |
| doi | 论文身份权威规范化的 DOI；库无关版本强身份 |
| version_kind | `preprint` 或 `journal`，沿 ADR-0030 的 DOI／版本一对一规则 |
| categories | 去重排序的 `selection_authorization / screening_request / screening_attempt / read_request / read_attempt / decision / pdf_confirmation / pdf_attachment / report_member` |
| relations | 与种子相连的完整权威关系图，按预印本 DOI、正式版 DOI 排序去重；每项恰有 `kind=is-preprint-of`、`preprint_doi`、`journal_doi` |

payload 不含本库 paper/version/task/request UUID、metadata 修订号、物理位置、时钟、last_seen、
重复次数或派生状态；普通 metadata 修订、重复发现与重复关系 assertion 不改变内容身份。
新增类别、直接种子或相连权威边改变语义；无关图不扩大清单。

### C 的排除约定与合成示例

C 对规范 DOI 精确命中种子即排除，再沿 `is-preprint-of` 图的两个方向传播到所有可达端点。
端点尚未发现仍保留排除依据；`endpoint_missing`、`requires_merge` 都不能成为等待条件，
它们只描述本库归属，不否定权威断言。精确 DOI 排除与传播都不依赖临时 Paper 身份。

以下为合成示例，排版仅供阅读；正式文件使用上述规范序列化：

```json
{
  "domain": "paper-radar.exposure",
  "format_version": 1,
  "root_id": "00000000-0000-4000-8000-000000000200",
  "papers": [
    {"doi": "10.1/example-journal", "version_kind": "journal", "categories": ["decision"]}
  ],
  "relations": [
    {"kind": "is-preprint-of", "preprint_doi": "10.1/example-preprint", "journal_doi": "10.1/example-journal"}
  ]
}
```

C 即使尚未发现 `10.1/example-preprint`，以后取得该端点也继续排除；从预印本种子进入的
反向场景同样成立。`10.1/unrelated` 没有可达权威边就不扩大排除。未来新权威边或实体合并
由 C／I 在身份权威处保留排除依据；B 的格式不承担导入或合并引擎。

### 冻结审计、事务与恢复

`exposure_exports` 保存不可更新／删除的 export_id、root_id、格式版本、artifact_id、
审计摘要及独立完整 `scope_json`。`exposure_manifest` 制品恰有 `audit / payload` 两成员；
audit 留存各事实拥有者的完整持久主键集合、安全不可变引用及私有字段摘要，与可移植字节分离。
关系、任务、决定、PDF 和报告的 SQL／历史校验由各自公共组件拥有，导出服务只装配并集。

全历史捕获在一个显式一致读事务内；文件发布在事务外。最后短 `BEGIN IMMEDIATE` 只重核
根身份和各组件显式主键元数据集合，变动即 `facts_changed` 回滚登记。锁内不加载全历史或文件。
冻结范围不使用墙钟 as-of、当前选择或隐式 rowid；SQLite VACUUM 和标准恢复不会重解释其身份。

历史验证重读原冻结完整主键闭包，核对独立范围、不可变引用／摘要、root_id、两成员字节与
重建 payload。遗漏冻结项目、篡改引用或重算外层 hash 不能替代这个核验。
新请求、attempt 后续结算、lease 续期、prepared→published、metadata 修订或新关系追加不进入旧范围；
旧导出不与今日全集全等，也不是只核验今日一个未声明的子集。

`experiment.validation.validate_all` 是唯一备份聚合接线；登记、两成员及源闭包全部随业务备份。
`Exposures(database, data_root).payload/receipt/write/validate_all` 支持标准恢复的
`database.sqlite3 + blobs`，不要求原根、配置、模型、Docling 或网络；`write` 只重建输出，不写库或日志。
视图发布使用私有同目录临时文件、fsync 和不覆盖 hard-link；已有不同字节或软链受控拒绝。

### CLI 与隐私

执行入口显式注入所选根 FileSink。stdout 仅输出安全 export_id、root_id、格式、论文数与
相对视图引用；必要 DOI／关系／类别只在获准私有文件内。日志、错误不展开论文正文、自由文本或私有位置。
帮助纯本地，不开库、不建目录；自动配额 0，不调用来源、Pi、模型或 parser。

## 错误与拒绝

成功 `0`；参数、用途、强身份、闭包、文件或路径错误 `2`；用户中断 `130`。
`strong_identity_missing` 要求先在论文权威处补强 DOI；`facts_changed` 要求基于新事实显式重试；
`registration_invalid` 要求保留诊断、核对冻结范围及可信备份；`content_corrupt / unsafe_path`
要求保留原文件并核对受控位置。中断后重跑复用已有登记；不覆写损坏对象。
底层制品的 `publication_failed` 等受控原因沿[制品 Contract](artifact-store.md)保留。

## 不提供／不证明

不提供 C 导入器、全库 merge engine、跨库预算、正式校准资格或结果提升／复用。
合成离线恢复和 Python 冷守卫不证明现场 OS 隔离、真实材料质量或 NAS；责任见[路线图](../roadmap.md#模块承接索引)。

## 相关

- 依据：[ADR-0070](../adr/0070-freeze-stage-b-exposure-after-selection.md)、[ADR-0030](../adr/0030-paper-version-identity-and-source-observations.md)、[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
- 组合：[B 工作流](stage-b-workflow.md)、[备份与恢复](backup-restore.md)、[制品](artifact-store.md)。
- 独立覆盖：[B 暴露导出台账](../verification/issue-200-exposure-export.md)。
