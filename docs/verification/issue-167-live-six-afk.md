# #167：六格批次 AFK 源码检查点与待裁定边界

固定 Node 诊断[已通过并恢复](issue-167-node-diagnostic-result.md)。随后按所有者偏好拆分fresh subagent并行完成资源观察、IPC、runtime/批次和独立审阅。当前交付是 **blocked 的源码检查点**，不是执行包；没有新Pi/认证/刷新/模型/网络/root、真实锁或实验库写入。

## 固定检查点

目录 `.scratch/issue-167/live-six-afk-review-v1/`；manifest SHA=`32c948e1a4d33d27d82453841d646958410ae9f995a4ba7788a89c2994ebba3b`，review.md SHA=`48ebb0811282f3db08130718cb80acf2046763866e437c69383de745a7336596`。

12个源码/测试副本、工作树对应源、合成manifest及5个固定Pi公开sourceproof全部同SHA。readiness=blocked、execution_authorization=false、run_preallocated=false、real_calls=0；无owner-wizard或安装入口，计划e93f7b82c461尚未预占/消费。原65个合成成员及authorization=not_granted保留，不借旧余额取得许可。

## 已实现且仅离线验证的接缝

- 受信runtime绑定解释器、标准库、应用源码及必要site packages；Root只执行stdlib封印/生命周期代码。UID1000在导入应用前核文件和目录成员，源码绕过旧pyc；未知模块不能转交后续finder，根链接不能追出许可代码范围。原始实际公有runtime绑定约2284文件/28根，只有已明确许可的内部链接，不复制全venv或向模型放宽权限。
- 六格沿真实公共prepare_launch/use_install/RPC及业务validator，保留原OFD、短期token匿名管道/私有内存/模型env，不改产品argv/env/preexec/策略身份。真实输入尚未执行；六格description/render在/tmp新库重定位的独立公开API回放6/6同字节。
- 原实验库的新低/高配置将通过公共compile/activate登记与切换。controller局部guard在公共BEGIN IMMEDIATE事务内同时核OLD完整选择与NEW固定实例/root/请求snapshot；冲突使整笔回滚，原函数/租约恢复。启动基线来自封印选择，提交后再核returned/current；恢复只按本批已确认选择CAS，追加历史，不字节回滚。
- 原选择及已确认activation写入原子journal；SIGTERM/SIGINT走受控finally恢复，commit不明、外部选择变化或journal/DB恢复未知都不能finish/passed。Root的unit/table恢复与DB恢复分别记录；SIGKILL及未确认commit不保证自动恢复，不猜归属或覆盖别人。
- auth/model两门闩在同unit中分别核CG和完整规则；已终止worker会提前结束等待，不拖到整批45分钟。token不进门闩、manager或回执；agent没有读凭据内容。
- 资源adapter预arm、CG可信封口、原删除、独立deleted；IPC与实际窄反馈见[独立台账](issue-167-live-ipc-afk.md)。这些组件完整不代表session零写；当前批次仍保留未解决的whole-attempt零写候选，生成执行包会受控拒绝。
- 协议观察只留类别计数、完整prompt写计数及对应ACK/agent_start等必要序号，不保存原流。公共run_call配合fake ByteSession的早/迟ACK两例均接成候选并验证元数据；HTTP下界不从prompt/TLS/packet造1，仍0+unknown，token依Pi报告，缺失/零未知。
- 每格在实际阶段开始采UTC/monotonic，协议、业务、文件观察和后验完成后才采verified/elapsed；类型、UTC、有限值、顺序均严格检查。这是未来采集口径，不是已生成供应商能力时间、产品clock authority或激活。

本轮没有真实实验库选择变动。未来公共配置登记/切换/恢复是必须列入新H1/H2的明确DB副作用，不能偷换audit_snapshot_id、伪造新库根身份或用前轮窄供给投影冒充完整use_install。

## 真实阻断与裁定材料

[裁定材料](../../intent/review/issue-167/live-six-observation-decision.md)列明固定实际入口的静态反证：正常Pi会创建非session的auth/model存储，入口还启用compile cache；因此“整个attempt mutation0、终态仅settings1”候选不可用于原样Pi。尚未实测，不能以预seed/env/argv变更、改产品身份或忽略写入使其过关。

原票目标是session全历史、attempt终态和独立删除。是否先实现内容无关的session/已知缓存分类观察，或保留更强零写候选继续阻断，等待所有者决定；分类未证明可行前不发真实执行申请。

所有者确认了专用认证目录供准备并由其维护。最窄lstat发现models.json缺失、models-store存在；没有读取内容、长度/哈希、token或派生值。固定auth分支仍读模型cache/全部provider凭据，命令型key可执行命令，provider参数不穷尽输入影响。必须由所有者声明可信输入范围或另供目录；不自动加凭据reader、删除cache或修改Pi。此信任条件与最终认证/模型执行许可分开。

## 验证及证明边界

五个新增独立未绑定D1模块：batch31、runtime11、bundle2、resources14、IPC28，相关组合 **86 passed**。命令为 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked pytest -q` 加这五个明确模块；没有Node/Pi或真实网络。12文件mypy（MYPYPATH=src）、Ruff check/format通过。

fresh实质反例包括finder回落、根链接、类型0/1混同、跨run窗口、缺协议顺序、事务旧选择/新目标覆盖、早期worker终止等待、恢复证据unknown仍可能finish及时间缺项；已按各自/tmp或纯mock回归收口。不是实际数据库并发故障/凭据泄漏。真实A4 IPC反馈仅为自建target/peer，不能算本服务/真实Pi通过；本轮不重复该矩阵。

checkpoint各成员/源/5个公开sourceproof核对通过，固定scope含collect审计、链接/diff随本轮回记。不改历史固定登记、分母、required或正式回执；未运行完整离线门禁。模型能力/参数效力、供应商故障、H5、产品接收与激活继续保留，普通产品仍缺证据阻断。

内部配置、进程/内核详情、绑定/回执及相关哈希仅留本地，不发布GitHub。
