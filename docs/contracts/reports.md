# 实验报告

## 用途与范围

`experiment report render/rebuild/verify` 把实验库的既有事实投影为中文私有 Markdown。
日报与单篇共用最终 `report_runs` / `report_entries`；scope 固定 `experiment`，
不提供普通生产报告候选、自动调度或普通复核入口。

## 规则

### 固定输入与身份

`render --root ROOT --date YYYY-MM-DD --timezone IANA [--snapshot SNAPSHOT]`
创建日报；`--analysis-id ANALYSIS` 创建成功分析的单篇修订。快照只用于冻结披露配置；
未提供时配置显示 unknown，不猜测 cwd、当前配置或模型档位。
日报按根身份及日期唯一；第一次固定的时区保持不变。单篇按 analysis 唯一，
新 analysis 取得新 UUID；同一 analysis 可同时作为日报和单篇成员。

run 保存种类、实验范围、日期、时区、renderer=1、固定时点、完整投影 JSON、
输入 fingerprint、预期字节哈希、受控相对路径及 prepared/published 状态。
entry 保存 paper/version/revision、primary 种类与引用、analysis、supporting Screening
成功及制品引用、固定 N1–N5、栏位、顺序和 first-publication key。
授权、决定、Screening 输出、Read 权威投影、历史 PDF/正文三元组、警告/丢弃规则、
准入片段及运行摘要在准备事务提交前全部冻结；报告不接收模型输出。

日报最多五项，其中成功分析最多三项。分析按完成时间 FIFO；非分析槽位由待决定
value 成功与缺 PDF／终态解析受阻事实共同按首次可发布时间 FIFO 竞争，
同刻按稳定 paper ID 破同；同类型、同事实只预留一个 daily 首次发布键。
已接受筛选不独立占 pending 槽；analysis 的 supporting Screening 不新增槽位。
方法、数据、代码/工具归可转化栏，其余归认知栏，不给跨栏总排名。

同日日报固定后，重跑只复用原 run。当天已发布空/失败日报后成功的分析可生成
单篇，等待次日日报；新事实不改写原成员。prepared run 预留首次发布键，
中断后按原日期继续，不通过另一天重选原成员。

非分析成员另冻结 Body 决定范围 decision_scope：through_sequence、boundary_decision_id
与序号/ID/结果元数据的 decisions_sha256。完整接受关联和来源在事务外预验；
报告固定写事务只通过 Body 的同 Connection 元数据端口重核范围，变化以 facts_changed
回滚并要求显式重规划。Body 不读取实验关联；report 以已预验的 decision_id 映射 supporting value 成功。
历史 pending 只排除冻结范围内已接受的同一成功，后来追加的决定即使墙钟回退或相同也不进入原范围。
日期/时间只作披露，不作为决定 as-of 次序。缺少范围的旧开发树非分析输入受控拒绝，不按墙钟回填；
此范围属于本票首次发布的固定输入格式。

### 发布与核验

发布顺序是同一事务固定 run/entries → 同目录独占临时文件 → 核对成员、引用、
evidence 与受控路径 → flush/fsync → atomic replace → 同步目录 → 标记 published。
run 输入及 entries 有追加保护，run 只允许 prepared 到 published 的状态更新。
路径仅为 `views/YYYY-MM-DD/UUID.md`，不用题名。题名的 Markdown 元字符显示为
字符实体；Read/Screening/evidence 位于不可逃逸的 JSON 代码围栏中。
报告仅产生固定成员的内部锚点链接，内容中的链接或文件路径不成为可执行导航。

replace 已完成、published 尚未提交时，重跑仍使用原输入、成员与首次发布键。
`rebuild REPORT --root ROOT` 只原子重建原投影，不更新库、任务、预算或日志；
`verify REPORT --root ROOT` 只读核对预期字节、完整成员及权威来源闭包。
缺文件、坏字节、缺成员、不安全路径及引用损坏均拒绝，不猜测当前 PDF 补旧依据。

每次 render/rebuild/verify 和获准历史查询都实际调用共享 visibility，B 的隐藏集合为空。
原题名保持来源文本；Screening 明示实验非决定支撑；授权者 owner 与代执行者 agent
分列；实际存在代执行记录时注明依预先选样授权代执行，不声称所有者看过模型输出。
尚无该记录的 pending 条目明确显示“尚无代执行接受决定（保留选样授权）”。
Read 只经 `analysis_payload` / ReadQueries 消费已接收输出、历史 attempt 依据和 evidence；
显著披露受限内容未核对、各类 discard 标记与计数。evidence 保存原页码、bbox、
charspan；没有稳定章节定位时显示 unknown。健康运行摘要只显示计数，异常展开受控告警；
空日报分别显示无新结果或因故障没有结果。

准入披露复用 doctor 的共享片段及分项行，分别展示 Screening/Read 格，
披露所有者豁免、本次 assessment=not_assessed、未读取的 original_state=unknown、
historical_state_read=false、原因、时点及下一动作，不计论文容量。
报告发布只读取业务库豁免/显式快照，不探测宿主、认证、安装或受保护 Live 链；
未作观察的分项如实为 not_assessed，未读取的历史状态不写成 absent 或原 not_assessed，
received/active/revoked 也保持 unknown，不合成历史 claim 或因此产生 verified。重建使用冻结片段，
不重新查询当前 doctor 或所有者选择。

### 恢复与消费接缝

公共 `Reports(database, data_root, output_dir).rebuild/verify(report_id)` 接受显式位置，
标准恢复的 `database.sqlite3` 与根级 blobs 无需改名或套用 ExperimentRoot。
恢复输出目录独立；重建不写 SQLite、attempt、预算、历史或日志。
`Reports.history()` 返回经闭包校验的不可变 `ReportInput` 历史，entry 显式保留
paper/version/revision、primary/supporting 与原授权依据，供后续暴露清单消费。
它是获准私有内容边界，不能用于默认安全诊断。

`Reports.validate_all` 经 `experiment.validation.validate_all` 唯一接入备份闭包。
备份保存冻结输入及所有源成员，不复制可重建 Markdown；标准恢复可独立重建相同字节。

## 错误与拒绝

成功退出 0；参数/受控业务拒绝/执行失败退出 2；中断退出 130。
受控原因包括 invalid_arguments、unknown_command、invalid_date_timezone、
invalid_clock、facts_changed、ordinary_consumption_denied、
analysis_not_found、analysis_scope_invalid、report_not_found、visibility_denied、
registration_invalid、unsafe_path、file_missing、content_corrupt。
错误只含受控原因与下一步，不回显题名、摘要、模型响应、路径或自由文本。
render 显式注入所选根 FileSink；安全 JSON 只含身份、固定成员与摘要哈希。
获准的私有 Markdown 保留必要内容，日志字段闭集保持不变。

## 不提供／不证明

不提供普通生产日报/复核、周报、生产队列或完整运行摘要；承接：[H](../roadmap.md#module-h)。
不证明真实论文、模型质量、现场脱网隔离或 NAS；B 现场回放与[I](../roadmap.md#module-i)
各自验收。恢复 API 的 Python 禁 I/O 守卫不代表操作系统隔离证明。

## 相关

依据：[规格 §4.11/§5.6](../../intent/draft.md#411-报告与复核)、
[#185](https://github.com/MeteoBoy4/PaperRadar/issues/185)、
[发布后固定裁决](https://github.com/MeteoBoy4/PaperRadar/issues/185#issuecomment-6848385568)、
[ADR-0018](../adr/0018-keep-v1-markdown-reports-read-only.md)。
[B 组合](stage-b-workflow.md)、[doctor](doctor.md)、[Read 权威消费](read-validation.md)、
[备份恢复](backup-restore.md)。
