# B 实验工作流

## 用途与范围

`paper-radar experiment` 在必填的显式 `--root` 中组合 B 实验动作。
当前提供 `init`、`feed-fetch` 和 `candidates`，不推断 cwd 或父目录中的根。
实验用途、执行来源和质量资格分别判断；组件规则仍由各自 Contract 定义。

## 规则

### 根与布局

`paper_radar.experiment.ExperimentRoot(root)` 是唯一布局入口：

| 属性／内容 | 相对显式根的位置 |
| --- | --- |
| `database` | `paper-radar.sqlite3` |
| `data_root` | `.`，供既有 `ArtifactStore` 与组件服务使用 |
| 内容制品 | `blobs/sha256/`，沿用[制品契约](artifact-store.md) |
| 制品发布临时成员 | `tmp/`，不是模型 attempt 运行目录 |
| `config`／`settings` | `config/`／`config/settings.yaml` |
| `logs` | `logs/`，沿用[运行日志](runtime-logging.md) |
| `views` | `views/`，私有只读业务投影的输出位置 |

`init` 显式迁移数据库并经 `BodyService.register_root` 一次性登记 experiment。
新数据库先在根内私有临时目录完成迁移及用途登记，再无覆盖发布；失败重跑不暴露
未登记的半库。初始化锁串行化同根的初始化。既有 experiment 库先核对用途再显式升级，
重放保持原 root_id；production/unknown 库拒绝迁移或改登记。根用途的唯一权威及
禁止改作生产用途的规则见[正文持久化](body-persistence.md)。

`require()` 只读核对固定布局、当前数据库版本和 experiment 用途，不创建根、日志
或数据库。固定业务位置拒绝符号链接及错误文件类型。组件服务仍接受显式数据库与
数据根；后续实验命令消费本类及此守卫，不维护另一套布局常量。

### 显式 Feed 取得

`feed-fetch --root ROOT --request-id REQUEST --contact-email EMAIL` 先核对 experiment
用途及联系邮箱，在库中同值幂等登记共享声明的 JGR 规范端点，再用 `FeedPipeline`
显式选择 `feed_parser_version=2` 与 `abstract_rules_version="audit-abstract-v2"`。
组合版本参数与缺省 v1 兼容规则见[Feed 组合](feed-pipeline.md)。

输出安全 JSON 含检查、来源检查、HTTP 状态、原位次、论文／元数据引用、强冲突、缺项
与语言依据，不展开题名或摘要。HTTP 304 保留组件 `reason=acquired`，另以
`outcome=not_modified` 和 `status_code=304` 如实标识，并以 `source_check_id` 关联
原有效检查及其成员；不会把 304 投影成零候选。历史依据继续沿原请求恢复未完成部分。
相同请求重放不发起新一轮取得；新请求可以产生不同响应并保留历史，不要求第二次必为
304 或相同条目。身份、增量及冲突规则见[Feed 取得](feed-ingestion.md)与
[论文事实](paper-facts.md)。

每个关联 Paper 经数据库 Feed 身份派生并持久保存 v1 语言观察；JGR 的 `false`
仅表示非中文。策略、来源歧义和预算冻结规则见[任务语言依据](screening-tasks.md#feed-原题名语言来源)。
完整摘要只在获准的私有业务读取接口中存在，日志／终端诊断不展开文本。

### 候选事实与私有视图

`candidates --root ROOT --check-id CHECK` 不再次取得来源，只读回放指定检查；
304 沿 `prior_check_id` 找到有效历史成员，编号等于原 `FeedItem.position`，不按 DOI
重排、不截断到日报五项。来源失败拒绝生成，不解释为零候选；有效空检查可以生成空清单。

当前展示输入在同一只读数据库事务内选择，随后以 `candidate_snapshot` 制品的单一
`payload` 持久登记。载荷使用 `paper-radar.candidate-snapshot` domain、整数
`format_version=1` 和 `render_version=1`；封闭字段由
`experiment.candidates.CandidateSnapshot` 及 `CandidateItem` 定义。UTF-8 JSON 键排序、
紧凑分隔、无末尾换行；`view_id` 等于该制品身份，不包含生成时钟或文件路径。
快照固定请求检查、成员来源检查、Feed 制品与 parser 身份，以及每个成员的原 FeedItem、
完整主摘要和来源语言题名、DOI、原文链接、展示版本／修订、当时当前修订、全部获选字段
来源引用、元数据请求与路线、语言来源和强冲突。它不保存完整 Prompt、凭据或原始模型响应。
原文链接优先使用该原始条目的出版者链接；缺失时沿固定字段来源链接。

视图写入 `views/candidates/VIEW_ID.md`，只作为快照投影。每项展示最低元数据、
非截断主摘要、当时当前版本、语言与强冲突标记；受阻时列明原因和下一步。
缺摘要不生成替代文本，疑似截断保留原文并明确阻断；强冲突／解析失败条目仍保留原位次
和可解析的原题名／摘要，不冒充已关联 Paper。JGR 语言 false 只表示非中文。

`candidates --root ROOT --view-id VIEW` 校验种类、规范载荷、固定成员、历史修订、
元数据依据与展示一致性，再重建原字节；不重新选择当前事实。后来补摘要、DOI／版本
依据或成员顺序变化不静默改写旧视图；显式按检查重新生成可以得到新身份，同依据生成
身份和 Markdown 字节稳定。文件通过私有临时文件 fsync 后原子替换，失败不发布半文件，
重跑复用已登记快照。每次实际渲染均调用共享 visibility 的 PAPER_FACTS 许可；当前无
隐藏事实生产者时仍传空集合调用，不将其提升为 Agent 内容展示许可。

公开读取为 `CandidateViews(ExperimentRoot).load(view_id)`；返回上述固定字段。
跨组件只读接缝 `load_candidate_snapshot(database, data_root, view_id)` 不依赖实验库文件名，
`validate_candidate_snapshots(database, data_root)` 校验全部候选快照，供 B 聚合消费。
选样命令须重新核对当前依据与就绪条件，不能仅凭旧快照曾就绪领取任务。
候选快照及完整摘要随既有 artifact blob 闭包备份；views 文件不作为备份事实源。
既有 restore 的 `database.sqlite3` 与实验命令固定布局的公共协调由
[路线图 B](../roadmap.md#module-b)恢复票承接，本接口不修改恢复 manifest。

示例：

```bash
paper-radar experiment candidates --root /tmp/my-experiment --check-id CHECK
paper-radar experiment candidates --root /tmp/my-experiment --view-id VIEW
```

### 日志与命令帮助

`feed-fetch` 显式注入 `FileSink(root)`，日志只写所选根的 `logs/`。新执行入口装配
守卫位于独立 D1 模块 `tests/test_experiment_feed_cli.py`；既有审计守卫保持原样。
`init` 与只读候选投影不记录模型／来源执行日志；候选默认终端只输出身份、数量和相对
文件名，完整题名／摘要只进入获准的私有快照与视图。帮助不联网、不开库、不建目录。全部命令的自动配额
恒为 0，不调用模型、不领取任务。错误只投影封闭原因与白名单字段位置，不展开
异常自由文本、私有路径、HTTP 响应、Prompt、Profile、摘要、正文或凭据。

## 错误与拒绝

| 退出码／原因 | 含义与下一步 |
| --- | --- |
| `0` | 初始化成功，或 Feed 取得并且所有成员最低元数据、非截断主摘要及语言均就绪；空的有效 200 响应也返回 0，仍不推断新增数量 |
| `0 / candidates` | 候选生成或历史重建成功，含受阻成员也返回 0；就绪依据在私有视图中披露 |
| `2 / invalid_arguments` | 缺必填参数或未知参数；查看对应 `--help` |
| `2 / root_unknown` | 没有 experiment 登记；对独立空根运行 init，既有未知用途库不能改登记 |
| `2 / root_not_experiment` | production 根被拒绝；使用独立实验根 |
| `2 / unsafe_layout` | 固定位置不安全或不可写；检查布局、链接与权限 |
| `2 / registration_corrupt` | 候选种类、载荷、历史成员或固定事实不一致；核对原检查及备份，不能覆盖历史事实 |
| `2 / 组件封闭原因` | 来源受阻、HTTP／条目失败、元数据缺项或版本／请求冲突；按 check_id 回查，未完成请求用原 request_id 重跑，不能覆盖冲突 |
| `2 / execution_failed` | 意外执行失败；检查根、数据库与原检查，保留历史后显式重跑 |
| `130 / interrupted` | 操作中断；使用同根及原请求继续，不推断成功或退款 |

业务结果中的失败状态仍完整输出 JSON，再以 2 退出；空 `items`、失败、缺项及异常均不
解释为“无新论文”。组件异常保留封闭 reason；路径只输出入口白名单内字段，否则为
`component`。数据库、制品及元数据的故障原子性沿既有组件契约。

## 不提供／不证明

不提供生产根初始化、生产消费、自动队列、选样或模型执行。实验结果不能提升为生产结果。
离线 HTTP 替身覆盖不证明真实 Feed 字段、entry 稳定性、主摘要完整、语言来源约定或
模型／Docling／现场隔离成立；真实链与后续命令由[路线图 B](../roadmap.md#module-b)承接。

## 相关

- [Feed 组合](feed-pipeline.md)、[元数据](feed-metadata.md)、[正文持久化](body-persistence.md)、[运行日志](runtime-logging.md)。
- [根与 Feed 工程覆盖](../verification/issue-187-experiment-feed.md)、[候选工程覆盖](../verification/issue-188-candidate-views.md)。
- 依据：[#185](https://github.com/MeteoBoy4/PaperRadar/issues/185)、[#187](https://github.com/MeteoBoy4/PaperRadar/issues/187)、[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
