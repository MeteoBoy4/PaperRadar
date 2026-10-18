# A4 父规格与评论逐条归属

依据：[父票 #36](https://github.com/MeteoBoy4/PaperRadar/issues/36) 正文、实施前补充、
[六项裁决](https://github.com/MeteoBoy4/PaperRadar/issues/36#issuecomment-6243720810)、
[第二补充](https://github.com/MeteoBoy4/PaperRadar/issues/36#issuecomment-6243820754)、
[Pi 1.3.0 更正](https://github.com/MeteoBoy4/PaperRadar/issues/36#issuecomment-6243849006)。
后裁决优先。以下是责任和验证入口，不是历史证据的通过继承；本次整体状态以同 run_id 的
六份主要文件和额外 pytest 回执为准。没有批准 A4a/A4b 截断。

## 正文 Implementation Decisions

| 条目 | 责任票 | 实现/公共验证落点 |
| --- | --- | --- |
| 1 生命周期内聚、纯规则与 I/O 分离、无通用任务框架 | #38–45 | pi_supply 公共服务；全部固定 Pi 模块；#45 唯一 AcceptanceGroup |
| 2 经验证快照、显式槽、版本源、不增 settings 槽 | #38 | test_pi_supply、boundaries、history；既有 config 公共回放 |
| 3 严格请求、精确 Node/npm、用户 D5、Linux x86_64/glibc | #38 | models；test_pi_supply、boundaries、tree |
| 4 清单规范载荷/supply_id、实例、语义三类身份独立 | #38/#40 | manifest-vector；test_pi_supply、activation_history |
| 5 官方三材料原字节、override、逐包依据、冻结重建 | #38/#39 | materials；test_pi_supply、rebuild、rebuild_history |
| 6 npm 实际消费固定摘要、冲突/缺依据拒绝 | #37/#38 | derived-lock-v1 ADR-0028；transport/process 与材料负例；#37 spike 仅机制 |
| 7 bundled npm、固定 ci、私有环境、明确入口、有界取消 | #38 | execution/transport；test_pi_supply_process、transport、boundaries |
| 8 tree-v1 全范围、链接/执行位、入口冻结、无模型检查 | #38/#39 | filesystem；test_pi_supply_tree、rebuild、process |
| 9 全检查后冻结、不覆盖发布、事务/并发、重复/损坏重建 | #38/#39 | service；test_pi_supply_history、rebuild_history、boundaries |
| 10 SQLite 原字节、审计、固定导出、无 blob 扩种类 | #38–44 | tables/repository/export；history/export/cleanup_history 全量回放 |
| 11 显式短事务激活、旧/新完整选择、历史快照 | #40/#41 | execution/selection；activation、activation_history、protection |
| 12 内核保护、子进程继承、异常保守、不替代 task lease | #41/#43 | protection；test_pi_supply_protection、cleanup_execute；ADR-0029 |
| 13 当前+最近三不同旧实例、额外保护/超限、未激活统计 | #42 | retention/cleanup；test_pi_supply_cleanup、cleanup_history |
| 14 install_check/RPC scope 分离、无生产伪成功导入 | #40–43 | doctor/retention；activation、cleanup；合成 RPC 只作规则输入 |
| 15 固定计划、事实版本、实际树、仅计划 ID 执行 | #42/#43 | cleanup_models；cleanup、cleanup_execute、cleanup_cli |
| 16 排他窗口、永久退役、trash/逐项中断恢复、材料不删 | #43 | cleanup_execute/delete/history；真实强杀与半删恢复回归 |
| 17 D1–D5、新 adapter 纪律、三态/基线/引用、无 enable | #38/#40 | models/materials；pi_supply、history、activation_history；沿用 #23/#26 |
| 18 doctor 只读供给切片、具体缺项、RPC/模型未验收 | #40/#41/#42 | doctor_supply；activation、activation_cli、protection、cleanup |
| 19 全部供给 CLI、显式根、分离保护、中文 help/退出码 | #38–44 | pi_supply/cli 与根 CLI；各票 *_cli、export、boundaries |
| 20 日志/参数/异常脱敏、有界消费、D5 用户非秘密材料 | #38–44 | transport/cli/error；process、boundaries、各 CLI/export 失败哨兵 |
| 21 a302→追加迁移、既有事实不变、语义备份/隔离恢复 | #38–44 | a401–a405；history/rebuild_history/activation_history/cleanup_history/execute_history/export_history |
| 22 离线 fake/真实实现分开、live_install 恒 false | #37/#38/#45 | 真实 httpx/Subprocess 实现；#37 一次 spike；#45 a4_verified 不授予 live |
| 23 同次必需 A4、前置/receipt/身份/格式、严格覆盖/兼容 | #45 | a4_acceptance/scope；a4_acceptance、a4_entry、a4_test_receipt、既有 verification 回归 |
| 24 Contract、词汇、ADR、布局、README/证据文档 | #38–45 | pi-supply/backup-restore/offline-evidence、CONTEXT、ADR-0028/0029、主方案 §6 |

## User Stories（逐条编号）

| 编号与需要 | 责任票 |
| --- | --- |
| 1 项目独立安装 | #38 |
| 2 精确工具链 | #38 |
| 3 adapter 取版本 | #38 |
| 4 三材料原字节 | #38 |
| 5 override 保留 | #38 |
| 6 实际下载校验 | #37/#38 |
| 7 补充 integrity | #37/#38 |
| 8 平台条件 | #38 |
| 9 staging 完整检查 | #38 |
| 10 显式激活 | #40 |
| 11 明确 Node/JS | #38/#41 |
| 12 原子选择 | #40/#41 |
| 13 在途安装固定/保护 | #41 |
| 14 固定预期重建 | #39 |
| 15 树规则 | #38 |
| 16 adapter 新版本与历史 | #38/#40（沿用 #26） |
| 17 D5 判断/依据/证据 | #38 |
| 18 执行审计不改变投影/基线 | #40 |
| 19 语义风险不自动兼容 | #38/#40 |
| 20 当前+三旧窗口 | #42 |
| 21 先计划后执行 | #42/#43 |
| 22 当前/在途/验收保护 | #41–43 |
| 23 执行前重查 | #43 |
| 24 逐项中断与重入 | #43 |
| 25 清理后材料/审计 | #43/#44/#45 |
| 26 备份历史与材料 | #39/#40/#42–45 |
| 27 恢复不装程序/不激活 | #44/#45 |
| 28 doctor 具体缺项 | #40–42 |
| 29 doctor/help 无副作用 | #38–44 |
| 30 无 Node/Pi/网络普通测试 | #38–45 |
| 31 受控安装诊断 | #38–44 |
| 32 旧库/恢复兼容 | #38–45 |
| 33 独立同次 A4 | #45 |
| 34 真实供给显式，fake 不冒充 | #37/#38/#45 |

## 正文 Testing Decisions 矩阵

| 验收行 | 责任票与固定公共回归 |
| --- | --- |
| 配置衔接 | #38：pi_supply、boundaries、history |
| 版本纪律 | #38：pi_supply、boundaries；沿用 #26 |
| 官方材料 | #38/#39：pi_supply、rebuild、rebuild_history |
| 下载完整性 | #37/#38：pi_supply、transport、boundaries、process |
| Node/npm | #38：pi_supply、boundaries、process |
| 安装约束 | #38：boundaries、process、history |
| 树哈希 | #38：tree、pi_supply |
| 首次冻结/重建 | #38/#39：history、rebuild、rebuild_history |
| D5 | #38/#44：pi_supply、history、export_history |
| 激活原子性 | #40/#41：activation、activation_history、protection |
| 安装保护 | #41/#43：protection、cleanup_execute（真实父强杀/子 fd） |
| 保留窗口 | #42：cleanup、cleanup_history |
| 清理计划 | #42：cleanup、cleanup_cli、cleanup_history、cleanup_unreadable |
| 清理执行 | #43：cleanup_execute、cleanup_execute_history、cleanup_cli |
| 语义身份 | #40：activation_history（沿用六投影/基线公共服务） |
| 验收范围 | #40/#42/#45：activation、cleanup、a4_acceptance |
| migration | #38–43：各 history 的真实旧 revision 升级；storage_migrations |
| 备份恢复 | #39/#40/#42–45：各 history、export_history、a4_combination |
| doctor | #40–42：activation/CLI、protection、cleanup |
| CLI/help/隐私 | #38–44：各 CLI、process/transport/边界与导出哨兵 |
| 证据 | #45：a4_acceptance/entry/test_receipt、verification_*、a2_full_entry |

验证顺序由 #45 执行相关子集后，稳定提交上运行唯一 `./scripts/check-offline`。
公共服务使用真实临时 SQLite/文件树，仅下载/外部程序与必要系统故障边界替换。
低层排列由相应分票负责；#45 非空组合验证完整生命周期、清理后导出和隔离恢复衔接。

## 实施前补充与六项裁决

| 评论条目 | 责任票、裁决结果与证据落点 |
| --- | --- |
| 补充一 1 / 六项裁决 1：三槽与单一选择 | #40：全部已配槽匹配；混合版本具名拒绝；记录快照，未来执行者重验 |
| 补充一 2 / 裁决 2：多实例布局/坏树 | #38/#39/#42/#43：supply_id/install_id、staging、实际 hash 候选；主方案 §6 |
| 补充一 3 / 裁决 3：D5 三引用/基线 | #38/#44：文件原字节有界、仅已存在材料/记录，首次拒 no_change；恢复可解析 |
| 补充一 4 / 裁决 4：派生锁与 spike | #37/#38：方案 A 仅补 integrity、不改图/原件、冲突失败、ADR-0028；#37 独立机制实测 |
| 补充一 5 / 裁决 5：来源/代理/httpx | #38：三来源固定、逐跳拒外部、npm resolved+integrity 边界、无 userinfo/环境代理；新越界端点必须回父票裁决 |
| 补充一 6 / 裁决 6：a302 备份断档 | #38–45：唯一 head 精确匹配；旧批次 checkout A3→verify/restore→新程序 db upgrade，建议新备份；backup Contract/README |
| 补充一 7：Node 收窄 | #38：推导官方 URL、SHASUM 原字节/bundled npm、tar data filter、glibc 探测；不作 GPG 声明 |
| 补充一 8：engines/共用校验器 | #38：最小 >=X.Y.Z/精确子集；Node/npm/Pi 同一 exact_program_version |
| 补充一 9：整树/umask/入口/规范编码 | #38：node/app 全树、任一 x 位、私有缓存在树外、只读发布、bin 冻结；tree 测试 |
| 补充一 10：核验深度表 | #38–41：pi-supply Contract；prepare/rebuild/verify 执行探测，activate/use/doctor 仅静态核验 |
| 补充一 11：重复 prepare | #38/#39：同材料拒绝指向 rebuild；坏树不改冻结身份/D5 |
| 补充一 12：flock | #41/#43：树外持久锁、SH/EX 非阻塞、fd 继承、先永久退役再 trash/delete、本地 FS；ADR-0029 |
| 补充一 13：恢复选择 | #39/#40/#44：绝对根仅本机审计、现场完整则可继续、丢失 rebuild→显式 activate，无恢复标记 |
| 补充一 14：启动网络边界 | #37/#38：固定关闭遥测/更新与私有环境；不声称生产 OS 网络隔离 |
| 补充一 15：请求/doctor/中断 | #38/#40：严格 JSON/YAML/重复键拒绝、相对证据路径、不默认 scope、退出 130 |
| 补充一 16：备份/根 | #38–44：backup format1 不增字段，语义闭包、所有保护根互不包含；A3 blob 无删除论证不变 |
| 补充一 17：未知残留 | #38/#42/#43：未知 staging/发布树只列人工处理及占用；只能按可信冻结/登记重入，不自动认领删除 |
| 补充一 18：live 证据 | #38/#45：用户库真实 prepare 的 install_check；离线恒 false，无新 live 文件或导入捷径 |
| 补充一 19：Git/导出 | #38/#44：.tools 忽略，固定七类导出名避开忽略模式，D5 内容寻址 |
| 补充一 §三 收缩 | #38/#40：只补快照供给、共用版本校验和代表性六投影/基线；不重复旧排列/通用 semver/npm 独装/备份字段 |
| 补充一 §三 扩展 1–7 | #40 混合槽；#38 umask；#39/#43 坏实例重建与删除；#44 恢复异根/D5；#41/#43 父强杀子 fd；#38 重复准备；#37 spike |
| 补充一 §三 拆分预案 | #45：未批准截断，十项能力全部必需；不能据预案降低范围 |
| 补充一 §四 六词汇/Contract/ADR/布局 | #38–45：CONTEXT 六术语；供给/备份/验收 Contract、README/help、ADR-0028/0029 与 §6 |
| 补充一 §五 revision 成本 | #38–45：逐个重绑 a2/a2_full/a3/A4/backup；不放宽任意 head、不借机改框架 |

## 第二补充（逐条）与版本更正

| 条目 | 责任票与落点 |
| --- | --- |
| 1 显式快照/混合可准备不可激活 | #38/#40：既有 reference 解析、无 latest；doctor 具名 mixed |
| 2 多实例确定选择 | #40：最近 install_check 通过且现场可用；事件 install_id、CLI 无实例参数 |
| 3 安装根归属/恢复共用 | #38/#42/#43：root marker，他库拒绝/标注；恢复共用原根旧副本退役前禁止 execute，flock 仅保护在途；Contract/ADR |
| 4 rebuild 重新联网 | #39：只用保存 SHASUM/固定哈希重取归档，不重取元数据/解析依赖；Contract 明示 |
| 5 并发同请求 | #38：唯一冻结身份先提交胜，后到者树一致才幂等指向、清理自有 staging，无第二实例 |
| 6 固定安装策略 | #38：install-policy-v1 进入清单，无自由扩展参数 |
| 7 trash 残留 | #42/#43：已退役待删单列，新显式计划回收；未知 staging/trash 始终人工 |
| 8 doctor scope/退出/D5 | #40：固定 pi-supply、未知/缺项退出2、全通过0，D5 原文/摘要只展示 |
| 9 平台作用域 | #38–44：运行时 arch/libc 比对，仅 prepare/rebuild/activate/verify；list/show/export/备份恢复无平台前置 |
| 10 空间预检/占用 | #38/#42：下载前 statvfs 失败前移，真实 allocated/logical 遍历、回收估计不进身份 |
| 11 固定导出名 | #44：package.json、package-lock.json、release.json、supply-manifest.json、integrity-supplements.json、SHASUMS256.txt、d5-evidence/<sha前16>.bin |
| §三 测试 1–8 | #40 mixed/最近实例；#38/#42 他库根；#38 并发；#42/#43 trash；#40 doctor；#38 runtime platform/空间预检 |
| §四 不变量/编码/树文本 | #38/#40/#41：invariants 执行审计不进指纹、python-conventions httpx、tree-v1 UTF-8/POSIX 路径 |
| §四 六文件与回执 | #45：wrapper help、唯一链式入口、固定模块/计数、六主文件另加 receipt |
| §四 spike 回贴内容 | #37：精确 Node、derived-lock SHA-256、EINTEGRITY 脱敏摘要；仅机制，不替代 A4 |
| Pi 1.3.0 更正 | #37：机制实测改为 1.3.0；#38 fixture 使用该官方形状；不设部署默认版本、不新增 live |

## 未领取范围与旧能力纪律

| 正文 Out of Scope / 备注约束 | 责任 |
| --- | --- |
| A1/四冻结契约、A2/adapter、A3 既有算法不重做 | #38–45：只新增必要公开接缝、追加 migration、兼容绑定；旧 migration/冻结字节保留 |
| RPC/ACK/agent_settled、provider/model/参数/模型隔离/输出 | 后续阶段 A；#45 rpc_verified 恒 false |
| 论文事实、指纹执行、task/attempt/lease、两次预算/配额、eligibility/visibility/调度 | 后续任务；安装保护不替代业务租约 |
| 用户 Profile/模型凭据、校准等级/evaluation/enable | 后续任务；D5 不自动推断或授权 |
| Read 权威输出、Docling/正文/参考文献/报告/trace | 后续任务；A4 不安装或调用 |
| 四刊 registry/来源审计、Feed/PDF/模型/NAS、完整 doctor/日志 | 后续任务；离线 A4 不授予阶段 A/B 或自动精读资格 |
| 代码开发只在本地、实施分支 implement/、集成 integration/ | #37–45 实施与主集成代理；不 push；Issue 回贴/关闭由主代理处理 |
