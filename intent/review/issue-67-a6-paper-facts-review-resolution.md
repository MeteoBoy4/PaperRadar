# #67 A6 r1/r2 审查处置

基线为 `706ecb1dc4c0354f0c00738d611b23af5f3abd33`。本次逐条复核两份外部报告，
按已裁决的边界实施合理修复；[r1](issue-67-a6-paper-facts-review-r1.md) 与
[r2](issue-67-a6-paper-facts-review-r2.md) 正文、原快照、来源限制和历史完成状态均保留，
仅追加处置索引。本表不把静态观察、历史门禁或本次子集当作最终完整门禁结果。

## 实际改动与不变边界

DOI 剥离一次支持包装后仍以 `doi:`/`http:`/`https:` 开头时返回 `unsupported_form`，
不递归解码；更正三条旧向量原因，未改变接受集合或规范 DOI。读取接口原样保留普通
`StorageError` 的缺库、未初始化、旧 revision 等原因；制品 `ArtifactError` 是其子类，
仍以窄转换保留 `PaperError/corrupt_reference`。真实 SQL/持久引用损坏仍受控拒绝。
写回执及映射结果的封闭原因没有扩充，映射已有存储失败兼容转换保持。

CLI 缺制品根在数据库 I/O 前退出 2；直接服务核验缺根为 `invalid_observation/data_root`。
URL 错误准确指向 provider/query_key/fields.*.locator/relations.locator/source_url，
不包含原 URL。show 文本增加当前选择 ID、版本、原因与时间；trace 沿用完整历史输出。
A6 实际 `mapping_result` 从 `ScreeningMappingResult` dataclass 的 `format_version`
字段默认值读取，和独立期望 1 比较，不在 writer 伪造生产值。

规范事实、仲裁来源及关系状态用领域 Literal 别名；规范关系 kind 仅允许规范方向，
raw_kind 允许两个原别名。原始输入 source_kind/kind 及 relations 的开放校验层保持，
避免将 unsupported_source/unsupported_relation 提前变为 invalid_observation，
也避免基类重校验丢弃或拒绝 NormalizedRelation 的 raw_*。
没有为静态注解增加多层输入框架。直接构造的脱敏 ValueError 参与 Pydantic union
候选回退，应用 model_validate* 负责最终 PaperError；合法日期字典回归固定这一差别。

choose/explain 共用最高 parser 键与 max 规则；包内共用名改为 require_utc_timestamp、
require_uuid、load_candidate、identity_conflict_result、insert_candidates、
saved_acquisition_result，未增加顶层 API。重复 retry SQL 改为复用首行，原先精确重试、
身份核对与异内容拒绝顺序保留。末次回执 update 只写 status/reason；同事务读取关系前的
response_bytes_retained 写入保留。manual 的摘要输入命名改为 interpretation_input。

没有 migration、StageInput 或四份 Frozen Contract 版本改动，没有大模块拆分或文件搬迁。
历史 A5 七份主文件文案增加时间限定并链接当前八份主文件/十份 JSON；原 A5 范围、
NOT_ASSESSED 和历史 JSON 不变。

## r1 全部编号

| 轴/ID | 裁决 | 证据、实施与验证 |
| --- | --- | --- |
| Standards F1 | 部分采纳 | 收紧规范关系及内部来源/状态类型；原始 str/object 承担专用拒绝和 raw_* 保留边界，不能照建议全面提前 Literal 化。review_boundaries 的未知来源、Typed/dict 关系和原书写用例；mypy。 |
| Standards F2 | 不采纳 blanket 删除 catch | 读取侧消费持久行、JSON 与原始人工材料，坏结构、缺关系、非法持久 URL 都是引用损坏；报告没有合法数据程序故障复现，不能削弱 fail-closed。真实环境原因另按 r2 H2 分离；backup/recovery_damage/integrity 固定受控拒绝。 |
| Standards F3 | 不采纳整流程统一 | Feed first_seen、manual parser=1/事件与 actor、publisher 取得时序及 raw DOI 均是既有语义；无具体默认值缺陷。现有共用 update_revision 与回执决定保留，避免大记账函数隐藏差别。acquisitions/feed/manual 及组合恢复回归。 |
| Standards F4 | 采纳 | choose_fields/explain_fields 共用 _parser_key/_highest_parsers。原 source_arbitration、paper_reparse、feed_arbitration 公共回归保护获选与说明。 |
| Standards F5 | 采纳 | 六组跨模块私有名改为准确包内共享名，更新引用和 A6 哈希；无顶层导出扩张。完整 A6 子集、Ruff/mypy。 |
| Standards F6 | 不采纳本次拆模块 | 行数不足以证明职责冲突；读取、历史与完整引用校验共享事实闭包，本次修复无需移动。架构观察保留为以后有具体行为收益时的工作。 |
| Standards F7 | 采纳 | README、stage-inputs 明确 A5 历史计数，链接当前说明；不回改旧证据。 |
| Standards F8 | 不采纳两项建议 | 直接将 __init__ 改 PaperError 会中止 union 候选尝试，使合法日期字典无法选 DateValue，review_boundaries 固定合法路径；保留脱敏构造协议并说明。backup 内 import 与既有 CLI/备份延迟加载一致，无循环或功能失败证据，未仅因位置上提。 |
| Spec F1 | 部分采纳边界说明 | List<String>/Array<int> 与标签形状存在歧义，保留保守 invalid_text；拒绝白名单放宽。Contract/README 明确输入限制，新增三例标签形状拒绝、两例数学接受，规范文本版本/已接受值不变。 |
| Spec F2 | 部分采纳说明 | requires_merge 保留既有 DOI 成功提示，优先于 not_retained，不是 Paper 主 status 或新增材料证明。Contract 明确；旧候选复用测试继续通过，review_reads 补普通 volume 更新、关系断言不新增及精确重试原回执。 |
| Spec F3 | 采纳 | CLI 先校验 verify/root 组合，固定中文提示、退出 2、不建库、不透 ID；直接 trace 缺根 invalid_observation/data_root。review_reads 红→绿及旧 CLI 回归。 |

## r2 全部编号

| 轴/ID | 裁决 | 证据、实施与验证 |
| --- | --- | --- |
| Standards H1 | 采纳 | 双包装 unsupported_form 对齐 Contract；六例新增含大小写与 URL percent 编码，三条旧向量仅换原因。原 P1 偏高：这是拒绝分类一致性问题，不是接受非法 DOI 或数据损坏。 |
| Standards H2 | 采纳 | trace/show/revision/validate_all 环境 StorageError 原样；坏制品窄转换保留，backup 层继续翻译 StorageError。review_reads 12 例覆盖三种环境/四读接口及 CLI 指引；recovery_integrity missing/corrupt 先红后绿。写入及 mapping_result 形状不扩展。 |
| Standards H3 | 采纳 | require_public_url 接受受控 path，各调用点准确传入；五位置负例断言原因/路径和敏感字串不泄漏。 |
| Standards H4 | 部分采纳 | 同 r1 Standards F1。原始输入不是规范事实，不能为静态类型牺牲专用原因或原断言；内部已收紧。 |
| Standards H5 | 采纳 | 仅 show 文本补当前选择 ID/版本、reason、selected_at，trace 原序列保持；review_reads initial/journal_upgrade 两例红→绿。 |
| Standards H6 | 采纳 | 同 r1 Standards F7，历史计数注明当时边界。 |
| Standards S1 | 采纳 | 保存首个 retry 行，在身份检查后复用，不重复 SQL；精确重试优先和异内容校验顺序不改。acquisitions/reparse/process 回归。 |
| Standards S2 | 采纳 | 同 r1 Standards F4，最高 parser 共用纯 helper。 |
| Standards S3 | 不采纳 | 同 r1 Standards F3，来源记账差异是领域要求，不做大流程抽象。 |
| Standards S4 | 部分采纳 | 删除末次 update 的重复材料标志赋值；拒绝删除第一次写入，因为紧随 load_relations 会验证同事务材料保留标志，relation-only/复用字段新增关系需要该值。version_relation_materials/backup/recovery 回归。 |
| Standards S5 | 采纳 | 同 r1 Standards F5，包内共享名字和 scope 更新。 |
| Standards S6 | 采纳 | manual material 改 interpretation_input，原请求 payload、actor 审计材料和摘要计算不变。manual_corrections/source_backup 回归。 |
| Standards S7 | 不采纳本次拆模块 | 同 r1 Standards F6，记录架构观察而不扩大本次变更。 |
| Spec A1 | 采纳 | 同 r2 Standards H1，双包装错误分类对齐，不改变已接受规范值。 |
| Spec A2 | 采纳 | A6 独立期望增加 mapping_result=1，实际值读公共模型字段默认；review_formats 一例正常记录与 2/True/1.0 三例漂移拒绝红→绿；更新既有验收期望，原模块条数不变。 |
| Spec C1 | 部分采纳 | 同 r1 Spec F1，明确歧义输入限制，不声称泛型接受已修复；阶段 C 真实解析校验仍未验。 |
| Spec C2 | 部分采纳 | 同 r1 Spec F2，采纳报告提供的“补 Contract 后保留实现”路径；DOI 提示优先级和材料标志独立说明，精确旧回执不重算。 |
| Spec C3 | 采纳 | 同 r1 Spec F3，缺根属于参数错误而非损坏，不增加 reason 枚举。 |

r2 报告开头与 Standards 的“15 commits”是原历史元数据误计；实际
`git log main..706ecb1 --oneline` 为 14 条（包含 merge commit）。原文作为审查快照保留，
在此更正，不将它当产品缺陷。r1 的 14 条与实际一致。

## TDD、固定分母与验证

测试 seam 沿用已批准的 PaperFacts、公开纯规范化、CLI、backup 及 A6 writer/status。
新模块与固定用例数量为：

| 新模块 | 用例 | 覆盖 |
| --- | ---: | --- |
| tests/test_paper_review_boundaries.py | 22 | DOI/URL、歧义文本、原始拒绝、关系原书写、日期联合 |
| tests/test_paper_review_reads.py | 18 | 存储环境、缺根、show 选择、普通更新提示与精确回执 |
| tests/test_a6_review_formats.py | 4 | mapping_result 实际模型格式与严格版本反例 |

原固定回执范围并集 171 模块/3033 例保持条数；仅既有 DOI 三个期望类别及 A6 验收格式期望同步。
新增后固定回执范围收集并集 174 模块/3077 例（不是全套 pytest 总数）；A6 为 48 模块/543 例（原 45/499 加 3/44）。
全部新模块作为 A6 固定测试登记，源码/向量变更显式重哈希。按 A2-01→完整 A2→A3→A4→A5→A6
拓扑核对，本次前五组材料实际未变，只需 A6 的生产源码、验收期望、旧/新模块与向量哈希变化；
不是为上游零变化而强制造新绑定。处置报告不作为自绑定 scope 材料，但参与最终工作树身份。

工作树外 `/tmp/paperradar-67-r12/evidence/` 保存各轮 red/green、范围变更、静态检查和收集日志。
DOI 六例、存储十三例、缺根两例、URL 四个原错误路径、show 两例、mapping 四例均先失败后修复。
额外不变边界用例在整理前后通过；ArtifactError 子类边界以现有恢复测试两例先红后绿保护。
完整 gate 的 run_id 与终态不写回 tracked 文档；根代理将在本地提交冻结后运行唯一完整
`./scripts/check-offline`，其退出码及 verification-status 才是本次完整门槛证据。

提交前验证结果：A6 全部 48 个固定模块 **543 passed**（178.71 秒，零跳过/取消选择）；
全仓 `uv run --offline --locked ruff check .`、`ruff format --check .`（572 文件）、
`mypy`（377 文件）均返回 0。`uv run --offline --locked python -m scripts.audit_verification_scope
--collect --json` 返回 0，固定回执范围收集并集 174 模块/3077 例，哈希/依赖/计数无漂移。`git diff --check` 通过。
这些是提交前相关验证，最终完整门禁留给提交冻结后的主树运行。

## 剩余风险与未验 live

真实 Feed/Crossref/出版者、guid 裸 DOI、Wiley 落地页参数、eLocator、截断标记真实性和
parser 完整性均未验证；RPC、Pi、Docling、NAS、完整阶段 A、任务续跑、资格/预算/校准与
自动精读未验收。歧义标签形状文本仍明确拒绝。阶段 C 强冲突观察持久化及 parser 升级固定样本
回归/关键字段减少声明继续作为硬门禁。未增加 HTML 抽取、生产 adapter、merge/undo 或新任务能力。
