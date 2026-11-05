# #155 两轮审查整改：独立增量证据

本次只核实并处置 [R1](../../intent/review/issue-155-body-read-integration-review-r1.md) 与
[R2](../../intent/review/issue-155-body-read-integration-review-r2.md) 的发现。原文保留，处置
追加在各报告末尾；原静态判断与后续实测分开。关联父票
[#155](https://github.com/MeteoBoy4/PaperRadar/issues/155)，对应正文制品 #156、持久前置
#158、Docling #159、Read 任务 #161、查询 #163；元数据 helper 仅服务既有历史闭包。

实施基线为当前 `integration/body-155` 的 `6e15d1cdfea10353437c7394f5966fedf0017ea8`。
用户明确排除最后 `6e15d1c` 的补充文档提交；R2 Spec 1 因此范围排除，不改写 #165
已发布台账或 133 项材料 JSON，不重新登记补充文档，也不重跑 smoke。
未知文档仍按固定材料处理；原报告称其为 live 不是分类依据。
原完整门禁只属于 `65a5c12` 的历史树；本轮未运行完整离线门禁，不主张当前树
`passed/verified/same`。R1 Spec reviewer 未完成，无可补造的 findings，也不升级为通过。

## 逐条处置

| 编号 | 处置与依据 | 验证与风险边界 |
| --- | --- | --- |
| R1 Standards 1 | 采纳。FulltextError 按九类 FulltextReason 提供安全中文下一步；遵守 cli-output 和日志隐私规则，保留 reason/quality。 | `test_fulltext_review_guidance.py` 九节点修前失败、修后通过；只用受控文本，不回显路径或原异常。 |
| R1 Standards 2 | 采纳局部重复判断。Body 低层 `pdf.valid_pdf_bytes` 统一 SHA-256、`%PDF-` 与 1024 下限；四个消费者继续各自映射 BodyError、ReadTaskError 或恢复拒绝。 | Body/fulltext/Read 前置与恢复组合；不合并 attach 的输入类型检查或外部上传规则，不证明真实 PDF 归属或可解析。 |
| R1 Standards 3 | 采纳。元数据 `_verify_route_closure` 统一 DOI、规则及 acquisition 闭包；仅历史调用显式传 `revision_no`，保留 result_revision_no 不得晚于所引修订。 | `test_historical_metadata_cannot_borrow_a_later_acquisition`、历史新事实及 metadata 子集；不以当前资格替换历史。 |
| R1 Standards 4 | 采纳。全仓检索只有 `prepare_correction` 的业务消费者与 Contract；把实现移到该入口，删除无调用的 correction 转发关系。 | Read execution RPC/history 与 tasks 子集；未承诺仓库外对未文档化 correction 的调用兼容。 |
| R2 Standards 1：规则与命名 | 部分采纳。契约明确兼容字段 restricted_content_warning 指任意非丢弃的程序降级诊断。GLOSSARY 的降级诊断含“数值或受限源内容”，普通数值置真并非已证实 Bug。拒绝 DTO 改名与改变告警政策。 | 新查询三节点独立验证 number_not_supported、discard-only、model-warning-only，另保留公式正例；B/H 仍须显著展示未核对与丢弃。 |
| R2 Standards 2：值对象 | 采纳。内部 frozen ReadBasis 单处声明九键，encode/decode 固定形状；消费者用属性，不再重复键集。公开 `ReadAttempt.basis` 和服务返回仍为 dict[str, str\|None]，JSON 编码仍由原 repository 负责。 | 新领取依据五节点人工九键预期、缺键/额外键/bool/int 拒绝及只读不改历史字节；原历史资格、备份与冷恢复继续验证，不重写旧 basis。 |
| R2 Standards 3：枚举比较 | 采纳。复用 RootPurpose、QualityBasis、ExecutionSource 和实际存在的 ReadV2DiagnosticReason；原报告所说 ReadIssue 本身是 dataclass，未凭名称造新枚举。 | 原生产/实验、普通消费与警告分支回归；序列化值不变，历史字典仍用等值比较。 |
| R2 Standards 3：预检原因 | 采纳受控闭集方向。实际环境拒绝为五种 dependency/platform 原因，选择失败 selection_invalid；probe 另有 runtime_selection_invalid，部署/复制/哈希错误统一 model_deployment_invalid；参数仍由 DoclingRun 校验。枚举保留这些原值，未知直接构造拒绝且不回显。 | 新预检八个合法原因、一未知原因，以及原公共 preflight 不领取测试；没有为 SDK/native/模型加载失败新增预检原因。 |
| R2 Standards 4 | 采纳真实 Bug；拒绝仅 getattr(result, ...) 的不完整建议。领取后先初始化峰值 0，convert 成功立即保存返回峰值，FulltextError 分支读该值。 | 新 parser FulltextError 回归先 RED UnboundLocalError，再 GREEN；另验证 publish 拒绝仍保留 4096 峰值、永久结算、已花预算和 absent 质量。 |
| R2 Standards 5：常量 | 采纳。历史分支只读引用 reading.context / reading.numbers 的 v1 常量；冻结 v1 源码不改。 | v1 历史分析恢复及现有规则拒绝/降级组合，不新增 migration，不改规则值。 |
| R2 Standards 5：none | 采纳契约澄清：历史 limitation_rule_version="none" 表示无独立限制策略版本，以冻结 v1 重放，不补造 v2 诊断。 | `test_synthetic_v1_history_replays_using_frozen_v1_acceptance`；值与旧存储形状不变。 |
| R2 Standards 6：digest | 拒绝统一。Body 默认 JSON 空格与 Read 紧凑 JSON 已参与各自持久 request_hash；相同值跨服务哈希相等没有需求/Contract 依据，统一会破坏历史幂等。 | 两 repository 原字节未改，各自请求冲突、精确幂等、历史回放/恢复验证；不新增无需求的跨服务相等断言。 |
| R2 Standards 6：required/transaction | 拒绝泛型抽取。相似实现很短，但独立受控错误与事务是两服务的边界；参数化错误工厂增加抽象，不能解决真实共享消费需求。ADR-0045 已选择独立 Read 内核。 | Body/Read 原子提交、恢复和幂等既有测试；不建立统一错误或统一短事务公共 API。 |
| R2 Standards 7：alias/长度 | 采纳 `tuple[WorkerWarning, ...]`，不再手写同一 Literal。保留 max_length=2 当前协议上界；未来扩枚举仍须显式审阅数量限制，不能按 Literal 长度自动扩大。 | 新协议两个负例断言 too_long/literal_error；成功回包往返保留两个警告。 |
| R2 Standards 7：SDK 警告覆盖 | 采纳。真实 SDK 数据/选项、真实 mapping，替换外部 DocumentConverter 与 backend 页信号，不解析 PDF 或加载模型。 | 四节点逐一覆盖两警告、同时缺失和均不缺失，断言精确 warnings 和 WorkerResponse 往返；只证明边界映射。 |
| R2 Standards 7：manifest 字段 | 拒绝把 ExtractionManifest.warnings 收紧为 WorkerWarning。它承载兼容历史 parser 警告，CanonicalParser 不只来自当前 worker。 | 旧 manifest 字节兼容测试继续通过；保留 tuple[str, ...]，不重写旧制品或 Frozen Schema。 |
| R2 Standards 8：内联 helper | 拒绝。`_set_read_facts` 真实调用于 ReadFacts 构造及 `_replay_facts` 的历史 replay 两处；报告“一次调用”的前提不成立，内联会复制身份/语言验证。 | stage_inputs/service.py 原字节未改；Read 输入构建与历史恢复继续经此逻辑。 |
| R2 Standards 8：默认质量 | 采纳。缺提取时直接 QualityFact()，无需为默认值构造无关 PaperProjection。 | 原缺前置与质量拒绝测试；默认仍是原 absent 值。 |
| R2 Standards 8：私有成员命名 | 拒绝为命名扩大公开 API。acceptance/validation 是 ReadTasks 同包内部实现，_owned 保护 token/lease，_now 校验时钟，_prepare 重建历史上下文；消费者未跨出该服务边界。拆回类或公开重命名均增加无需求改动。 | 所有权、租约、接收、历史回放等公共 seam 组合；Python 下划线仍是内部约定，不声称语言级访问控制。 |
| R2 Spec 1 | 范围排除；用户明确忽略补充性文档提交。原门禁身份不可外推的事实保留，本轮不回填历史 #165 JSON 或覆盖旧结论。 | 原材料与历史 JSON 原字节检查，scope 另审计本轮增量；未运行完整门禁/live。 |

## 新增覆盖与实测

新增 D1 模块独立未绑定，不扩展旧 A9 或任何历史 required 分母。人工预期先定为
`2 + 11 + 4 + 9 + 8 = 34`，再 collect 核对；SDK 模块只在 extra+dev 执行，基础环境
不以跳过替代通过。

| 模块 | 人工预期节点 | 行为 |
| --- | ---: | --- |
| tests/test_body_review_remediation.py | 2 | parser 返回前拒绝的结算、发布拒绝的已有峰值 |
| tests/test_docling_preflight_review.py | 11 | 八原因、未知拒绝、worker 两协议负例 |
| tests/test_docling_sdk_review_warnings.py | 4 | 真实 SDK 数据映射的两类警告及对照 |
| tests/test_fulltext_review_guidance.py | 9 | 受控正文错误的安全下一步 |
| tests/test_read_review_remediation.py | 8 | 三警告投影、九键领取形状与四种损坏 |

实测记录与材料差异见下表；开发期检查均不是完整离线门禁。

| 实际运行 | 结果 | 耗时/计数口径 |
| --- | --- | --- |
| Body parser FulltextError 回归（修前） | 1 failed，UnboundLocalError | 0.59s；真实公共提取 seam |
| 同回归 + 原 Body 提取模块（修后第一轮） | 22 passed | 6.74s；当时新增 Body 回归一节点 |
| FulltextError 指引（修前） | 9 failed，缺下一步文本 | 0.13s |
| FulltextError 指引（修后） | 9 passed | 0.11s |
| Read 新警告/领取依据模块 | 8 passed | 10.26s |
| SDK 新边界模块 | 4 passed，零 skip | 2.02s；最初测试材料缺合成输入文件的四个 FileNotFoundError 已修复，不计作产品 RED |
| 新五个 D1 模块 collect-only | 34 collected，匹配人工 34 | 0.46s；收集不等于执行 |
| 相关 Body/fulltext/metadata/Read tasks/query/execution/Docling 组合 | 321 passed，零 skip | 40 模块，412.91s；含新 34 节点与真实无 extra 冷进程恢复 |
| 全仓 Ruff | 通过 | `ruff check .`；初轮格式问题已修复 |
| 全仓格式 | 通过 | `ruff format --check .`，1211 files already formatted |
| 全仓 mypy | 通过 | 877 source files |

环境为既有磁盘 `.venv` CPython 3.14.4、extra+dev；测试通过
`UV_CACHE_DIR=.scratch/issue-150/152-cache uv run --offline --locked --extra docling pytest ...`
运行，临时根在 `/tmp`，无网络。组合的精确 glob 选择为
`tests/test_body*.py tests/test_fulltext*.py tests/test_feed_metadata*.py tests/test_read_tasks*.py
tests/test_read_queries.py tests/test_read_query*.py tests/test_read_execution*.py
tests/test_read_review_remediation.py tests/test_docling_executor*.py tests/test_docling_mapping.py
tests/test_docling_manifest_compatibility.py tests/test_docling_cold_import.py
tests/test_docling_preflight_review.py tests/test_docling_sdk_review_warnings.py`。
无 extra 冷进程显式使用已有 `.scratch/venvs/merge163/bin/python`，没有复制或新建解释器。

包初始化/服务导入链变化另运行 `UV_NO_SYNC=1 ./scripts/check-compatibility cli`：
8 模块、59 passed、零 skip，pytest 69.30s，入口退出 0，总耗时 69.77s（含 uv）。
UV_NO_SYNC 只避免把已锁定 extra+dev 环境同步掉；实际检查仍使用入口规定的
`uv run --offline --locked`，无下载或环境复制。此兼容检查不发布正式验收结论。

## 材料身份与固定不变量

本轮增量清单仅记录实际改动的 source、新增测试与现状 Contract。两个原审查报告纳入提交，
其前缀分别与树外 3001/18614 原字节一致；原文 SHA-256 分别为
`458a68b2abc1b13ba23d9e19792ffa5860e76b93a041ca584015d0742631195a` 与
`7803a6a569e72551860b33fa3e46aa3c279a7ce76f4078f694ecfedee87523e0`。
本台账不追改已发布材料清单；报告附录、台账本身由本轮提交与完整工作树身份保护。

| 本轮实际材料 | 原 SHA-256（基线） | 新 SHA-256 |
| --- | --- | --- |
| docs/contracts/body-persistence.md | ac632480ea4cf6fc4c9d00c3dd7dbb955d9088c58b915d366857c8cc5bbeeeee | f7bad627500d2aa9842da706fec4dbf4632c8b6ad899e9eb208cf945365f54bb |
| docs/contracts/docling-execution.md | 68070172090126d23bb5bc4aad3ec8a9548707be325d41009a1a44714958ac8c | b7aadf27ca597de8dddaef1756bf15aebcf40cb79c09e4f8457d8d4ed9bea592 |
| docs/contracts/fulltext-extraction.md | fbf28da2ded4581cb59e00fcc27d51ea6ccfcb99c3ecf5dabd9936c3f196f9a4 | 87eedc11bec11796e92eca1fb63396d9bc78cc7e9c054bd49f98e162d27a8f4f |
| docs/contracts/read-tasks.md | 1dd3dc28e6d8d8998dad309459b449bfc0e67b1188543e9b8428a268fc0ec5b4 | a7c399487b9f95e7906ad384b512b404a27c12d0baa0a33ecc83b063372c7841 |
| docs/contracts/read-validation.md | e4d93cb7bdd3732773c21d0c2f7720feaa1d410c3c85ce732d6a25eeb2f5c330 | 7b63f2db0bcd13d78470b9e5894f8832afbdc8fc554d5a6185a423adb7cd41ae |
| src/paper_radar/body/extraction.py | 872e2741a6bd4b17e121e496b303cc17a89301933c8d64a8f5ec2582b6031c19 | 9c03e2307fd8283d3bfe645481f5eb145d0565651dedf7f69d1ff97c28028790 |
| src/paper_radar/body/pdf.py | 新增 | 5cd366714412f8478aa83526ea26a39c2a0429e961a1798120a3a10d79eedd51 |
| src/paper_radar/body/read_basis.py | 新增 | c2040582c183427778102a17eb6f723f7a7126d1ca56bd8d02afbe874a50fa1c |
| src/paper_radar/body/service.py | a390dd1cdbd90e78cfb12be3d1faa481a3c41d65abcb9a134283c29df059879b | 5b56384911bfab069529a0e9db01b16adf695c22e74803bf042988345904c506 |
| src/paper_radar/body/validation.py | 45f100d8dd4674eaab4fe8ae85af1652001383245e945ff31553c8df6a39ff87 | 896d247030552e1ad031ee6332eeaf4e6cb3fa89cdf053b69fac37b84504d0f0 |
| src/paper_radar/docling_execution/models.py | 3e35adfae214ac88d1031b02e4bfad809dbbd76edc8936e55ccf69143268832e | a3c24765ff05c45aba748ff6ecf281800b18648d1b9c9eacb86193c68261164c |
| src/paper_radar/docling_executor.py | fe88aff0174369fe948d3a5d75d43272b1696ede3714c487ab859500766d1f13 | da6ab68764738b3d078250aa86758fc378d4ef3b31330b302a95d366be2549bc |
| src/paper_radar/feed_metadata/service.py | a27cbc101dd484c70887f96f797e290e6c94f33075a0bf37dd12aae4f3243412 | 7c5ff36998f6f34f46c1ea9ad2fbdc9dc44691929e3b2ee26d2a19cffe8546a8 |
| src/paper_radar/fulltext/models.py | f4233cf0f4b7459c0ece5ca936b786ad016695edd2b4199a622dcdb76cfad59b | 1e0ca1ccf277e64859b64fd0d485c461c708f4d6f0c57e41272cf003f7819051 |
| src/paper_radar/read_queries/service.py | 3bbf76319d4ee8c927940d225d3d455250d518b6a2672484b87752f4159d00c6 | a21008092a44921489cc87c47427c78cd2882a33cc15fa0dd46e2c87b386289a |
| src/paper_radar/read_tasks/preconditions.py | bf1d39eb48826c5e7ceb8cb6f38de02bcada28af68199e2e003cfd94a050b0c3 | 4e0a01810cd73f821b862191d21070896c80a63a144e46a508289e8eee985b77 |
| src/paper_radar/read_tasks/service.py | 35974a7b15e65ca583c9b9219bc957b5f98b66298bb75e4ad8503f93c508f4f7 | 85170d83ff2c6c275c67f68b3ac6132b2bc84aa01d9360b4a0b95606041bff86 |
| src/paper_radar/read_tasks/validation.py | d3a53d6c70f4570f0d821c8670e10a6ab1da098fd6e134285a30820251c86b82 | 2098406e158728b0169692371db3097b546972d53188599c83abd9069a0dbdbb |
| tests/test_body_review_remediation.py | 新增 | 82d8cf15c85758c63ea00bab792c6aa56eb8ab6c1a272f621cbc292bcbdd2c29 |
| tests/test_docling_preflight_review.py | 新增 | 209a7dc40cdb7015dca79cbca37f827809d314cb3fb342bed53a0d3cf4783ebd |
| tests/test_docling_sdk_review_warnings.py | 新增 | 58584c6bac9a1fc3deae3796375b4e01406a188cfb909a16b22048b2c44b6c41 |
| tests/test_fulltext_review_guidance.py | 新增 | 2e78f1745f837130125d503b2a14e3aade0d3045b81b670c6732c63ad4bcf0ef |
| tests/test_read_review_remediation.py | 新增 | 99137db21620da017b57722796357e434804df66a3e34023669b21c08471ca99 |

相对基线 `6e15d1c`、本地目标 `integration/body-155` 的只读 scope 审计（含
`--collect`）退出 0：issues/affected_groups/baseline_issues/登记 changes 均为空。
登记内 285 模块收集 5281 节点，零 collection skip/deselect；`execution=not_run` 明确
表示只收集，不是运行这些节点。A9 的十五模块人工分母仍为 560，逐模块收集一致。
本轮 13 source、5 新测试和 5 现状 Contract 共 23 项增量均不改变既有组登记；
没有哈希重绑、S3 豁免或旧身份确认复用，11 scope 与中央登记原字节保持。
首次收集因实施者同时更新本台账而以 baseline_identity_changed 安全拒绝，未进入收集，
该次退出 1 不计为通过；台账固定后重新审计，最终身份留树外报告。

另按原精确清单逐项核对 72 个冻结成员：A9 十个 v1 源码 + 十五测试、41 个既有
fixture 整体、6 个审计自身材料均 SHA 原样。41 是历史 fixture 整体，不能误当作
A9 REQUIRED_FIXTURE_FILES（该集合是 26）。全部 25 migration 与 A9 格式/规则/能力、
旧 required 分母不变；已发布 #164 两份报告、#165 closure 与 133 项清单 JSON 对基线
原字节一致。旧正式门禁 14 份 ignored JSON 按原磁盘 inventory 逐 SHA/字节数核对一致，
不把 git ls-files 的空集合当作验证。旧清单中引用源码的历史哈希仍描述原树；本轮修复后
的源码身份只由本增量表与当前提交证明，旧门禁适用性不向新树外推。

## 未验证与承接

本轮无联网、真实 PDF、真实模型推理、用户私有库或 SDK smoke；SDK 测试只用合成对象
与外部转换替身。没有运行 `scripts/check-offline`，没有新正式回执。
四刊质量、实际 Docling 保真与资源阈值、Pi 现场、B 产品接线、G 长文与 H 显著报告
继续按原路线图承接。本轮未改变依赖、模块完成状态或承接责任，路线图不变。
