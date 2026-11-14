# B 实验工作流

## 用途与范围

`paper-radar experiment` 在必填的显式 `--root` 中组合 B 实验动作。
当前提供 `init`、`feed-fetch`、`candidates`、`select/selection`、`egress-authorize/status/check` 和静态
`preflight`、显式无 prompt 映射探测 `probe-models` 与两阶段 `screen`、`accept`、`attach-pdf`、
`extract` 及 `layout-materials/layout-review`；不推断 cwd 或父目录中的根。
实验用途、执行来源和质量资格分别判断；组件规则仍由各自 Contract 定义。

## 规则

### 根与布局

`paper_radar.experiment.ExperimentRoot(root)` 是唯一布局入口：

| 属性／内容 | 相对显式根的位置 |
| --- | --- |
| `database` | `paper-radar.sqlite3` |
| `data_root` | `data/`，供既有 `ArtifactStore` 与组件服务使用 |
| 内容制品 | `data/blobs/sha256/`，沿用[制品契约](artifact-store.md) |
| 制品发布临时成员 | `data/tmp/`，不是模型 attempt 运行目录 |
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

Pi prepare 的 data/config 根使用这里的实际值；material/install 仍显式传入，
可分别选择根内并列的 `pi-materials/` 与 `pi-install/`。四根两两不得包含，
供给安全检查保持生效；prepare/verify/activate、模型探测与任务消费使用同一数据库
和实际 data_root。数据库保持根内原位置，预算和用途身份不因制品子目录变化重建。

旧顶层 `blobs/` 或 `tmp/` 非空时，`init` 和 `require()` 均以 `legacy_layout`
受控拒绝，保留原库、原材料和目录，不忽略旧制品、不自动搬迁。仅有用途登记的空库
可经 `init` 创建 `data/`，数据库不移动、root_id 不重登记；空的旧目录可保留。

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

### 外发授权与只读复核

`egress-authorize --root ROOT --snapshot REF --stage boundary --stage value --stage read
--reason TEXT` 从显式历史快照取得每个所列阶段的精确 provider/model，并追加所有者决定。
默认启用，`--disabled` 追加撤销；每次决定只覆盖所列阶段，不继承未列阶段。
Screening 的数据类别为 `profile/title_abstract`，Read 另含 `legal_body`。
理由必填且只保存在私有业务库，终端、错误与日志不回显正文。
授权者固定为 owner，是本地审计说明，不构成身份认证或密码学签名。

授权复用既有 `config_versions`，独立 kind/name 为 `experiment_egress/stage-b-egress`，
不混入[所有者豁免](pi-execution.md)的记录。格式 `stage-b-egress-v1` 记录根身份、
规范绝对位置、阶段/模型/类别范围、版本、原始字节 SHA-256、前版哈希与时间。
写入持 `BEGIN IMMEDIATE`，验证完整链后只追加；没有记录表示未授权，损坏、未知格式、
哈希不符、版本断链或时间倒退均拒绝，不能降级为缺省。

`egress-status --root ROOT` 只读返回历史链的安全投影：enabled、version、record_sha256
与 grants。恢复到新位置仍可验证并回查历史字节；enabled 只描述记录，不表示当前根已获执行许可。
`egress-check --root ROOT --snapshot REF --stage STAGE` 按本次选择只读核对执行适用性。
原根的授权不能延伸到复制/移动根、其他阶段、provider/model 或类别。

公共 `experiment.egress.egress_authorization(database, connection=None)` 验证完整链而
不比较当前位置，供备份/B 聚合验证消费；`selected_grants(snapshot, stages)` 只投影已验证
快照。`require_egress_authorization(root, stage, provider, model, categories, connection=None)`
在缺记录、撤销或范围不符时抛出封闭 `EgressError`；传入当前短事务的 Connection 可在
认证前及领取事务内重读，检查本身不写任务、不占预算。Screening/Read 产品编排负责在
每次新执行、两阶段之间和领取前消费此接口；历史请求回执不表示可继续执行。

### 静态执行预检

`preflight` 必须显式选择 `--root/--snapshot/--credentials-dir/--material-root/
--install-root/--attempt-root/--model-root`。data/config 根取固定实验布局，其余根不猜测。
命令组合 basic、所选配置的 boundary/value/read/extraction readiness、pi-supply、
Screening boundary/value 与 Read 自身模型/adapter/档位的工程检查、docling-runtime、
外发授权、所有者豁免及主机资源。Read 使用自身 `CallSite.READ/Consumer.READ` 准入用途，
不复制 Screening 投影；每个必要项失败均以四态、封闭原因和中文下一步报告。
组件四态与豁免披露沿[doctor](doctor.md)，不将 not_assessed/unknown 提升为 verified。

根约束逐个对象列出：计划 attempt 临时根与 data/config/material/install 四根分别互不包含；
凭据目录分别位于各根之外且互不包含；所选安装根须匹配供给登记实例并沿供给契约验证。
不额外要求四个执行根两两互斥，固定的 config 位于 data 内不因此被拒绝。
静态计划检查不创建 attempt 目录，实际启动仍由[执行资源边界](pi-execution.md)核验。

主机项读取 MemAvailable、所选冻结模型部署/文件哈希和临时快照磁盘余量、当前用户
cgroup v2 的 memory 写权限及 memory.peak。模型快照所需容量等于所选文件实际总字节，
不借用 Pi 安装或开发环境的磁盘门槛。memory.peak 不可读显示 not_assessed/unknown，
不代替 worker ru_maxrss；cgroup 能力通过不证明提取时 ≤8 GiB/swap=0 已实施。
MemAvailable 是非必需披露项：成功采集为 passed/host_memory_observed 并显示实测字节，
仅表示读到数值，不判断容量足够；不可读或格式异常为 not_assessed/host_memory_unknown，
明确 unknown。两者均不单独影响退出码，不新增可用内存硬下限，也不因低于 8 GiB 阻断。
这是[所有者“仅披露”裁决](https://github.com/MeteoBoy4/PaperRadar/issues/185#issuecomment-6869017674)
的范围；cgroup、模型临时快照磁盘、隔离和授权等必要闸门仍独立决定结果。

预检不建库、日志、任务或 attempt，不占预算，不调用可能刷新认证的 `prepare_launch`，
不读取 auth.json 内容，不启动 Pi/Docling、不联网。模型映射明确为
`model_mapping_not_probed/not_assessed`；无 prompt 的 RPC 探测是另一个执行边界。
成功只表示本次静态必要项通过，不授予业务执行、逐文档质量或模型能力资格。

### 显式无 prompt 映射探测

`probe-models --root ROOT --snapshot REF --credentials-dir AUTH --material-root MATERIAL
--install-root INSTALL` 默认独立探测 screening 与 reading；`--slot` 可只选一槽。
认证前核对实验根与精确外发范围（screening 为 boundary/value，reading 为 read），
再消费共享所有者豁免或严格证据与不可豁免隔离。它不消费选样、不登记业务任务或预算。
认证可能刷新并写回凭据，输出仅为本次映射状态；生命周期、副作用、时限、错误与证明边界
唯一规则见 [Pi 执行探测](pi-execution.md#无-prompt-模型映射探测)。

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

### 选样接受授权与换样

`select --root ROOT --view-id VIEW --position N --request-id REQUEST --reason TEXT
--actor owner|agent` 按该视图固定原位次记录所有者授权；也可用 `--doi DOI` 替代
`--position`。DOI 经统一规范化后必须恰好匹配该检查中的一个成员，不能查询全库并选取
其他检查的论文；没有匹配或同 DOI 多成员都受控拒绝。

授权者固定为 owner，录入者为 owner 或 agent。两者都是本地审计说明，不是身份认证、
签名或用户已阅读模型结果的证明。所有者原文选样理由、换样理由只保存在私有业务事实中；
终端安全投影、错误和日志不输出这些文字。选样表达对冻结论文／版本的接受授权，
不创建 `accepted` 决定、Screening/Read 任务，不调用模型；实际代记 accepted 由下述
独立显式命令引用该授权与所需真实成功，遵守 [ADR-0069](../adr/0069-treat-stage-b-selection-as-owner-acceptance.md)。

`experiment_selections` 只追加保存根身份、视图、请求检查／成员来源检查、原位次、发现、
冻结 Paper／版本／修订、DOI、元数据请求、原文理由、授权者、录入者、request_id 与 UTC
时间。规范 JSON 的 SHA-256 为 selection_id；SQL 引用列与完整载荷相互校验。
数据库触发器仅接受衔接当前末项的新序号插入，并拒绝 UPDATE/DELETE 及 REPLACE 覆写。根身份是可恢复的 root_id，不依赖原绝对路径。

写事务之前实际调用共享 visibility 的 SET_DECISION 普通动作许可；当前没有隐藏事实
生产者时仍传空集合。写入持 `BEGIN IMMEDIATE`，在同一短事务内重读用途、完整授权链、
当前选择、当前获选修订、当前元数据请求及全部路线、语言来源和强身份冲突。
候选必须 metadata_ready、主摘要非截断、当前版本、语言 resolved、无阻断冲突；任一
所见依据变化（包括同版本新增字段修订）返回 `basis_changed`，仅输出受控差异类别：
`version_changed/revision_changed/metadata_changed/language_changed/conflict_changed`。
所有者须查看显式生成的新视图再选样；不默默接受后来补摘要或变化的版本。

同 request、同完整内容返回原记录并标记 `replayed=true`；异内容报 `request_conflict`。
回执重放不重新选择样本、不改变当前有效选择，也不构成继续执行许可。
任何后续新执行都须在领取短事务内重读当前选择和当前完整资格；历史授权不会绕过新阻断。

当前有效选择是完整链的唯一末项。已有选择时，新 request 必须提供
`--replaces CURRENT_SELECTION_ID --replacement-reason TEXT`；缺少引用拒绝，引用过期
返回 `selection_changed`。换样追加指向被取代者的事实，不更新旧行。并发换样在写锁内
串行复核，至多一个请求可以取代同一当前选择。A→B→A 产生三个事实；旧授权、原因、
发现和暴露依据继续保留，不因换下样本而删除，也不重置任务预算。

`selection --root ROOT` 只读返回 `current_selection_id` 与全链安全历史，不创建日志。
公共 `Selections(database, data_root).history()` 返回完整私有事实；
`history_in_connection/current_in_connection(connection)` 支持下游在自己短事务内读取
授权历史／当前授权。当前记录查询不授予执行资格，调用者仍须联合校验版本、外发授权与
阶段资格。

### 显式两阶段 Screening

`screen --root ROOT --selection-id SELECTION --snapshot REF --credentials-dir DIR
--material-root DIR --install-root DIR` 对一个明确授权运行 boundary → value。
默认 boundary 是 manual 请求，request_id 由 B selection 身份、快照身份和阶段确定性派生。
`register_with_status` 原子区分新登记与精确重放；重放只返回登记时的原回执，不认证、
不领取、不补后来的成功，也不继续 value。历史选样被换下后仍可回查这种原回执。

每次新执行在认证前核对当前有效选择、同 Paper 的冻结 version/revision、当前最低元数据
与非截断完整主摘要、外发授权；Pi 仍执行所有者豁免或严格证据检查及不可豁免的运行
隔离。完整不可变选样链与候选制品在事务外预验，短事务用
`Selections.require_current_in_connection(connection, validated_record)` 复核当前行、
根和预验记录的规范字节，不在锁内读取候选文件。新登记、两阶段之间及每次领取短事务
重新读取选择、版本、元数据与适用外发范围；已通过 boundary 不直接放行 value。
领取守卫拒绝回滚、不新增 attempt/失败、不占预算；外部认证、RPC 和制品 I/O 在事务外。
已领取的在途 attempt 沿原租约接收，不因换样或撤销授权删除历史、退款或改写 A7 独立阶段事实。

每阶段一次命令最多驱动当前代际剩余的两次领取，第二次只使用 A7 的受控修正；成功即停。
boundary 的权威 `pi_rpc` 成功为 out_of_scope 时保留结果，以 3 停止且不登记 value，提示
所有者换样。其他 boundary 成功由 `FeedPipeline.register_value` 登记生产 value，语言从
Feed 派生；`test` 成功拒绝。组件独立阶段与来源规则见[任务](screening-tasks.md)和
[Feed 组合](feed-pipeline.md)。成功不创建建议、决定、Read 或 reuse；
`reuse_feasibility_inferable=false` 也不触发额外任务。

预算的唯一权威仍是 A7：同库、同 `(paper_id, stage, fingerprint)` 预算范围，每任务代际
最多两次领取；重启、换 request/标签或 A→B→A 不重建旧预算。失败终态只由带理由的
显式 retry 追加唯一后继，不自动重试或创建新代际。

`screen ... --receipt-id RECEIPT` 是独立的显式执行模式，只执行该明确回执，不登记
新请求，不自动继续另一阶段，不产生新代际。它重新核对当前选样、冻结版本、快照与
当前代际；value 还须有同预算的 Feed 生产登记、冻结语言和当前非 out_of_scope 的
`pi_rpc` boundary。ready/retryable 可使用剩余预算；running、已成功、非当前回执拒绝，
失败耗尽以 4 拒绝；第二次租约过期但未结算时要求先显式结算，不暗中回收或退款。
前置失败或中断留下的回执从公共任务查询回查，再由此模式显式继续；默认重放不表示继续许可。

`screen ... --continue-value` 与 `--receipt-id` 互斥，显式从当前成功 boundary 登记 value。
它仍重查当前授权、冻结版本、元数据与范围，boundary 必须为当前 pi_rpc 且非 out_of_scope；
新 value 经 `FeedPipeline.register_value_with_status` 生产登记，资格守卫位于 A7 同一写事务，
仅首次新登记执行；精确重复只返回原 value 回执，不认证、不继续 ready/failed 回执。
已有 ready value 用明确的 `--receipt-id` 执行；不会重开 boundary 或以新任意 request 绕过。
没有 boundary 成功时拒绝；out_of_scope 仍以 3 停止。

前置失败/中断后，先从公共任务查询取得明确回执，再按下列连续动作恢复（各占位身份
由原查询给出；配置与路径保持原值）：

```bash
paper-radar experiment screen --root /tmp/my-experiment --selection-id SELECTION \
  --snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials \
  --install-root /tmp/pi --receipt-id BOUNDARY_RECEIPT
paper-radar experiment screen --root /tmp/my-experiment --selection-id SELECTION \
  --snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials \
  --install-root /tmp/pi --continue-value
# 若 value 已登记但认证前中断，继续其原回执：
paper-radar experiment screen --root /tmp/my-experiment --selection-id SELECTION \
  --snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials \
  --install-root /tmp/pi --receipt-id VALUE_RECEIPT
```

### 失败查询、显式恢复与组合追踪

`screening failures --database DATABASE --snapshot SNAPSHOT` 查询全库模型失败队列，
安全 JSON 包含根用途与当前失败引用。当前性、最新代际和 state=failed 唯一规则来自
[Screening 任务](screening-tasks.md#11-显式-retry-与共享查询)，不局限当前选样。
retryable、lease_expired 与旧指纹失败保留在 trace，不进入当前失败列表。

`screening retry PAPER_ID --database DATABASE --snapshot SNAPSHOT --request-id REQUEST
--reason REASON --actor ACTOR [--stage boundary|value]` 调用 A7 产品重试边界，只登记唯一
后继回执，不执行模型；request/reason/actor 非空，歧义拒绝，精确重放返回原回执。
写入前实际调用 visibility；本地 actor/reason 是审计说明，不是身份认证。
`screening reclaim RECEIPT --database DATABASE` 显式结算过期尝试为 outcome_unknown，
不退款、不续租。只读 failures/show/trace 从不调用 reclaim。

第二次租约过期时，下列是连续可复制的动作路径。查询输出提供 PAPER、SNAPSHOT、
原 RECEIPT 和选择身份；SUCCESSOR_RECEIPT 取自 retry 输出；其余执行路径保持原值。

```bash
paper-radar paper trace PAPER --database /tmp/root/paper-radar.sqlite3 \
  --data-root /tmp/root/data --snapshot SNAPSHOT --json
paper-radar screening reclaim RECEIPT --database /tmp/root/paper-radar.sqlite3
paper-radar screening failures --database /tmp/root/paper-radar.sqlite3 --snapshot SNAPSHOT
paper-radar screening retry PAPER --database /tmp/root/paper-radar.sqlite3 \
  --snapshot SNAPSHOT --request-id retry-1 --reason 所有者选择重试 --actor owner
paper-radar experiment screen --root /tmp/root --selection-id SELECTION \
  --snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials \
  --install-root /tmp/pi --receipt-id SUCCESSOR_RECEIPT
# boundary 恢复后尚未登记 value：
paper-radar experiment screen --root /tmp/root --selection-id SELECTION \
  --snapshot SNAPSHOT --credentials-dir /tmp/credentials --material-root /tmp/materials \
  --install-root /tmp/pi --continue-value
```

`paper show/trace` 对 experiment/production/unknown 根中性，每次实际调用 visibility，
包括空隐藏集合。论文事实规则由 [PaperFacts](paper-facts.md#8-当前查询历史重建与只读-cli)定义；
`paper_radar.paper_trace.query_paper_trace(database, data_root, paper_id, snapshot_id=None,
include_agent_content=False)` 返回 `PaperWorkflowTrace`，组合任务、正文与 Read 两轴，供报告消费。
其 `safe_payload()` 保留 root、Feed 来源与语言观察、选样授权安全引用与完整换样链、
Screening 预算/指纹/代际/父链/attempt/租约/安全失败、代执行接受授权关联及双方角色、
PDF 附加/独立确认与冻结样本引用（理由只引用选样），
以及共享 `evaluate_paper(projection)`
概念结果、原因和支持范围；不倾倒内部 projection 或决定载荷。
论文事实与各组件分别读，不承诺跨组件同一 SQLite 快照，允许并发滞后。

显式 `--snapshot` 才核对 Screening 与 Read 输入的当前性；省略时 Read 最小事实保持
mapping_determinable=false，model_failure_queue 以 partial/task_mapping_unknown 披露，
不从历史任务猜当前失败。已装配事实按[共享资格](eligibility-visibility.md)提供
Screening/Read 当前最新代际范围，其他 partial/deferred 含义保持。metadata_ready 仍仅最低元数据；value 的当前成功作为
current_screening_artifact，boundary 单阶段成功不冒充完整建议/决定。
实验 eligible_for_auto_read 始终包含 experiment_no_auto_queue；前置通过不代表名额、
预算或领取许可。PDF 附加、确认与样本提供独立事实；正文与 Read 资格由各自权威和
下述显式组合继续核对，报告由报告组合承接，未装配事实保持 unknown。

默认输出不含 Agent 内容、Profile、Prompt、摘要正文或原始响应。`--show-abstract`
展开获准的论文事实；`--show-agent-content` 必须同时提供快照与 data-root，实际核对
agent_content 许可后，仅由 A7 load_success 展开已接收结构输出，永不转储原响应/完整
SuccessContent。所有只读命令不建日志；retry/reclaim 不调用模型，自动配额为 0。

screening 三命令成功退出 0，受控拒绝/参数错误 2，中断 130；paper 查询沿既有规则成功 0、
受控查询/可见性拒绝 1、参数错误 2。帮助均为中文且不联网、不开库、不建目录。
恢复副本通过显式 database/data-root 查询，支持恢复固定 `database.sqlite3`；失败列表、
retry 父链与安全 trace 保持，第二次过期仍未结算。实验专用执行布局与恢复副本再授权由
后续隔离重放入口承接，不把副本回查误称为可执行许可。

### 依预先选样授权代执行接受

`experiment accept PAPER --root ROOT --selection-id SELECTION --snapshot SNAPSHOT
--request-id REQUEST` 只在有效选样冻结的同论文、同版本及同修订下追加接受。
当前适用 boundary 与 value 均须由 A7 权威 `load_success` 完整回验且来源为 pi_rpc；
boundary 非 out_of_scope。value 预测无需支持 accepted，实验建议不取得决定权。
test 来源、缺成功、out_of_scope、版本/修订变化、选样被取代或 Paper 不匹配均拒绝。

完整授权链、成功内容及 PaperFacts 映射在事务外预验；短 `BEGIN IMMEDIATE` 内经
Selections 的 `require_current_in_connection`、当前获选修订及 A7 的
[成功引用复核](screening-tasks.md)重新核对，不把预读 current 当成锁内事实。
写前和短事务内均实际调用共享 SET_DECISION visibility，空隐藏集合也不跳过。
在同一个调用方 Connection 中经 [Body](body-persistence.md#根决定与来源) 的
`decide_in_connection` 追加 `accepted(direct_manual_decision, user_judgment)`，引用两项
成功，并追加 `experiment_acceptances` 授权→决定关联；任何写入/提交失败全部回滚。
不会先单独提交决定再补关联。该动作不认证、不调用模型、不产生 Read 任务，自动配额 0。

关联记录冻结 request、root_id、选样、Paper/版本/修订、配置快照、Body 决定与两成功 ID、
授权者 owner、代执行者 agent 和 UTC 时间，以规范 JSON SHA-256 寻址。外键及唯一约束
绑定选样/决定/成功；触发器拒绝 UPDATE、DELETE 和 REPLACE 覆写。同一个选样至多代执行一次。
同 request 同内容精确重放原记录并标记 replayed；异内容 `request_conflict`，不同 request
重复消费同一选样为 `already_accepted`。历史重放不重新取得当前执行许可。
Body 同事务写入受控 `delegation_kind=stage_b_preselection` 标记，聚合验证拒绝该标记
下缺关联的决定；普通决定及迁移前历史的标记为空。内部请求可使用 `b-accept-` 前缀，
前缀和自由 actor 字符串均不作为来源权威，普通 Body 请求使用同形字符串仍保持合法。

安全回执及 trace 的 `delegated_acceptances` 显示「依预先选样授权代执行」和授权者、
代执行者及全部关联 ID，不输出所有者理由或模型正文，不声称所有者看过模型输出。
`Acceptances(database, data_root).history()` 查询并回验完整历史；恢复副本不依赖原根路径。
该接受不等于 PDF 归属/合法性确认、六项人工版式核查、正式校准标签或自动消费许可。
命令中文帮助不联网、不开库、不建目录；安全 JSON 写 stdout，错误写 stderr，日志仅写所选根。
退出码成功/精确重放 0，参数、受控前置拒绝、冲突或执行失败 2，中断 130。
失败下一步为回查 selection 与 `paper trace --snapshot`，缺成功时显式继续/retry，
授权或版本变化由所有者重新选样；冲突不可覆盖。

```bash
paper-radar experiment accept PAPER --root /tmp/my-experiment \
  --selection-id SELECTION --snapshot SNAPSHOT --request-id accept-1
```

### B 事实验证与备份闭包

`experiment.validation.validate_all(database, data_root)` 是唯一 B 持久事实聚合，验证全部
候选快照、完整选样链、所有者豁免、外发授权链、代执行接受、PDF 确认与冻结、
有界提取执行、所有者版式核查、Read 关联、固定报告与冻结暴露清单闭包。
接受闭包重验规范关联及哈希、选样和根、原冻结修订/快照、两项成功原字节/审计、
Body 决定原因/actor/引用/时间、受控标记与请求身份，并检查缺关联决定；历史不要求授权仍当前。
[备份](backup-restore.md)的 `verify_contents` 仅调用一次该聚合，损坏统一映射
`registration_invalid`。验证在完整副本中进行，不回读原根；恢复数据库可以使用
`database.sqlite3`，不要求实验 CLI 文件名或原 views 文件。
外发授权在这里验证历史链，不以恢复位置重做当前执行适用性判断。

授权写入失败或事务中断不保留半条事实。恢复后可经显式数据库／数据根接口查询原授权、
理由和换样历史；它不自动续跑，也不证明恢复位置取得了新执行许可。

### PDF 独立确认与样本冻结

`experiment attach-pdf PAPER --root ROOT --selection-id SELECTION --version-id VERSION
--pdf FILE --sha256 SHA256 --owner-confirmed --actor agent --request-id REQUEST`
要求所有者明确确认该文件的论文/版本归属及副本合法性；确认者固定 owner，录入者为
owner/agent，本地角色说明不构成认证或签名。未给独立确认即拒绝，选样/接受授权及
历史 §13.3 PDF 不替代当轮确认。命令不作 DOI 检测、不调用模型或 Docling，自动配额 0。
文件检查复用 [Body](body-persistence.md#pdf-与实验样本) 的签名、最小字节数与 SHA-256。

确认绑定当前选样冻结的 Paper/版本/修订、根、PDF SHA-256、request_id、owner、录入者、
UTC 时间及已验证代执行接受引用。显式版本必须与选样一致且仍是当前修订；选样已更换、
版本/修订改变、接受缺失、哈希或签名不符均拒绝。写前、确认事务和附加事务前均实际调用
共享 SET_DECISION visibility，空隐藏集合也执行检查。

先在独立事务追加 `experiment_pdf_confirmations`；发布 PDF 在短事务外，经权威制品发布
核验原字节哈希。随后在同一 `BEGIN IMMEDIATE` 中重核当前选样/版本，并经 Body 的
Connection 接缝追加 PDF、冻结样本与 `experiment_frozen_samples` 关联。附件通过
`body_pdfs.confirmation_id` 外键绑定确认；附加/样本/关联任一写入或提交失败全部回滚，
已提交确认保留，可按原 request 续办。该独立确认事实不因文件发布失败而删除。
确认规范 JSON 的 SHA-256 作为身份；新增两表触发器拒绝 UPDATE/DELETE/REPLACE 覆写。
旧 Body 附件的确认标记为空，不因请求前缀或 actor 字符串而推断确认。

冻结样本关联选样、接受、确认、Body 附件/样本、当轮 Feed 发现与 source_check_id、
PDF 哈希；原理由保存在选样/Body 私有事实中，安全输出只给 `reason_selection_id`。
同 request 异内容拒绝 `request_conflict`；精确完成重放只返回同附件/样本，不追加。
重放仍须当前选样/版本且最新样本与当前 PDF 完全一致；变化后的文件使用新确认 request。
更换 PDF 保留历史，Body 重新判断当前正文与 Read 资格，Screening 输入指纹/预算不变。
PDF 确认与冻结均不产生六项版式通过、Read 任务或自动消费许可。

公共 `PdfSamples(database, data_root).history()/samples()` 完整核验历史并支持恢复位置；
`require_current_sample(paper_id)` 为正文产品编排提供预验，
`require_current_sample_in_connection(connection, validated_sample)` 在领取事务内只重读
当前选样、冻结修订、当前 PDF 和最新样本关联，不作文件 I/O。历史验证允许仅有确认的
可续办状态；带确认标记的附件必须与冻结关联双向闭合。所有 B 事实仅通过
`experiment.validation.validate_all` 聚合进入备份/恢复，备份服务不另建一套选择器。
trace 的 `pdfs/pdf_confirmations/frozen_samples` 是安全引用，不展示 PDF/理由正文。

中文帮助不联网、不开库、不建目录；stdout 安全 JSON，stderr 受控原因，执行入口日志
只写所选根且不含文件路径/正文。成功/精确重放 0；参数、未确认、无接受、归属/哈希/
样本/版本不符、visibility 或执行失败 2；中断 130。失败时核对所有者确认、selection、
accepted、文件哈希与版本；中断可同 request 续办，内容冲突不能覆盖。

### 显式有界提取

`experiment extract PAPER --root ROOT --snapshot SNAP --model-root MODELS
--timeout-seconds SECONDS --threads THREADS` 对当前冻结样本显式执行一次 Body 提取。
模型根、有限正超时、1–32 线程显式提供；`DoclingRun` 固定显式 `RLIMIT_AS=32 GiB`，
这是虚拟地址空间资源参数，不是物理内存上限。部署清单、commit、全部所选成员哈希及
私有模型快照仍由 [Docling 执行权威](docling-execution.md)核验；不下载模型。
快照前按所选文件实际总大小核对 `tempfile` 实际临时根的可用磁盘，空间不足拒绝，
不使用开发环境或 Pi 的磁盘阈值；复制期间失败仍按既有预检受控拒绝。

入口只读 `/proc/self/cgroup` 与 v2 mountinfo，定位当前进程所属组并要求
`0 < memory.max ≤ 8 GiB`、`memory.swap.max = 0`；无限、缺失、不可读、歧义、越界路径或链接拒绝。
它在根锁前及等待根锁后、领取事务前重新核验；更换所属组拒绝。
主机 `MemAvailable` 仅披露实际字节或 unknown，不设置硬下限，也不解释为容量足够。
资源或模型预检拒绝不建立 attempt 或提取预算；只可能追加所选根安全入口日志。

先通过 `PdfSamples.require_current_sample` 完整预验冻结样本，外部文件读取在事务外；
实际领取短事务经 `require_current_sample_in_connection` 重核当前选样、冻结版本／修订、
当前 PDF 与最新样本关联，预检后换样或修订不能领取。parser 只接收 PDF 与 extraction
语义，不从参数或数据库补题名、DOI、摘要，遵守 [C1](stage-inputs.md#c1-已知未决问题封面识别的论文元数据依赖)。
根锁、同 backend／指纹两次预算、永久失败及失联领取结算全部复用
[Body 权威](body-persistence.md)，不建第二套计数器。每次命令最多转换一次；
失败、无文本层、质量失败、资源耗尽或超时均停止，不截断、不自动换样、不调用 Read。
SIGKILL 未提供可归属 worker 的 OOM 证据时沿原 `executor_error`，不凭组事件猜测。

`experiment_extractions` 与 Body 新领取同事务追加，结构绑定 sample／paper／attempt，
保存已核验组限制与主机披露；`experiment_extraction_peaks` 与完成结算同事务追加，
保存完成后读取的 `memory.peak`。两表禁止 UPDATE/DELETE/REPLACE。
中断导致未观察或峰值不可读时为 unknown，历史丢失领取仍按 Body 结算，不退款。
worker `ru_maxrss` 字节继续属于原 attempt；组峰值标记 `historical_group_peak`，可能含
父进程和同组其他工作，不当作 worker 峰值、不作起止相减或通用 F 阈值。
命中成功／永久失败／耗尽时 `cached=true`，不创建执行记录或新组峰值；
当前主机披露不回写旧转换。`succeeded` 仅说明本次提取已有可用成功，
`automatic_quality` 披露自动门槛，独立的 `quality` 仍由 Body 保留版式核查资格。

trace 安全投影扩展 `extractions`（身份、质量、预算、attempt 与运行审计、worker 峰值）和
`bounded_executions`（冻结样本、限制、主机披露、组历史峰值）；不展开正文或私有模型路径。
新事实只扩唯一 `experiment.validation.validate_all`，随备份、无模型／SDK的恢复保留。
成功或已成功重放退出 0；参数、资源、样本／配置变化、预检或转换失败退出 2；中断 130。
失败须回查 trace，由所有者选择显式再次提取或换样；永久失败与耗尽不能用重跑绕过。

### 版式材料与核查

两个入口均必填 `PAPER --root ROOT --fingerprint FP --reading-sha256 READING
--evidence-map-sha256 MAP`，只消费当前冻结样本与 `Body.current_body` 明确身份，
经 `FulltextArtifacts.load` 校验四角色、规范编码、哈希与自动质量。
同一 PDF 多个成功正文三元组保留 `ambiguous_extractions`，显式参数也不代替选定事实。
只读取已登记 PDF 字节、reading/evidence-map，不读取原附件路径，不运行 Docling、模型或网络。

`experiment layout-materials` 只写 `views/layout-<身份摘要>/`，默认 JSON 返回正文身份及
六个受控相对 HTML 路径。每项配有 PNG 页面／裁切：正文起止及整页；持久阅读顺序的块列表
与编号 bbox 叠加；标题层级与 PDF；全部块页眉页脚去留与上下页边；抽样 evidence 的
页码、bbox、charspan、逐字 orig 并列裁切；公式、表格、不可靠字符的定位及降级标记。
evidence 确定性取首／中／尾及首个受限源；charspan 是持久 source.orig 的半开索引。
无定位、无源父块与零类别显示缺口／未覆盖，生成候选和占位没有 evidence。
源文字经 HTML 转义，只用本地相对图片，不预填判断。原始 PDF 和正文仍属私有材料。
同输入重建字节相同；既有目录不符以 `materials_conflict` 拒绝，不覆盖人工修改。
目录、链接不安全拒绝；页面最多 1000，累计渲染上限 1 亿像素，最长边最多 1600 像素。
PDFium 转换器处理 cropbox、旋转与两种来源原点；页数／几何不符拒绝，不猜坐标。
只延迟导入锁内 `pypdfium2/Pillow`，无 extra 时 `renderer_dependency_missing`，
帮助与纯 evidence 回查不导入渲染依赖。材料不写业务事实或日志，可从持久闭包重建。

`experiment layout-review` 另必填 `--reviewer owner --recorder agent --request-id REQUEST`
及 `--body-boundary/--reading-order/--sections/--headers-footers/--provenance/--restricted-content`
全部六个 `true/false` 原文输入；缺项或非布尔值拒绝，`--note` 可选，仅私有数据库保存。
本地 reviewer/recorder 是审计角色说明，不能认证输入人；没有所有者结论不得代签。
材料生成不构成结论。动作在写事务前检查 visibility，并在同一个短写事务重核
selection／版本／修订／当前 PDF／最新样本及正文身份，随后经 Body 权威追加核查。
`body_layout_reviews.recording_kind=stage_b_owner_review` 与
`experiment_layout_recordings`（review／sample／paper／owner reviewer／agent recorder）
同事务追加；关联失败则整组回滚，旧 Body 核查不回填标记或改写。
passed 等于全部六项通过；自动与人工均通过才由 Body 合成 `experiment_document_gate`。
任一否决永久产生 `failed(layout_review)`；之后通过拒绝为 `layout_conflict`。
记录与资源事实均不独立授予 Read、预算、自动队列或普通生产消费资格。

`LayoutReviews(database, data_root).history(paper_id=None)` 核验结构标记、关联、六项、
正文三元组、请求摘要、PDF 与冻结样本，并返回不含说明的安全历史；支持标准恢复路径。
trace 的公共 `safe_payload().layout_reviews` 保留这份安全投影；原文说明和正文不默认序列化。
新事实只扩唯一 `experiment.validation.validate_all`，备份／无 SDK 冷恢复沿同一闭包验证。
成功／精确重放 0；缺项、冲突、前置、依赖、渲染拒绝或运行失败 2；中断 130。

### 显式 Read 与恢复

`experiment read PAPER --root ROOT --snapshot SNAPSHOT --fingerprint FP
--reading-sha256 READING --evidence-map-sha256 MAP --credentials-dir AUTH
--material-root MATERIAL --install-root INSTALL --request-id REQUEST` 显式执行单篇默认中文 Read。
必需当前有效选样/冻结版本、关联的 accepted 及两项 pi_rpc 成功、当前确认 PDF/冻结样本、
唯一明确当前正文和 Body 的 experiment_document_gate；资源历史本身不授予 Read 资格。
所有者来源仅接受 `LayoutReviews.history` 核验的 `stage_b_owner_review` 结构标记及同样本关联，
旧 actor/request 文字不能提升；旧否决仍永久生效，多正文不能凭参数、配置或时间猜选。
完整文件与上游闭包在业务短事务外核验；认证前、等待根 Read 锁后、准备后及实际领取事务
重读当前事实、外发范围与资格，豁免/严格证据由 ReadExecution 原权威各检查点核对。
资格变化拒绝下一次领取；不取消/退款已领取在途预算。

登记和执行分别复用 [ReadTasks](read-tasks.md) 与 [ReadExecution](read-execution.md)，
label=manual、默认 zh；不创建 manual_read_request/read_requests、不扫描自动队列，自动配额 0。
每调用最多驱动当前代际剩余尝试（≤2），成功即停；完整最坏修正帧超额在任何模型调用前拒绝，
不截正文、不丢章节、不借 Screening 会话。v2 候选接收、末次降级、规则身份和原候选均由
[接收权威](read-validation.md)保存，B 不另写接收或预算规则。

精确 `--request-id` 重放只返回原登记身份，不认证、不补后来状态、不执行。
认证或领取前受阻后，`reading tasks --root ROOT` 查询 ready/running/failed/succeeded、
租约和原 task_id，再用同一明确正文、快照与执行根加 `--task-id TASK` 显式继续，继承原任务的冻结语言和指纹，
不因默认中文另建输入/预算/登记；
`--request-id` 与 `--task-id` 互斥。成功或非最新代际不能继续。恢复链为：

1. `reading tasks --root ROOT` 查询；过期仍保持 running，不进入失败队列。
2. `reading reclaim TASK --root ROOT` 显式追加 outcome_unknown，不退款；尚有尝试则 ready，
   用 `experiment read ... --task-id TASK` 继续。
3. `reading failures --root ROOT --snapshot SNAPSHOT` 枚举全库当前 Read 输入最新 failed 代际，
   不限制当前选样；配置或正文无法映射不猜失败，不隐式回收。
4. `reading retry PAPER --root ROOT --snapshot SNAPSHOT --request-id REQUEST --reason REASON
   --actor OWNER` 由公共 ReadTasks 当前失败查询唯一定位父代，显式追加后继。
   当前失败不唯一以 ambiguous_task 拒绝；可选 `--task-id PARENT` 明确父代，但仍须归属该论文、
   显式快照的当前输入、最新且已结算两次失败。成功、ready、running、过期未结算、非当前或非最新均拒绝；
   Read 的过期必须先显式 reclaim。写事务重新核对失败唯一性/父代、visibility 与当前选样/版本/PDF/正文。
   原失败保留，只返回登记回执，不执行模型；后继用 `experiment read ... --task-id CHILD` 单独执行。
   精确 paper/snapshot/可选task/reason/actor 请求先回原回执，后继推进、选样或当前性变化不新增或执行。

`reading analysis ANALYSIS --root ROOT [--snapshot SNAPSHOT]` 是获准的私有内容查询：
stdout 显著显示“受限内容未核对”、三类丢弃计数/标记、接收规则身份、接受后的结构结果与
逐字 evidence/page/bbox/charspan。原始候选与被丢弃陈述不出此视图；日志、错误、默认 trace
均不展开这些内容。`analysis_payload(database, data_root, analysis_id, snapshot_id=...)` 是相同
公共投影，包含原领取的 PDF 哈希/冻结样本引用及正文三元组，允许标准恢复副本 `database.sqlite3 + blobs`；供报告复用，不重建分析规则。
普通消费拒绝实验分析，恢复不升级资格。trace 的 `read_tasks/read_analyses` 只展示安全任务与
正文/配置两轴，MODEL_FAILURE_QUEUE 从共享 evaluate_paper 组合 Screening/Read 最小事实。
B 的唯一 validate_all 对已关联 B 样本的 Read 领取复核结构化所有者核查引用与三元组；
备份服务不复制此检查，旧无 B 样本事实不补标。

Read 成功/回执重放退出 0，参数/前置/运行拒绝 2，预算耗尽输出安全任务后退出 4，
中断退出 130；reading 查询/reclaim/retry 成功 0、拒绝 2、中断 130。
执行命令注入所选根 FileSink；tasks/failures/analysis 不建日志。帮助均不联网、不开库、不建目录。

### 冻结已暴露清单

`experiment export-exposure --root ROOT` 只在显式实验根登记全历史并集并发布私有 JSON，
执行入口注入所选根 FileSink；不领取任务、不调用模型。选样、失败、换下及后续持久事实
按[暴露导出 Contract](exposure-export.md)冻结；候选展示不计入。其规范 DOI／权威关系格式
供 C 机械排除正式校准，SQL 和历史核验由事实组件各自拥有。
导出 validate_all 仅经本组合的唯一聚合进入备份；恢复保持 root_id 和原字节，不提升结果。

### 最小实验报告

`experiment report render/rebuild/verify` 在实验 views 内发布、重建和核验最终 run/entry 投影；
同日日报固定后晚到分析只生成单篇并等待次日日报。容量、FIFO、首次发布键、私有内容、
历史准入片段及原子发布规则由[报告 Contract](reports.md)唯一维护。
报告每次实际调用共享 visibility，不调用模型、不新增任务/预算、不进入普通候选或复核。
标准恢复消费显式 database/data_root/output_dir，不改 manifest 布局；
report validate_all 经本组合唯一聚合加入备份，现场隔离回放另按 B 闸门验收。

### 日志与命令帮助

`report render` 显式装配所选根 FileSink；rebuild/verify 只读库、不建日志，守卫见
`tests/test_experiment_reports_cli.py`。

`screen` 显式装配 `FileSink(root)` 并传入 Pi/任务服务；独立入口守卫、任务事件与
隐私断言位于 `tests/test_experiment_screen_cli.py`，日志只写所选根。

`select` 显式注入 `FileSink(root)`，仅记录 component=experiment 的入口/结尾事件；
独立 D1 装配守卫见 `tests/test_experiment_selection_cli.py`，`selection` 不建日志。
`accept` 与 `attach-pdf` 同样装配所选根文件汇及入口守卫；成功/重放的入口事件及只读 trace 不追加日志的断言
见 `tests/test_experiment_accept_cli.py` 与 `tests/test_experiment_pdf_cli.py`。原文理由、模型正文和凭据不进入回执或日志。
`extract` 的独立入口／日志／隐私守卫在 `tests/test_experiment_extract_cli.py`；
只读 trace 不追加日志，帮助在冷进程禁止网络与 SQLite 后仍可用。
`layout-review` 显式装配所选根文件汇；独立执行入口／说明隐私守卫在
`tests/test_experiment_layout_cli.py`，`layout-materials` 只生成私有视图、不建日志。
`egress-authorize` 显式注入 `FileSink(root)`，仅记录 component=experiment 的入口/结尾事件；
装配守卫见 `tests/test_stage_b_egress_preflight.py`。授权只读查询与静态预检不建日志。
`feed-fetch` 显式注入 `FileSink(root)`，日志只写所选根的 `logs/`。新执行入口装配
守卫位于独立 D1 模块 `tests/test_experiment_feed_cli.py`；既有审计守卫保持原样。
`init` 与只读候选投影不记录模型／来源执行日志；候选默认终端只输出身份、数量和相对
文件名，完整题名／摘要只进入获准的私有快照与视图。帮助不联网、不开库、不建目录。全部命令的自动配额
恒为 0；只有显式 `screen` 发送业务 prompt 并领取任务；`probe-models` 只进行无 prompt 映射探测。错误只投影封闭原因与白名单字段位置，不展开
异常自由文本、私有路径、HTTP 响应、Prompt、Profile、摘要、正文或凭据。

## 错误与拒绝

| 退出码／原因 | 含义与下一步 |
| --- | --- |
| `0` | 授权写入/只读查询成功，或静态预检必要项均通过；初始化成功，或 Feed 取得并且所有成员最低元数据、非截断主摘要及语言均就绪；空的有效 200 响应也返回 0，仍不推断新增数量 |
| `0 / candidates` | 候选生成或历史重建成功，含受阻成员也返回 0；就绪依据在私有视图中披露 |
| `0 / screen` | 两阶段或明确回执执行成功，或默认请求精确重放原回执 |
| `3 / out_of_scope` | boundary 成功但停止 value；由所有者换样 |
| `4 / budget_exhausted` | 当前代际两次失败已耗尽；查询后由所有者显式 retry |
| `2 / invalid_execution_mode` | `--continue-value` 与 `--receipt-id` 互斥；选择一个明确动作 |
| `2 / frozen_version_changed / metadata_not_ready / receipt_scope_mismatch` | 冻结版本、完整元数据或显式回执范围不符；回查事实后重新选样或使用正确回执 |
| `2 / already_succeeded / not_latest / task_running / lease_unsettled` | 回执不能重新执行；查询当前代际与租约，必要时显式结算，禁止退款或重开预算 |
| `2 / owner_confirmation_required / confirmation_mismatch / acceptance_missing` | 独立确认、冻结归属或接受缺失；由所有者确认正确 PDF，并核对 selection/accepted |
| `2 / invalid_pdf / pdf_unreadable / sample_missing / sample_mismatch` | 文件不可读、签名/体积/哈希不符或当前样本不符；核对合法 PDF，以新 request 确认变更 |
| `2 / cgroup_limit_invalid / cgroup_changed` | 当前组不合规或等待期间变化；在符合 ≤8 GiB、swap=0 的组内显式重跑，不占提取预算 |
| `2 / model_snapshot_space_insufficient / model_deployment_invalid / runtime_selection_invalid` | 核对完整部署、实际快照磁盘、正有限超时与 1–32 线程；不领取尝试 |
| `2 / extraction_failed` | 本次单次转换失败或已有永久失败／预算耗尽；回查 trace，由所有者选择下一步，不调用 Read |
| `2 / owner_conclusions_required / invalid_arguments` | 缺少所有者六项明确布尔输入或角色不符；请按帮助取得所有者结论再原样代录 |
| `2 / body_identity_mismatch / ambiguous_extractions` | 当前正文不符或多个成功身份；核对明确三元组，不能猜最新 |
| `2 / layout_conflict` | 当前指纹已被否决；保留否决，不以之后通过覆盖 |
| `2 / renderer_dependency_missing / pdf_render_failed / pdf_geometry_mismatch / pdf_pages_mismatch / render_limit_exceeded` | 渲染依赖、PDF 几何或有界渲染不满足；核对锁内 extra 与登记材料，禁止重跑解析或猜坐标 |
| `2 / unsafe_material_path / materials_conflict` | 私有视图存在链接或内容不符；保留原材料，核对后显式重建 |
| `2 / invalid_arguments` | 缺必填参数或未知参数；查看对应 `--help` |
| `2 / root_unknown` | 没有 experiment 登记；对独立空根运行 init，既有未知用途库不能改登记 |
| `2 / root_not_experiment` | production 根被拒绝；使用独立实验根 |
| `2 / legacy_layout` | 旧顶层制品或临时目录非空；保留原库与材料，另行安排显式迁移 |
| `2 / unsafe_layout` | 固定位置不安全或不可写；检查布局、链接与权限 |
| `2 / invalid_request / candidate_not_found` | 选样参数、所有者理由或成员不唯一；从固定视图按唯一编号或 DOI 重选 |
| `2 / candidate_not_ready / basis_changed` | 就绪缺项或所见依据已变化；补齐后生成新视图并由所有者重选 |
| `2 / request_conflict / replacement_required / selection_changed` | request 冲突、缺换样引用或引用过期；回查 selection，以新 request 和当前引用显式换样 |
| `2 / visibility_denied` | 普通决定动作受共享规则阻断；先完成专用校准流程 |
| `2 / registration_invalid / invalid_clock` | 授权链损坏或时间无时区；核对可信备份／修正时钟 |
| `2 / registration_corrupt` | 候选种类、载荷、历史成员或固定事实不一致；核对原检查及备份，不能覆盖历史事实 |
| `2 / 组件封闭原因` | 来源受阻、HTTP／条目失败、元数据缺项或版本／请求冲突；按 check_id 回查，未完成请求用原 request_id 重跑，不能覆盖冲突 |
| `2 / egress_not_authorized` | 无记录或已撤销；由所有者显式登记 |
| `2 / egress_history_invalid` | 授权格式、哈希或版本链损坏；修复完整业务历史前保持拒绝 |
| `2 / egress_scope_mismatch / egress_model_mismatch / egress_category_mismatch` | 根、阶段、provider/model 或类别不符；不得沿用其他范围授权 |
| `2 / egress_action_invalid / egress_model_unconfigured / egress_clock_invalid / egress_unavailable` | 动作、时间或存储不可用；核对选择与完整历史后显式重试 |
| `2 / 静态预检原因` | 必要项 missing/invalid/not_assessed；按逐项中文下一步修复，不领取任务 |
| `4 / budget_exhausted` | Read 本代已结算两次失败；查询 reading failures，所有者决定显式 retry |
| `2 / owner_review_required / document_gate_required / task_scope_mismatch` | 核对同样本结构化所有者核查、当前质量、明确任务/正文/语言；不从旧 actor 或裸指纹猜许可 |
| `2 / execution_failed` | 意外执行失败；检查根、数据库与原检查，保留历史后显式重跑 |
| `130 / interrupted` | 操作中断；使用同根及原请求继续，不推断成功或退款 |

业务结果中的失败状态仍完整输出 JSON，再以 2 退出；空 `items`、失败、缺项及异常均不
解释为“无新论文”。组件异常保留封闭 reason；路径只输出入口白名单内字段，否则为
`component`。数据库、制品及元数据的故障原子性沿既有组件契约。

## 不提供／不证明

不提供生产根初始化、生产消费或自动队列。显式 Screening 仅限有效实验选样。实验结果不能提升为生产结果。
离线 HTTP 替身覆盖不证明真实 Feed 字段、entry 稳定性、主摘要完整、语言来源约定或
模型／Docling／现场隔离成立；真实链与后续命令由[路线图 B](../roadmap.md#module-b)承接。

## 相关

- [Feed 组合](feed-pipeline.md)、[元数据](feed-metadata.md)、[正文持久化](body-persistence.md)、[运行日志](runtime-logging.md)。
- [根与 Feed 工程覆盖](../verification/issue-187-experiment-feed.md)、[候选工程覆盖](../verification/issue-188-candidate-views.md)、[授权与预检工程覆盖](../verification/issue-189-egress-preflight.md)、[选样工程覆盖](../verification/issue-190-selection-authorization.md)、[Screening 工程覆盖](../verification/issue-192-screen-command.md)、[失败恢复与追踪工程覆盖](../verification/issue-193-recovery-trace.md)。
- 依据：[#185](https://github.com/MeteoBoy4/PaperRadar/issues/185)、[#187](https://github.com/MeteoBoy4/PaperRadar/issues/187)、[ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
