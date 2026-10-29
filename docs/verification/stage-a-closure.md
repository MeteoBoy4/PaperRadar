> 冻结说明：以下正文与表格按文档统一基线 `91e5d02e199f1921ca8afd2b7bdb8f257e6264f3` 原字节保留；当前责任见[路线图](../roadmap.md#承接责任)。

# 阶段 A 收口清单（#111）

2026-10-28 文档基线：`cdf5c1f4f18c19eead77d78cab0e9fafe668ebf1`。
依据 [#111 正文与全部评论](https://github.com/MeteoBoy4/PaperRadar/issues/111)，较新确认优先；
[主方案 §11](../../intent/draft.md#十一九阶段实施与验收) 是统一入口，与 GLOSSARY、ADR、Contract 共同约束。
[固定讨论文件](https://github.com/MeteoBoy4/PaperRadar/blob/212e312/intent/discussions/阶段A剩余工作.md) 仅为历史背景。

**A1–A10 通过不等于完整阶段 A 通过。** 下表的“历史离线已验”仅指 E0 的代码/材料范围，
不声明当前修改树已通过完整门禁；“转移”是责任调整，不是能力通过。原 §11 A 的 15 项实施、
26 项测试和 4 项 DoD 各保留顺序编号 I01–I15、T01–T26、D01–D04，原文列取自上述基线。
本票没有改业务代码、测试数量、Frozen Contract 或历史 JSON，也没有执行 live。

## 证据索引与范围

| 索引 | 可核对依据 | 能证明什么 / 不证明什么 |
| --- | --- | --- |
| E0 | 本机忽略目录 `verification-runs/ab9a89500053400db1c07d40e180a064{,.terminal,.pytest,.a1,.a2,.a2-full,.a3,.a4,.a5,.a6,.a7,.a8,.a9,.a10}.json` | 历史 `a8a8ad87efb65bdf79719b6f093efe2a3c54f138`，clean，5274 passed，required A1–A10 passed、控制方退出 0；本票只读 status 确认历史 passed，当前工作树不匹配。所有历史 stage_a_verified=false 保持。 |
| E1 | [A1 固定 scope](../../scripts/a1_scope.py)、[离线证据 Contract](offline-evidence.md#a1-独立结论) | Schema/原因、工程与已交付 CLI；不是全管线。 |
| E2 | [完整 A2 scope](../../scripts/a2_full_scope.py)、[配置 Contract](../contracts/config-snapshots.md) | 历史配置、投影/基线；不等于真实模型/阶段就绪。 |
| E3 | [A3 scope](../../scripts/a3_scope.py)、[制品](../contracts/artifact-store.md)、[备份恢复](../contracts/backup-restore.md) | 内容身份、原子性与本机恢复；不含 NAS 或未交付业务。 |
| E4 | [A4 台账](a4-requirements.md)、[供给 Contract](../contracts/pi-supply.md) | 固定供给/保护/清理机制；不证明 Pi 1.4.0 生产兼容。 |
| E5 | [A5 scope](../../scripts/a5_scope.py)、[阶段输入](../contracts/stage-inputs.md) | boundary/value/extraction/reuse 配方；无 Read StageInput。 |
| E6 | [A6 台账](a6-requirements.md)、[论文事实](../contracts/paper-facts.md) | 本地身份/来源/映射/历史恢复；无真实 Feed、强冲突材料生产接线。 |
| E7 | [A7 台账](a7-requirements.md)、[任务 Contract](../contracts/screening-tasks.md) | boundary/value test 任务/预算/成功/retry/恢复；无生产来源或完整编排/可见性。 |
| E8 | [A8 台账](a8-requirements.md)、[Pi RPC](../contracts/pi-rpc.md) | 1.4.0 离线协议、Python 管道进程、A7 test 接线；DERIVED 假设仍需 live。 |
| E9 | [Read Contract](../contracts/read-validation.md)、[A9 scope](../../scripts/a9_scope.py) | 结构/给定源字符/数值/reduce/配置与候选恢复；无真实正文生产、Read 任务。 |
| E10 | [A10 台账](a10-requirements.md)、[摘要审计](../contracts/fixture-audit.md) | HTTP 离线工程、冻结选样/矩阵/恢复；不证明四刊 live 或来源稳定。 |

索引中的 scope/Contract 是当前导航；执行过的具体哈希、分母及 not_assessed 以 E0 原始 JSON
为准，不用当前文档替换旧证据。原文件不存在的环境只能复核文档记录，不能据此声称本机重跑。
本票不把自己的最终 run_id 或工作树哈希写入绑定材料，避免验证身份自循环。

## 原实施逐条处置

| ID | 原要求 | 本次要求/实现状态 | 证据（范围见上表） | 下一责任节点 |
| --- | --- | --- | --- | --- |
| I01 | 初始化 uv 项目、锁文件、代码质量与测试命令； | 保留；已实现，历史离线验收 | E1 | A 后续能力沿用工程入口 |
| I02 | 声明 Docling slim 可选依赖组，保证常规测试套件不依赖 Docling 安装； | 转移；extra 未交付，普通环境无 Docling 仍可测试 | E1；§10/§11 B | B 前置独立票：安装/兼容/lockfile/模型；可并行 A |
| I03 | 建立配置编译、提示词版本、运行配置快照及阶段/校准配置投影； | 保留；配置与六阶段投影已离线验收 | E2 | B/D/G 实际消费与语义变更接线 |
| I04 | 建立 §7.7 的有界 Pi RPC adapter，固定运行资源与策略身份；V1 首次只启用 `prompt_only`，专用提交工具保留为显式升级能力； | 拆分；描述/协议内核及 test 接线已离线验收，生产启动器未交付 | E8 | B：1.4.0、真实成功来源、权限资源、/srv/pi-cwd 与 live |
| I05 | 建立 §7.8 的显式固定供给步骤、安装校验、原子激活、保留上限与显式清理，独立于个人 Pi 更新；配置编译切片只登记配置事实，不承担安装或 RPC 执行； | 保留；供给/安装保护/激活/清理机制已离线验收；无生产兼容证明 | E4 | B 首次固定 1.4.0 安装/RPC；保留 1.3.0 历史 |
| I06 | 建立 `screening/schema.py` 单一 Schema 权威、`screening/reasons.py` 原因权威及冻结 JSON Schema 导出； | 保留；单一结构/原因权威与冻结导出已离线验收 | E1 | B/D/H 消费同一权威 |
| I07 | 建立逻辑数据模型、Alembic 初始迁移和 repository 边界； | 保留；已交付范围的迁移/repository 已离线验收 | E1、E3、E6、E7、E10 | 各消费者逐片追加；不预建空表 |
| I08 | 建立内容寻址 blob/artifact store； | 保留；不可变内容 store 已离线验收 | E3 | B 真实内容与恢复闭包 |
| I09 | 实现阶段输入指纹、`normalization_version`、`excerpt_selector_version`、`chunking_version` 和任务 attempt/lease； | 拆分；A5 四阶段配方、A2 配置投影、A7 Screening attempt/lease 已离线验收；无 Read 任务 | E2、E5、E7、E9 | B Read StageInput/预算/持久化，D reuse，F/G 扩展 |
| I10 | 建立共享 eligibility 与 calibration visibility Interface； | 收口；完整共享纯规则接口未交付，现有局部规则不是替代 | E6/E7 未验边界；§11 A | A 合成事实/原因接口；B 首消费者，C 保留器 |
| I11 | 建立结构化日志、CLI 骨架和 doctor； | 收口；CLI 骨架与 pi-supply doctor 已实现，最小运行日志/基础配置 doctor 未闭合 | E1、E4；src/paper_radar/pi_supply/cli.py | A 最小日志/doctor，B 前接线；不建遥测平台 |
| I12 | 为根命令和首批命令组建立中文 `--help` 契约； | 保留；已有命令中文帮助已离线验收 | E1、E4、E6、E10 | B/C/D/H 随新增命令扩展 |
| I13 | 建立本机 SQLite 一致性快照及隔离恢复命令； | 保留；本机快照/隔离恢复已离线验收 | E3、E6–E10 | B 真实链恢复；I NAS |
| I14 | 固化四刊 Feed、摘要可得性、参考文献和 PDF fixture 注册格式； | 保留；四种样本声明/取得审计登记已离线验收，不表示真实 fixture 通过 | E10 | A live，F 四刊正文/摘录 |
| I15 | 四刊各审计 5–10 篇近期论文的 Feed、DOI 注册机构和出版者公开摘要路线，记录命中、疑似截断与所用获取策略版本。 | 未验收 live；工程已具备，首轮不足可移交但不算 A 通过 | E10；§4.3/§11 B | A 四刊首轮，JGR 判据阻断 B；C/F 补跑，D 前四刊收口 |

## 原测试逐条处置

| ID | 原要求 | 本次要求/实现状态 | 证据（范围见上表） | 下一责任节点 |
| --- | --- | --- | --- | --- |
| T01 | 摘要审计按获取策略分别保留路线结果与分母，渲染或授权通道不可用不改写公开路线结论；策略版本或联系信息变化不使既有审计结论失效； | 保留；策略/路线/分母离线已验，真实命中未验 | E10 | A live；C/F 新策略 |
| T02 | 空目录迁移后数据库可打开，外键、唯一约束和索引生效； | 保留；已交付迁移约束离线已验 | E1、E3、E6、E7、E10 | 后续每片迁移/恢复 |
| T03 | Schema 中不存在 papers.status、Rank、citation、自由标签或被引指标； | 保留；已交付 Schema 离线已验 | E1、E6 | 后续保持不变量 |
| T04 | 相同规范输入生成相同指纹； | 拆分；A5 四阶段与配置投影已验；无 Read 指纹 | E2、E5 | B Read StageInput；D/G 消费 |
| T05 | fake RPC 覆盖 ACK 未完成、正常 settled、错误/截断 stopReason、实际模型不符、超时、取消、子进程退出和 Schema/业务拒绝；仅完整有效输出可以成功，单次故障不阻断其他任务； | 保留；fake/真实 Python 管道子进程离线已验，不是真实 Pi | E8 | B 实际 Pi 协议/参数/完成条件 |
| T06 | 固定清单与 fake 供给/进程接口覆盖 Node/Pi 不匹配、包校验失败、安装中断保留旧版本、个人 Pi 更新不影响项目，以及 doctor/run-due 不隐式安装；无真实 Pi/Node 前置； | 拆分；供给 fake/机制已验；doctor/run-due 不隐式安装的未来消费者未全部交付 | E4 | A doctor；B/I 实际调度 |
| T07 | 跨论文、Screening 两阶段、reuse、Read map/reduce 及修正 attempt 的会话隔离；历史 Profile、隐藏结果、全文、自动发现资源与个人设置不能进入当前输入； | 拆分；通用会话机制与 boundary/value test 接线已验，跨阶段真实消费未验 | E8 | A 机制收口；B Screening/Read，D reuse，G map/reduce |
| T08 | Pi 隐含 retry、compaction、额外模型回合与未许可工具被禁止；同一输入最多两次 Python attempt，重建进程或切换通道不能重置预算； | 拆分；隐含回合协议拒绝和 A7 两次预算离线已验，真实抑制未验 | E7、E8 | B live 与 Read；D reuse，G 长文 |
| T09 | Screening/reuse 的适配器语义变化进入相关指纹与校准差异，纯 Read 策略或进程/会话 ID 变化不误伤 Screening； | 拆分；配置/阶段投影传播已验，真实接线未验 | E2、E5 | B/D/G 消费者 |
| T10 | normalization、excerpt selector 或 chunking 语义版本变化只使相应下游指纹变化； | 拆分；normalization/excerpt 配方及 chunking 投影已验，Read 下游未验 | E2、E5、E9 | B Read StageInput，D/F/G 扩展 |
| T11 | 同一声明版本下修改 Profile、提示词、契约或适配器材料内容时运行配置快照编译失败；新增版本并切换 selector 时保留旧文件和旧哈希； | 保留；声明版本不可换字节及历史回放已离线验收 | E2 | 后续版本化材料沿用 |
| T12 | 供给清单缺少行为影响判定、依据或证据引用时拒绝冻结；显式清理只删除计划内非保护安装，当前、在途引用与最近验收通过的版本不被移除； | 保留；供给冻结与保护清理离线已验 | E4 | B 生产实例验收，历史材料不改 |
| T13 | 只改变 Read 模型时可得到新运行配置快照，但校准语义基线及 Screening 输入指纹不变； | 保留；Read 配置不影响 Screening/校准基线已离线验收 | E2、E5、E9 | B/G 真实 Read 接线 |
| T14 | §4.5 工作流、Agent adapter、repository 和测试都导入 `screening/schema.py`，不存在第二份手写字段定义； | 拆分；已交付权威复用已验，§4.5 编排未全部交付 | E1、E7、E8 | B/D 两阶段/reuse 编排 |
| T15 | 规则、盲评、普通复核和元数据命令共享 `screening/reasons.py`，非法的结果/来源组合不能写入； | 拆分；原因组合/接收已验，盲评/普通复核/元数据写入口未全交付 | E1、E7 | B/C/D/H 随入口逐项验 |
| T16 | 所有展示面通过同一 calibration visibility Interface 屏蔽 waiting_calibration 与未揭晓批次的 Agent 制品； | 收口；完整 visibility 未交付，不声称所有展示面已隐藏 | E6、E7 的范围限制；§11 A | A 合成纯规则；B 首接，C/D/H 实际隐藏 |
| T17 | `paper trace`、调度和各积压列表对同一事实返回一致资格与原因； | 收口；完整共享 eligibility/调度积压组合未交付 | E6、E7 的映射/查询范围；§11 A | A 合成一致性；B trace，C/D/G/H/I 消费 |
| T18 | 改变卷期页码不使 Screening/Read 指纹变化； | 拆分；Screening 配方/任务书目隔离已验；无 Read StageInput | E5、E6、E7 | B Read 指纹；C/G 版本任务 |
| T19 | 改变摘要只使 Screening 及下游相关制品过期； | 拆分；摘要改变 Screening 身份与派生适用性已验；全下游未验 | E5、E6、E7 | B/C/D/G 失效消费 |
| T20 | 改变 PDF 使相关 Docling/Read 过期；若该 PDF 的制品贡献了复用摘录，相应升级也按其输入指纹重算，不使题名摘要 Screening 失效； | 拆分；extraction/reuse 配方传播已验；无真实 Docling/Read 过期闭环 | E5 | B 正文/Read；F/D/G 摘录/reuse/长文 |
| T21 | 在“文件已落盘、数据库未提交”和“数据库事务中断”处故障注入，重启不产生半条成功事实； | 保留；已交付 store/任务/审计故障原子性已离线验收 | E3、E7、E10 | B 新持久化边界故障与恢复 |
| T22 | 日志 fixture 中的 API key、完整 Profile、摘要和正文不会出现在输出； | 收口；局部诊断隐私已验，最小运行日志全禁项出口未验 | E7、E8、E10；§8.7 | A 全禁项合成 fixture；B 真实日志 |
| T23 | Pi session/JSONL、完整 RPC 消息与 stderr 不被永久落盘；必要成功输出可按业务制品回查，盲评未揭晓结果仍不出现在任何展示面； | 拆分；协议不留会话和成功原字节恢复离线已验；真实进程/展示面未全验 | E3、E7–E9 | B 真实日志；C/D/H 未揭晓消费者 |
| T24 | 根命令和每个已有子命令的 `--help` 为中文、包含副作用与示例、不访问网络或执行数据库写入； | 保留；已有命令离线帮助契约已验 | E1、E4、E6、E10 | B 及后续新命令随片验 |
| T25 | WAL 活跃时建立本机快照，隔离恢复后通过 integrity、foreign key 和清单检查； | 保留；活跃 WAL 非空历史隔离恢复已离线验收 | E3、E6–E10 | B 新闭包，I NAS |
| T26 | 摘要审计表按期刊、来源和疑似截断状态可重放；主路径不稳定的期刊会阻断相应真实闭环而不是伪造就绪。 | 拆分；离线矩阵回放已验；live 稳定与 B 就绪未验 | E10 | A 首轮；B JGR 门槛；C/F 补跑，D 前四刊 |

## 原DoD逐条处置

| ID | 原要求 | 本次要求/实现状态 | 证据（范围见上表） | 下一责任节点 |
| --- | --- | --- | --- | --- |
| D01 | 全部底座测试脱网通过； | 历史固定底座范围通过；新 A 收口能力未交付，当前树未跑完整门禁 | E0、E1–E10 | A 真正收口时验证完整新增范围 |
| D02 | 从本机快照恢复的副本可由 CLI 查询； | 已交付本机历史恢复/CLI 查询离线已验；无真实全链报告恢复证明 | E3、E6、E7、E10 | B 真实链，I 最终恢复 |
| D03 | doctor 能区分“基础工程可运行”和“因 Profile/模型尚未配置不能校准”； | 未完成基础/配置 doctor；已有供给诊断不等价 | E4；§11 A | A 复用既有查询，区分缺失/非法/通过/未验收 |
| D04 | 后续阶段无需重写身份、指纹、制品和事务基础。 | 持续约束；底座已有，不能证明未来消费者无需改动 | E1–E10 | B 起复用最终接口；首张 A 收口票定验收登记，A 真收口产机器结果，I 聚合 |

## 收口责任与未决项

- A 窄收口：最小日志、基础/配置 doctor、eligibility/visibility 纯规则。日志先于首次真实执行，基础 doctor 先于 Pi readiness，纯规则先于 B 首消费者。首张 A 收口实现票决定新能力 required 组或全量 pytest 的登记规则，后续沿用；本票不新建框架。
- 本 Markdown 是过渡清单。A 真正收口时由收口实现票生成机器可读阶段结论，I 负责聚合；历史 `stage_a_verified=false` 不改写，本票不新增全阶段通过字段。
- B 的工程链与 A 窄收口可并行：Docling extra，Pi 离线启动器→固定 1.4.0 安装/RPC，强冲突→Feed/元数据/语言事实，正文生产→Read 身份/预算。汇合入口、JGR 判据和私有本机重放见 [§11 B](../../intent/draft.md#阶段-bjgr-feed-第一条真实纵向闭环) 与 [ADR-0036](../adr/0036-isolate-stage-b-read-experiment.md)。
- 四刊首轮审计仍未执行；不足转 C/F 不算 A 通过。JGR 至少 5 篇全部非疑似截断主摘要的判据已确认；其他刊不阻断 B。四刊稳定阈值与是否一律非截断仍待用户在验收前确定，最迟 D 正式预热冻结/首批校准前逐刊收口，未达标时另裁决降级及披露。
- cwd 已确认 `/srv/pi-cwd`，不再列为待用户选值；现场无资源/权限隔离、1.4.0 DERIVED 假设与实际参数仍未 live 验收。Docling/Python 兼容与样本质量、F TDM/渲染/授权、正式校准和 NAS 同样未验证。
- C 初始化生产根，先导入 B 暴露清单再启用保留器与 visibility；F 供给四刊正文/摘录，D 执行 reuse 与校准，G 扩展长文，H 扩展展示面，I 聚合运行/恢复。

## 本票验证口径

语义复核覆盖较新评论、现行前置与历史记录的区别、全 45 条责任、相对链接及 ADR 例外。
scope 修改前必须先审计并解释漂移；只重绑实际改动的登记文件及 scope 变化导致的传递下游。
`order` 是引用图拓扑顺序，`affected_groups` 是当前异常及传播，最终可以为空。
默认审计不收集测试；独立核对分母须显式 `--collect --json`，它不执行测试体或发布结论。
不处理 #112 的绑定范围架构，不改旧验证 JSON，也不运行完整离线门禁。
