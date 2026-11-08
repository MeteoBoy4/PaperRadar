# #167：H5证据盘点草稿（未接收、未闭票）

本稿供所有者审阅探索范围、残余项及后续工程，记录到[T1未触发且恢复结果](../../../docs/verification/issue-167-t1-result.md)为止的事实。它不是新的执行计划、接收权威、产品准入证据或激活记录，不授权任何root、网络、认证、模型或故障操作，也不把本票或Live模块标为完成。

所有者已在[故障范围H4材料](post-e01-h4-fault-scope.md)中明确选择K2/T1：不另备E02，直接注入实际Pi保留not_assessed且合成回归保留；先准备双向过滤无凭据验证，通过后再另批真实合并案例。本稿不把方向批准当现场执行或H5接收，更不能以“移交”替代明确有限范围接收。普通产品仍须独立满足完整Live准入。

## 阅读口径与绑定

1. 证据逐份采用自身记录的源码、实例、平台/host、启动/隔离、材料、角色、观察窗口及恢复绑定；确切hash、私有过程/认证元数据只链本地证据，不在此重复。相同Pi版本号不等于相同完整绑定，相同规则模板不等于已部署或已测效力。
2. 历史`unknown`、`not_assessed`和消耗保持原字节；后来的前瞻修复、独立成功或仅恢复，不能补造旧run缺失事件、改判旧结果或退款。表中“有限采用”与“整轮通过”分开。
3. [A1原事实矩阵](../../../docs/verification/issue-167-facts.md)、[初期AFK材料](../../../docs/verification/issue-167-afk.md)及早期原型是各自时点快照。计数、core、出口及S边界按后来的所有者裁决解释，不能恢复旧文中已经被取代的候选阻断或更强主张。
4. 供应商能力证据自**原验证完成**起30天硬到期；研究、接收、H4采用、重复激活或H5审阅不重置时钟。当前回执未进入产品接收权威，不在本稿另造可激活凭证。

## A1–A7盘点

| 项目 | 已有产物及可采用范围 | 尚缺／阻断与下一责任 |
| --- | --- | --- |
| A1 事实与覆盖矩阵 | 原矩阵覆盖I04/I05/T05/T07/T08/T12及DERIVED-01…11；其后[六格有限事实](../../../docs/verification/issue-167-live-six-result.md)、[E01](../../../docs/verification/issue-167-e01-result.md)、[官方资料研究](provider-authority-review.md)补充真实调用、文件观察和公布能力依据 | 原矩阵的历史未测状态不追写；H5须逐项接受新的适用范围。请求回显／公开配置支持不证明实际参数因果效力、日期alias或当前账号限额；未覆盖项由Live继续补证或交H4明确有限范围 |
| A2 三类文件观察 | [离线原型](../../../docs/verification/issue-167-observation.md)及后续服务/真实Pi接缝分开记录history、terminal、deletion；六格与E01的S窗口均有完整session/guard、终态分类及独立删除事实 | 只在绑定的被观察树/窗口成立；已知非session事件是下界，cache内部history仍not_assessed；终态空、删除成功或pre/post相同不能替代全部历史。Live产品仍须接可信collector及失败阻断，不能把合成descendants声明直接上线 |
| A3 请求／刷新计数 | [固定路径](../../../docs/verification/issue-167-request-paths.md)、[既有事件源核查](../../../docs/verification/issue-167-client-observation.md)明确分层；[ADR-0048](../../../docs/adr/0048-accept-bounded-request-observability.md)已接受可证下界＋unknown，以Pi报告token计量预算 | 隐藏retry/预热/刷新、独立HTTP及计费不可见保持；Pi缺usage或零值不当零成本。模型/CLI/packet不互换。loader保持[离线材料](../../../docs/verification/issue-167-loader.md)，不产品化、不登记请求覆盖或分母，不为此重跑EXP-2；精确计数在I无人值守/NAS门槛重评 |
| A4 部署隔离 | [core正负对照](../../../docs/verification/issue-167-final-core-validation.md)与[接线/服务](../../../docs/verification/issue-167-core-wiring-h1.md)、[IPv4合成](../../../docs/verification/issue-167-h1-v5-result.md)、[服务/OFD/观察](../../../docs/verification/issue-167-resolver-window-v3-result.md)、[网络](../../../docs/verification/issue-167-service-network-result.md)、[Node诊断](../../../docs/verification/issue-167-node-diagnostic-result.md)、六格及E01形成逐层有限依据 | 不合成为“所有隔离均通过”。当前只约束项目服务/资源及应用可见出口；IPv6 not_assessed、上游映射/出口身份未核验。项目INPUT双向机制已在IPv4 loopback无凭据正负对照中通过并恢复；最终post-stop原始值未留存，不能独立再算该项。T1已在实际Pi/fake-IP TCP443观察到双向DROP，8份完整快照和post-stop基准可再算；公共84.21秒提前error终态，300秒未触发，不扩为全部隔离资格；实际部署/变化检查/回收仍由Live工程负责 |
| A5 生命周期设计 | [生命周期原型](../../../docs/verification/issue-167-lifecycle.md)验证来源/完整性、批准计划、缺覆盖、人工激活、到期、漂移/失败撤销及重验拒绝路径；完整绑定组成候选已列 | HMAC/内存状态/合成owner action不是产品安全权威。receiver/collector独立权限、持久化/抗回滚、完整解析/绑定构造、逐调用核验与人工激活均未产品接线。不得导入任意JSON/Markdown/布尔值自证passed |
| A6 计划与预算 | [候选计划](field-plan.md)、[持久预算原型](../../../docs/verification/issue-167-budget.md)、逐轮封印/授权及[剩余矩阵](remaining-after-six.md)已区分动作、上限、期限、停止和恢复；E01单次范围已完成 | 原候选数量不是余额，换runID/失败/未触发/用量未知不退款或自增预算。K2/T1方向已定；T1无凭据前置已完成并恢复，真实合并案例已按单次批准执行并[未触发且恢复](../../../docs/verification/issue-167-t1-result.md)，许可已消费，不补跑/退款；剩余有限范围仍需所有者接收。本稿不新增许可 |
| A7 验证与文档 | 各轮结果分存verification、过程留review/Issue；新D1逐模块记数，相关pytest/静态检查、只读scope审计及fresh复核有相应报告 | 历史组合不相加为一份“总门禁”，旧分母/required/正式回执不扩大。E01准备115项／相关176项、T1准备197项及末次owner36项不是本轮重跑或产品准入；完整离线门禁未运行，只按用户明确指令执行。最终交付仍须对其当时完整树记录适用开发核对 |

## H1–H5盘点

| 项目 | 当前状态 | 所有者仍需明确的事项 |
| --- | --- | --- |
| H1 宿主部署审阅/执行 | 各具名包由所有者按独立封印审阅执行；agent仅只读复核。最近e93/d5遗留两树分别[仅清理完成](../../../docs/verification/issue-167-live-six-cleanup-result.md)、[仅清理完成](../../../docs/verification/issue-167-live-exit-cleanup-result.md)，E01及T1自身恢复/删除完整 | 这些批准不授其它unit/表/新机制或重验。任何后续新现场仍需具体H1。旧失败包曾按设计保留代码/runtime/永久记录；本稿不新查宿主、不能据最近成功声明所有历史制品已清零；H5应接受受控保留范围或另作精确清理安排 |
| H2 认证与现场调用 | 六格与E01各有单次批准和原预占；[认证附账](../../../docs/verification/issue-167-auth-input-refresh-ledger.md)撤回cache写回前提并记录e93批次关联依据；E01及T1已有credentials pre/post纯metadata直证，T1按独立条件0/1刷新计划执行 | T1后新的expires未读取，不能沿用任何旧过期声明保证再刷新1。下一轮须新输入或条件刷新计划，并明确可能联网/持久写/失败停止；真实目录cache新增只按该轮观察登记。旧批准、已完成auth或未用完信号上限不产生新调用余额 |
| H3 现场补测 | 六格各消费者/档位有有限正常事实；所有者H4 A已采用但整轮unknown不改。E01真实外部SIGINT→同一KI及本例清理/恢复通过，T1项目双向DROP与收尾有有限事实但目标未触发。core、规则/网络/Node等各有自身有限实测 | E02确定点直接注入实际Pi、实际Pi300秒/自然网络挂起、真实供应商错误、参数实际效力/日期alias/账号限额未由这些事实证明；普通产品CLI/租约、其它fault时点及跨consumer异常行为不得外推 |
| H4 取舍 | core第三路、计数有界口径、应用可见出口、S分类和六格有限采用已有明确裁决，见下表 | [K2/T1](post-e01-h4-fault-scope.md)已明确；不能扩展为现场执行批准。实际能力/限额等不可证项仍须逐主张明确接受范围、阻断和后继；不能把候选计划或公开文档当豁免 |
| H5 探索结论/交付 | 本稿只形成盘点；尚无H5接收、闭票或产品激活 | 所有者须审阅完整绑定/原始安全元数据引用、失败历史、有限范围和保留项；选择继续补测，或明确接受有限探索并逐项写清责任/阻断/下一动作。H5接收、闭票、Live完成和产品激活是不同动作 |

## 已接受H4边界，不重新选方向

| 边界 | 已接受内容 | 必须保留的代价/限制 |
| --- | --- | --- |
| core第三路 | [ADR-0049](../../../docs/adr/0049-bound-core-persistence-with-explicit-zero-limit.md)：持密子进程exec前软硬RLIMIT_CORE=0、服务LimitCORE=0，绑定Apport非打包适用分支；C合成零/非零对照成立，auth/model合成接线和现场零限额另有依据 | 不用全机分发器，不证明“从未被root内存采集”；该瞬时内存残余由owner接受。collector版本/配置/有效限额/uid路径漂移须后续doctor长期检查，不能迁移为NAS或其他程序core结论。正例rawcore精确清理已由后续接线报告确认，旧报告当时“尚未删除”字节不改 |
| 请求数与预算 | ADR-0048下界＋unknown；Pi token用量为预算权威，缺/零值未知；关闭既定retry/compaction/预热配置保持 | 不采用新产品启动身份、不产品化loader、不重跑EXP-2；unknown不填0，不由连接/packet补HTTP1。I重评精确计数；doctor和后续日报须披露不可见项 |
| 真实出口 | [ADR-0050](../../../docs/adr/0050-bind-egress-to-owner-visible-addresses.md)采用所有者冻结的应用可见fake-IP池TCP443与路由器UDP/TCP53 | 池/配置变化停止；不换真实供应端IP，不核上游映射或主张出口身份；无TLS中间人取owner来源，IPv6not_assessed。具体调用/TTL窗口单独批准，旧窗口不续用 |
| S文件分类 | session/guard完整、session零观察写、完整终态和独立删除；源码支持的非session store/cache/锁/公开settings重写另列 | 不等于全attempt零写；边界事件下界和缓存内部history not_assessed保持，未知路径/别名/失watch/overflow/缺参照阻断；认证持久目录与模型临时agent不能混算 |
| 六格有限采用 | [owner选择A](live-six-exit-decision.md)：正常RPC/业务/S/usage有限事实可作后继输入，原监督退出缺证据单列 | e93整体仍unknown，不重发六格、不退款；后来的d5/E01监督成功不能补写其缺失退出证据，也不延长30天期限 |

## 失败、unknown与恢复分列

| 历史 | 可采用的后续状态 | 不可重写的内容 |
| --- | --- | --- |
| 早期H1 v2/v3 | [失败与修订](../../../docs/verification/issue-167-h1-failures-auto.md)保存初始化/能力缺口、预占和恢复摘要；后续修订有独立新授权/结果 | 不把后来配置/权限修复当原例通过；旧code/runtime曾明确保留，不能从artifact=null声称已删 |
| v4 IPv6/恢复 | [v4记录](../../../docs/verification/issue-167-h1-v4-recovery.md)保留超时、规则身份历史缺口与一次性恢复；[后续IPv4](../../../docs/verification/issue-167-h1-v5-result.md)有独立合成成功 | IPv6超时不是拒绝成功；一次性恢复例外不放宽通用归属判据，IPv4成功不补原未完成阶段 |
| c591 resolver/window | [原例与仅恢复](../../../docs/verification/issue-167-resolver-run-unknown.md)确认资源恢复；[v3新例](../../../docs/verification/issue-167-resolver-window-v3-result.md)通过并保留真实baseline/完整快照 | 原例整体unknown、缺失全局resolver前基线不重建；新例不回填旧例，也不称旧真实异常已唯一定位 |
| e93六格 | 六格有限事实经owner采用；后续两树清理闭合 | 原整轮unknown/exit缺口、失败字段、账本与消耗不变；不以目录已清代替成功退出 |
| d5监督 | [退出有限事实](../../../docs/verification/issue-167-live-exit-probe-result.md)及后续18节点清理闭合 | 原artifact失败及整体unknown不改；nsfs误拒有具体实现反例但旧root原异常未保存，不声称唯一归因 |
| T1真实单格 | [双向DROP成立、公共提前error终态及恢复完整](../../../docs/verification/issue-167-t1-result.md) | 结果not_triggered_and_restored不改，300秒未证明、不认供应商错误通过；不补跑、不退款 |
| T1无凭据双向机制 | 单次loopback正负对照及恢复通过，完整留存阶段链可再算 | 不转移到真实Pi/外部TCP443；最终post-stop原始快照未留存的限制保持，不改旧unknown |
| E01 | 单次受审结果及host/DB/目录恢复通过 | 不转移到其它consumer/档位、全部KI时点、供应商取消/零成本或产品CLI/租约；不消除旧unknown |

永久单次记录是刻意保留的审计材料；“unit/表已卸载”“代码/runtime已删”“原账本不变”“没有任何历史残留”是四种不同主张。仅在相应报告有据时采用，不以本稿作新宿主盘点。

本稿形成后新增[四run有限metadata盘点](historical-retention-metadata.md)：旧code/runtime和永久记录确实保留；精确unit文件/CG缺失，主代理普通宿主只读manager核七Id均not-found且无MainPID/CG/加载路径，其中两guardian仅保留failed退出缓存。当前nft未另查，采用历史owner恢复证据时保持该层次。此盘点不授权删除，也不新增“全部历史制品必须清零”的要求。

## 逐项剩余主张与接收前条件

| 保留项 | 当前依据/缺口 | 所有者选择与后续阻断 |
| --- | --- | --- |
| E02直接注入实际Pi | E01实际KI＋合成pump/cleanup KI已知；确定post-decode/pre-return点直接注入未测 | K2已定：本阶段不另备E02，采用有限KI依据，H5明确范围/后继；direct-injection not_assessed，不记passed |
| 实际Pi300秒/网络挂起 | 本地合成300秒已测；项目机制及真实T1的双向DROP已有各自有限事实，public84.21秒stop_reason返回、300秒未触发 | 单次许可已消费，恢复完整；300秒能力仍未证明，不补跑/退款，剩余范围交所有者H4/H5；不得加大任务、停pump、重置300秒起点或重试凑通过。未触发保持未触发 |
| 自然供应商迟延/错误 | 本机DROP、SIGKILL、合成错误不是供应商事实；自然错误未安全取得 | 自然遇到也须来源足够；不故意耗尽额度/损坏凭据/超额请求。保留not_assessed或由H4明确有限范围，不因别的fault通过而放行 |
| 实际effort、日期alias | 官方公布模型/low/high语义及固定源码映射有依据；实际因果效力和日期映射未确立 | [官方资料成本方案](provider-authority-review.md)供H4；不靠两次输出/耗时差异、猜日期后缀或加alias白名单。strict mismatch保持，Live能力资格缺口保留 |
| 当前账号模型/订阅限额 | 旧实际调用和OAuth结构不能给当前余额/重置/可用集合；公开catalog不等于当前账号权威集合 | 可由owner给非秘密界面声明或另批适用查询，未做则unknown；不自行登录、查token或套API key配额/价格 |
| 认证持久写/刷新 | e93的更新通过owner补证关联批次而非回执事件；E01及T1pre/post直接记录metadata delta | 不从metadata推内容、writerPID、全历史或HTTP1；未来沿用有界metadata接缝。当前expires已可能更新，不沿旧过期值强制推计划 |
| IPv6/新平台/无人值守 | 当前本机应用可见IPv4范围有限；IPv6 not_assessed | 不迁移当前site/collector/root风险接受。I重新评估NAS/无人值守与精确计数，缺项继续阻断其资格 |
| 普通产品CLI/任务租约 | 实验公共prepare/run_call不同于PiExecution.run_attempt和正式任务入口 | B/Live后续在正确入口核租约/预算/日志/中断结算；不通过patch admission或测试私有_evidence_for获取许可 |

## 后续Live产品工程交付清单（尚未实现）

当前[source read_evidence](../../../src/paper_radar/pi_execution/admission.py)仍返回None，[执行Contract](../../../docs/contracts/pi-execution.md#一次任务执行组合)的explicit映射为空；普通任务继续缺证据阻断。以下是需由Live规格/实现接走的明确工程，不是本票已接线清单：

1. **受信采集与接收**：受保护collector/receiver身份、来源和完整性、独立权限、所有者批准计划与逐案例预算、失败/unknown历史、观察连续性和安全metadata解析。不得信配置passed或原型合成owner字符串。
2. **完整绑定构造**：实际供给/实例/整树及Node工具链、平台/host/boot/kernel/ABI、cwd祖先、端点/上游范围、服务/CG/规则/core、精确argv/env/settings、observer及六格config bundle/slot、provider/model/protocol/sampling/auth/参数。路径或版本字符串不能代替实际身份，缺项不接收。
3. **持久状态与人工激活**：完整案例重算为received/pending身份，再经独立owner通道显式activate；持久化/事务审计/抗回滚与备份权限。接收不触发模型，激活不重置原验证完成时间或预算；本票实验接收/闭票均不代替该动作。
4. **到期、逐调用检查与撤销**：[ADR-0047](../../../docs/adr/0047-expire-and-explicitly-activate-live-evidence.md)的30天硬expire、当前绑定/条件复核、漂移/失败立即保守撤销、旧事实不复活；明确依赖表、针对性重验及影响不明扩围。重验另批，通过后仍需人工激活。
5. **真实生产入口与预算**：在领取/刷新前接缺证据阻断，完整prepare/use_install和OFD生命周期；任务attempt/每日配额/租约/retry代际由原服务维持。持久计划索引与预占、未知不退款、重启不清余额，不能用新文件或runID重置。
6. **部署与doctor**：产品专用服务/规则/权限安装卸载、observer/CG可信边界、失败恢复与当前配置检查；core版本/配置/有效限额/非打包分支漂移长期doctor由后续工程负责。[doctor](../../../docs/contracts/doctor.md)仍需填真实readiness，不自动安装、调用或激活。
7. **诊断/日报口径**：doctor与后续日报明确请求近似下界＋unknown、Pi token而非独立计费、隐藏retry/预热/刷新不可见、usage缺/零值未知及剩余未验范围；不得让操作者把模型或认证成功误读成Live就绪。精确计数的实现选择由I重评，loader不顺带上线。

B仍承接真实产品入口/实验根/所选根日志/用途与预算质量消费并等待完整Live；F仍承接真实四刊正文/摘录质量，G仍承接长文与map/reduce，I仍承接无人值守/NAS恢复与最终集成。真实资料外发、正式校准、四刊正文质量、长文和NAS资格均未由本票授予。

## H5签收前尚须明确

- 核对K2/T1的实际落实：E02保留未测与合成回归，T1无凭据前置已完成，真实单次未触发且恢复；300秒缺口及其余保留项仍须明确有限范围接收；采用范围不能扩成product通过或把候选余额当授权。
- 对每个保留项明确下一责任、阻断对象和下一动作；需要改变既有要求的另行裁决及相应文档，不把“研究已看过”当实际能力通过。
- 接受完整失败/unknown历史、永久记录和受控保留材料；仅恢复/后继成功不改变旧run，后续所有实际清理仍精确H1。
- 接受后续产品清单的未实现状态和普通产品阻断，区分本票接收、是否闭票、Live模块状态与另一次产品激活。
- 审阅交付时的完整树/相关开发核对及固定scope结果；不把历史subset或本草稿当完整门禁。完整门禁只在用户明确指令时运行，本稿不新增“必须现在跑全门禁”的要求。

初稿由子代理只读既有本地票快照、文档和源码形成；主代理随后按K2/T1及各次独立结果更新盘点。编写本稿本身不运行现场或读取凭据内容、环境、日志/core或私有账本；各次实际动作及验证只以所链按次证据为准。当前具体H4/H5待审入口见[按次审阅材料](post-t1-owner-review.md)；本稿不是批准记录，未执行闭票或产品激活。
