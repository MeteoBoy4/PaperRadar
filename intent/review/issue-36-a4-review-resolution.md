# Issue #36 A4 外部双轮审查处置

实施基线：`6d188616cc941505c4799f085ce7f28ea04e0cde`，分支 `implement/issue-36-external-review`。
本文件是独立核实与处置记录，不改写审查历史。两份原报告完整纳入版本控制：

- [r1 原文](issue-36-a4-full-review.md)，SHA-256 `a57e5d970d9df221605739405221ce3edb15e3ac4d28ff651cf24af637c23eff`。
- [r2 原文](issue-36-a4-full-review-r2.md)，SHA-256 `c860455731e953f1e9fba1933ce1c6338fc36ff6d247239b63963785d44e6f5f`。

权威依据为用户本次裁决、父票 #36 的正文与后续裁决、子票 #37–#45、`intent/draft.md`、
`CONTEXT.md`、相关 ADR、Contract 和 `docs/agents/`。实施时读取的 Issues 原文在
`/tmp/paperradar-issue36.md` 至 `/tmp/paperradar-issue45.md`；仓库长期对照入口是
[a4-requirements.md](../../docs/verification/a4-requirements.md)。审查推断不等同规格明文。

## 用户裁决与安全边界

2026-10-18 用户接受本次 A4 export 的必要安全文件能力边界；能力不足继续受控拒绝。
Windows 安全导出由 [#46](https://github.com/MeteoBoy4/PaperRadar/issues/46) 后续交付和验证，
#46 不阻塞已裁定的本次平台范围；#36 保持 OPEN。本次未开发 Windows 后端，未放宽
nofollow、目录句柄、不覆盖发布或 fsync 要求。README、Contract、主方案 §7.8 和父规格逐条归属已同步。

list/show 是历史读取，保留原目录不可达时的隔离恢复能力。list 补充「历史登记、未核验现场」；
show 既有披露保留。doctor、activate、使用句柄声称当前可用时仍须现场核验。

## r1：Standards 全部编号

| 编号 | 独立证据及判断 | 处置、理由与验证 |
| --- | --- | --- |
| S1 边界越界 | `git diff main...基线 -- intent/draft.md` 有五个纯空行，分布三个 hunk；其余供给布局和六份结论有父票依据。 | 采纳，逐一回退五个空行，保留合法布局/A4 结论。无需为 Markdown 空行编造运行时测试。 |
| S2 A3/A4 acceptance 重复 | `_reason/_environment/_migrated_revision` 和结论骨架确有相似代码；底层 byte/receipt/identity/publication 原语已共享，各阶段消费与格式条件不同。 | 本轮不采纳提取三个helper，理由是范围与回归成本取舍：共享实际environment/migration采集完全可行，也不会削弱独立期望校验，但需额外修改并重新审查绑定跨阶段脚本，本轮优先修已复现行为缺口。三个helper的重复作为可行后续整理保留，不将该建议扩大解读为必建通用框架。各阶段独立判据继续保留；r2 S8另讨论输出常量共享的不同风险。 |
| S3 安装根 Message Chains | 当前源码有 16 处 `.path.parent.parent`，确实共同表示登记实例的安装根；审查所说17处属于统计差异。 | 采纳有界改进：`InstallInstance.root` 统一表达该领域概念，替换 cleanup/protection/repository 等现有消费点；纯路径投影，不访问现场、不改存储字节。trash 推导只有定位与验证等不同职责，保留，避免把删除安全判断藏进通用路径 helper。既有保护/计划/执行/历史恢复回归覆盖行为不变。 |
| S4 roots Data Clumps | `safe_roots` 接受显式四根，公共 prepare/rebuild 用三个必填 keyword 根，计划冻结这些路径；它们是危险根判断的审查输入。 | 拒绝此轮引入 roots 对象。内部roots值对象完全可以保留公共API和plan字节；全面替换才会涉及更多边界。本轮不承担该可行整理，现有必填keyword已避免位置误传，未发现由此造成的错误；新增转换类型的维护收益暂不足以优先于行为修复。安装根语义通过 S3 改进，保留计划字段和字节。 |
| S5 ID Primitive Obsession | Pydantic `Hash` 是 Schema 字段约束；CLI/服务完整 ID 检查和库内回放分别使用不同受控错误，32/64位身份也不同。 | 拒绝机械改成统一 Pydantic 解析或统一异常。它会混淆调用输入错误与腐坏历史，增加一层转译；正则虽相似，边界责任不同，当前无格式不一致证据。既有非法 ID 回归保留。 |
| S6 lazy Middle Man | `__init__.py` 明确用于延迟执行模块导入，CLI help 的无 I/O 哨兵有公共回归；没有循环依赖证据。 | 接受报告“已缓解/可接受”的结论，保留公共 facade 与 lazy 边界；不因转发数量删除它。 |
| S7 use_install Speculative Generality | ADR-0029 和 #41 明确要求后续执行器可消费的安装使用句柄；它与 verify 的明确实例接口职责不同。 | 拒绝删除；这不是凭空预留。真实父子 fd 继承、选择变化和在途保护测试证明该 seam 的当前契约。生产 RPC 尚未实现继续披露。 |

## r1：Spec、聚合注记与覆盖声明

| 编号/范围 | 独立证据及判断 | 处置、理由与验证 |
| --- | --- | --- |
| (a)1 D5 路径 | #38 和父补充一15明文是“相对请求文件解析”，并未逐字规定 containment；`Path(base) / absolute` 会替换 base，`..` 与链接可越界，实测三例均在旧代码冻结成功。 | 部分采纳审查定性并修复：绝对路径违反相对输入；拒绝 `..` 和解析后越界是本次合理请求边界补强，不能声称是原规格原话。`RequestEvidence` 拒绝绝对/`..`，freeze 按请求目录解析且检查实际边界；旧证据只回放库内字节，不重读路径。公共 prepare 三个反例先红后绿，库内无供给登记。 |
| (b) scope creep“未发现” | 只交付供给生命周期，无 RPC/task 框架或业务表；mount 检查、RENAME_NOREPLACE、全库闭包与裁决对应。 | 接受这一覆盖结论，不据此新增功能。本次只修已核实缺口与局部可读性。 |
| (c)1 固定512MiB | 父第二补充10是“建议”下载前做粗略自由空间预检；没有规定512或要求精确预测 npm 峰值。`check_space` 确用 statvfs；Node 展开允许1GiB，512不是充分保证。`_publish_tree` 同文件系统改名，不复制第二份新树。 | 局部采纳：Contract 明确固定粗略早拒绝、非峰值估计、较大包/缓存/并发仍可能之后失败。拒绝以归档压缩大小猜 npm 展开量或无依据扩大保底值；额外扫描归档不能在下载前估计未来 npm 树，也不能保证空间足够。保留已有零空间拒绝/下载前无副作用测试和后续受控失败。 |
| 聚合注记 S1/(a)1 | 独立 diff 与公共服务红例支持实质问题；r1把 containment 称“收紧意图”，比“规格明文”准确。 | 按 S1/(a)1 处置，记录实际五空行/三个hunk。 |
| 其他实现已覆盖/残余风险 | r1列 prepare/verify/rebuild/activate/保护/gc/export/doctor、六项裁决、第二补充和 #45 六文件；这些有现有固定公共回归。 | 本轮保留这些实现；真实下载/安装 live 未运行，不继承 spike 为 live。报告提“6跳上限”并不准确：transport允许最多5次跳转（最多6次请求），Contract 已写5；不改变安全上限。 |

## r2：Standards 全部编号

| 编号 | 独立证据及判断 | 处置、理由与验证 |
| --- | --- | --- |
| S1 ADR 改写 | `git diff main...基线 -- docs/adr/0029*` 是新增文件，905ae19是在同一未合分支内修订；末段已有 #43 安全更正、原意与 inode 理由。 | 拒绝原文“既成 ADR 硬违规”，采纳聚合者降级。没有推翻已合 main 的 ADR，不需仅为行数/历史猜测新建 superseding ADR。保留安全更正，缺锁不得重建；文末已明确旧表述及原因，Git 可还原 #41 历史。 |
| S2 intent 范围 | `.tools/pi/<supply_id>/<install_id>/` 是父票裁决2明文，A4结论来自#45；五空行是三个hunk。 | 部分采纳：只回退五空行；拒绝回退正确布局/结论或重新索取已授权许可。对应 r1 S1。 |
| S3 read_state/service Long Method | read_state 同次只读事务加载并核验材料、引用、激活、计划/执行与失败事实，cleanup_history 已是独立纯回放模块；service 串联安装 I/O。 | 拒绝仅按647/853行拆文件。闭包验证跨这些事实是其单一责任；拆出多个helper并传同一connection能够保持一致性，属于可行后续整理，并不必然造成多次数据库读；本轮没有由函数长度导致的可复现错误，故不承担这项较大代码移动。局部统一 root、移除不必要延迟 import，保留单事务语义和备份完整性回归。该可导航性债务记录在此供后续设计评估。 |
| S4 重复校验/rows/双读/扫描 | RequestEvidence 输入使用 path，冻结 Evidence 使用摘要，supply_material 两者约束不同；D5.complete 又分别用 Field/回放限制。两个 facts rows 检查确实相同；双读事实在昂贵查询前后有并发防漂移意义。 | 部分采纳：统一私有 `_fact_rows(plan,name)` 的形状检查。保留请求/冻结两种校验责任、前后安全视图和不同历史查询的明确缺失错误；不为两次线性扫描引入通用repository框架。历史语义与新阻断坏事件回归覆盖。 |
| S5 CLI异常样板/plan过滤 | 命令各自映射 SupplyError到2、取消到130；同步查询与变更命令并不共享所有异常/输出语义。show-plan 按完整历史回查并过滤执行。 | 拒绝批量加装饰器/通用命令执行器以及仅为一次过滤新增服务API。当前边界显式且安全，抽象易遮蔽哪些命令取消可写事实。只在真实缺口处增加D5提示和批次阻断文字；公开CLI回归验证。 |
| S6 facade与别名/retention转发 | lazy facade延迟I/O，有#41公共协议；execution.retention_protection是已使用公共入口，对retention纯规则的命名适配。 | 拒绝删除/批量重命名公共转发。局部公开导入名称的误导按下表 O1修复；本次不改稳定消费方边界，不把Middle Man本身当bug。 |
| S7 roots/9参数/测试tuple | 根路径是安全边界显式输入；`_build_tree` 是单一服务内私有受控调用，当前两个调用有相同协议；tuple是既有fixture工厂。 | 拒绝roots参数对象和约640次测试tuple迁移，后者会重写远超本次触及测试且不增加行为证据；此轮无需新通用配置类型。现有 public keyword 根保留，root属性收口见r1 S3。 |
| S8 跨阶段scope/issue OR链 | A4消费端独立核对A1/完整A2/A3的封闭scope、issue和格式，不能接受任意前置；输出端各有自身常量。 | 拒绝共享输出端同一常量生成期望或通用验收框架；这会让改错的生产值和消费校验一起变化。底层字节/回执原语已共享。硬编码是独立验收合同，保留并由A4前置漂移/失败回归核验。其余helper重复按r1 S2有界拒绝。 |

### r2“一句带过”逐项归属

| 本文编号 | 原项与独立证据 | 处置与验证 |
| --- | --- | --- |
| O1 | service把公开 `check_platform/check_root_marker` 导成 `_platform/_check_root_marker`，名字隐藏真实作用。 | 采纳，保留公开函数原名和现有调用，Ruff/mypy与供给子集验证。 |
| O2 | repository函数内导入selection，selection不依赖repository。 | 采纳，移到模块顶层；help仍通过lazy facade隔离执行服务导入，纯本地help回归验证无I/O。 |
| O3 | materials.check_engine把条件表达式直接放if，语义正确但难读。 | 采纳，命名为mismatch后再判断，不扩大semver子集；既有engines拒绝/通过测试验证。 |
| O4 | 新测试有较多函数内import，部分为测试专用边界/依赖本地引入；成文标准未禁止该形式。 | 拒绝统计驱动的批量搬移。不会修行为缺陷，反会扩大固定资产重绑；本次新增测试沿用模块既有风格，只对真实公共行为增加验证。 |
| O5 | 原报告说“未发现退役/trash不可逆删除ADR”；ADR-0029实际已写#43退役/trash/删除遵守互斥窗口，Contract执行节明确永久退役与断点恢复。 | 拒绝以“未发现”推定缺失。父票D4/#43已授权永久退役和显式删除，并无偏离既有架构；没有理由新增重复ADR。本次不回退已有安全更正。 |
| O6 文档同步合格 | CONTEXT、README、Contract、离线证据与a405 head原本一致。 | 接受抽查，继续同步本次新增的用户裁决/输出/阻断语义；head不变。 |

## r2：Spec 全部编号

| 编号 | 独立证据与规格性质 | 处置、理由与验证 |
| --- | --- | --- |
| P1 export平台 | 父第二补充9及#44原AC确曾写“不受平台限制”；缺Python目录/no-follow能力即export_failed属实，原生Windows尚无后端。 | 按用户新裁决采纳范围收口；不是通过代码放宽安全门伪装完成Windows。四处相关文档链接#46并明示未实现/未验证，#36不关闭。对应本文用户裁决节。 |
| P2 D5路径 | 绝对路径与..逃逸在旧公共prepare实测成立；目录containment是合理补强，不是原规格逐字规定。 | 修复及三例红绿见r1(a)1。保持已有冻结材料、引用和供给身份原字节，不迁移历史。 |
| P3 list/show现场 | Decision10早期笼统“查询不能跳过现场核验”；后续父Decision21、#44及平台补充明确原根不可访问仍可历史查询。show已明示未核现场，list此前只有instances计数。 | 部分采纳防误读目的，list增加历史计数/未核现场。拒绝历史读取依赖本机Pi或现场；当前可用断言仍走doctor/activate/句柄。本次回归先红后绿，并在原安装根删除后运行跨进程list/show。 |
| P4 cleanup错误归因 | 旧active停末项，第二轮首项树变会把末项记failed；库级facts变化也错误归因末项。#43要求逐项事实真实。 | 采纳。每轮单项检查准确设active，库级前置active为空时整组原子追加not_run+受控阻断reason；回放要求全候选初始化、整组同reason、不可续行。按库内最后事件去重记录，退役提交后中断标真实未完成进展，completed/failed不覆写。两个OS flock驱动真实漂移反例先红后绿，均非空备份/恢复且撤销原根可回放；另有真实事务retired/completed提交后取消、坏reason/部分阻断/伪续行拒绝、第二条写失败整组回滚。 |
| P5 D5后续评估 | Decision17明文要求may_change/unknown显示后续评估；旧show仅原清单，doctor仅decision/basis。 | 采纳，show/doctor共用窄文字helper，明确需要后续相关语义评估、不代表校准兼容、不自动minor/major。两个decision经公共跨进程show和doctor先红后绿。no_change不会无依据显示这段，不改变门禁。 |
| P6 持久协调锁 | 原Contract已有“DB旁发布锁→根锁→固定输入锁”，并非完全未登记；文件名、生命周期确不完整。SQLite仍唯一供给事实源，空锁只协调内核互斥。 | 部分采纳：补精确名称、顺序、作用、只close不unlink、不进身份/备份/导出/删除候选。拒绝删除锁或伪装scope creep，unlink会割裂旧inode与新取得者。既有并发prepare/根认领/重入测试核验，文档补充无需镜像内部调用测试。 |
| P7 pi层help | 旧pi_app/supply_app共GROUP_HELP，pi实际只有supply，确误列直接prepare等。 | 采纳，为pi组写准确中文help和pi supply --help示例，保留配额/输出/副作用/纯help。公共help拒绝“prepare 准备”误述的回归先红后绿。 |

### r2 聚合者六项校正逐条核实

| 编号 | 处置 |
| --- | --- |
| A1 Standards1降级 | 同意；新增ADR在同未合分支修订，不是已合main裁决翻转。见S1，不新增无必要ADR。 |
| A2 Standards2部分纠正 | 同意；布局获父票裁决，空行才越界。实际五空行、三个hunk，见S2/r1S1。 |
| A3 Spec3降级 | 同意区分历史与现场；再补list缺少明确披露这一实际缺口。见P3。 |
| A4 Spec1维持 | 原审查时范围冲突确存在；现由用户裁决和#46收口，不再称未裁定阻断。见P1。 |
| A5 Spec2维持 | 同意路径缺口事实，纠正“相对”不等于原文含containment。见P2。 |
| A6 其余抽查 | 逐个归属S3–S8、O1–O5与P4–P7；采用真实收益有界修复，拒绝项均列具体边界和成本，没有把聚合“属实”自动等同必须重构。 |

### r2 子票验收表逐项归属

| 子票 | 本轮核实与处置 |
| --- | --- |
| #37 | 保留1.3.0机制spike和官方形状fixture；未重新运行网络/npm，不把机制结果算项目live。 |
| #38 | prepare/list/show闭包与安装流程保留；P2路径补强、P3历史提示、P5输出修复归该票。 |
| #39 | verify/rebuild固定材料、随机新实例、失败历史不变；root属性仅路径投影。相关旧实例/缺锁/重建回归保留。 |
| #40 | 唯一选择、显式scope、unknown安全拒绝不变；P3/P5/P7只补准确输出。 |
| #41 | 树外继承flock和缺锁不补建保留；root属性不改变fd或锁inode。真实进程竞争回归仍必需。 |
| #42 | plan-v1、facts_version及历史规范字节不改；root属性与局部rows去重不改变计划身份。 |
| #43 | P4修复真实逐项归因和库级前置阻断。a405既有表/字段/受控reason足以表示新增事件；无新增schema/migration，不改旧plan/旧事件。新程序接受全部旧合法历史；新阻断事件须使用匹配程序回放，不能靠旧程序拒绝新语义推定数据可删。 |
| #44 | 历史查询/非空隔离恢复保留，P1由新用户裁决及#46区分范围，不实现Windows安全后端。 |
| #45 | 固定范围人工核实后增加新回归分母，源文件与受影响测试逐项重绑；不删能力、不降分母、不自动bless、不改六主文件+回执协议。live_install_verified仍false。 |

## 验证记录与剩余边界

先按tdd技能在已获授权public seam验证：D5路径3例旧实现失败；第二轮树/全库facts漂移2例旧实现失败；
CLI历史披露、pi组help、两种D5状态共4例旧实现失败。修复后对应回归通过。
后续增加真实提交后中断、严格坏历史和整组诊断事务回滚，避免只修active表象。
相关六模块子集曾通过100例，新增事务原子性例随后单独通过；最终以冻结提交后的完整入口证据为准。

A4固定清单保持30测试模块、51源码、5 fixture；用例从346增加14为360：boundaries 21→24、
cleanup_execute 24→32、cli 10→13，其余分母不变。开发时独立pytest收集核对，再人工登记。
已有终端fixture是验收入口投影，与新增Pi输出无关，原字节保留；公开Pi行为通过跨进程断言验证，
不新增整份help快照。A2/A3固定资产逐项核对，只有实际字节受影响的登记项才重绑。
四份冻结契约、五个旧Pi migration和更早migration不改；历史plan字节由回归证明不变。

计划完成门槛为工作树冻结并commit后 `./scripts/check-offline` 返回0；该运行期间不修改任何跟踪字节。
最终run_id、七文件、逐检查退出码和提交身份写入 `/tmp/paperradar-issue36-external-review-implementation.md`，
避免为了把结果回写本文而改变正式证据身份。本文本身不宣称尚未运行的完整gate已通过。
真实下载/安装、模型/RPC、校准、生产隔离、NAS与Windows后端未在本轮验证；512MiB仍只是粗略前置拒绝。
read_state/service的大函数、roots对象与测试fixture类型化属于有具体理由暂不改的维护债务，非隐藏完成项。
