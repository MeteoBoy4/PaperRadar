# #167：单格E01外部SIGINT待审包

## 本轮状态与身份

[d5的18节点仅清理已完成](issue-167-live-exit-cleanup-result.md)，原e93/d5整轮unknown和消耗保留。本轮只准备E01，不重验旧案例。当前输入更正、07:13更新的批次关联与证明缺口见[认证附账](issue-167-auth-input-refresh-ledger.md)；精确模型/effort及订阅路线的公开依据见[官方研究](../../intent/review/issue-167/provider-authority-review.md)，不将其当当前运行效力、日期映射或账号余额通过。

canonical `.scratch/issue-167/h1-live-signal-e01-v1/`，run=`4e01c7a3b962`；尚未预占或执行，results仅offline-validation.json。

| 材料 | SHA256 |
| --- | --- |
| review-seal.json | `ddce0ec03ecbb819d124c94d92babf1d4d75420dcd97ff6972bb6bf9152e3646` |
| manifest.json | `fa93c2512eb380510186240704b20476d30209b5b34c57a5512e240e059bebde` |
| owner-wizard.sh | `df3f5aee23bdb4d137c5e00ae452cc16dab21f0e6190eb1bec116149f92bbd5f` |

旧draft1/draft2入口已禁用，旧c669封印不得代替本身份。最后重封只更新owner-review及随之manifest/driver/seal，其余39个core成员包括3份runtime源、context、unit、rules和zip未变。

## 新H1/H2/H3的具体范围

新增具名unit `paperradar-167-h1net-4e01c7a3b962.service`、唯一inet表 `paperradar167_4e01c7a3b962`，代码 `/home/paperradar-probes/issue167-4e01c7a3b962`、runtime `/run/paperradar-issue167-4e01c7a3b962`及永久单次记录。root操作由所有者审阅执行，准备授权和既有清理许可不包含本轮现场执行。

固定value/low，openai/gpt-6.1-sol/prompt_only/provider_default/chatgpt_subscription，temperature/top_p=null。最多auth CLI1、显式prompt1、模型exec1、Node2、外部SIGINT1；零应用重试，不退款/补跑。worker720秒、service780秒、owner900秒，auth30秒、model300秒及有界回收。正常过早完成或信号迟到不换high、不扩任务、不再试一次。

真实执行将读取专用OAuth并因当前过期而计划一次联网刷新、持久写回，然后运行一个合成模型调用；不能把认证安排成离线前置。独立模型/刷新HTTP下界0、上界unknown，packet、CLI或计划logical refresh不冒充HTTP1；Pi内部解析/QNAME/fallback继续unknown，须本轮H2明确认可。Pi报告usage为预算权威，缺失或零值不解释为零成本，不能主张供应商计算已经停止。

调用材料由公共build_stage_input/build_call/render_request重建，单格zip23成员，产生新的input fingerprint。执行复用完整public prepare_launch/use_install/run_call和原OFD，模型argv/env、产品LAUNCH与pi_protocol不变；不调用六格loop、修改ORDER或patch普通产品准入，不声称生产任务租约。

## 外部事件与三类结果

root初始ready即固定controller的pidfd/starttime/unit/CG身份，发送前重核；只向该controller发送一次SIGINT，不向unit或进程组发送。intent/delivery保存最小目标身份和marker引用，与worker ready、CG binding、Case fingerprint交叉核对，失败不换PID重发。

SignalMeter仅在已解码prompt完整写出、ACK started、agent_start且尚未观察settled/closing时发布一次marker，不暂停pump等待root。该marker不是RPC内核已消费ACK、供应商已收到请求或父目录fsync已返回的证明。实验controller handler只在明确MODEL_CALL通信窗口记录并抛同一真正KeyboardInterrupt；清理/认证/恢复期不得伪称有效中断，不扩大成普通产品CLI行为通过。

目标KI在prepare_launch作用域外、观察器作用域内捕获；要求public terminate完成、显式S assert_complete、模型目录独立删除、CG只剩controller、原逻辑选择恢复，controller随后按原严格loaded success/CG空退出谓词收尾。中断后的Node不强求exit0；controller正常收尾须exit0。

- observed_expected_and_restored：有效外部事件与同一KI、S/公共后验、DB/host/目录回收及永久记录均可核。
- not_triggered_and_restored：只限完整正常提前结束或明确记录的迟到，完整正常候选仍须公共validator/EOF/settled/退出0。它不是E01覆盖；向导完整保留回执并返回非0提醒，预算不退。
- unknown：发送/接收不明、缺目标/marker引用、格式或观察失败、协议/后验/恢复失败。不能按耗时或“可能迟到”推成未触发，也不自动补验。

## 当前认证、元数据与实验库

所有者再次确认onlyopenai OAuth、scope含chatgpt.tokens.use.direct、无额外provider/命令型输入；models.json缺失、models-store仍空2bytes/0成员、cache旧mtime。先前“已写回非空cache”前提已撤回。auth实际写入经精确时间窗/结构与排外声明关联e93批次，不指CLI序号/HTTP1，不重复加算；原回执缺写入事件这一限制保留。Case的分钟mtime是初始报告摘要，最新精确补证完整写入owner-review及认证附账。

credentials pre/post快照固定顶层四名及root，只有node-compile-cache下允许有界递归；max64节点/depth6/每份16KiB。输出仅relative集合与mtime/size/inode/ctime，类型/owner/mode/dev/nlink仅内部核边界；不读任何文件内容或marker值。逐层dir_fd pin祖先、NoFollow及两遍稳定检查；缺参照、越界、alias/special、采集中不稳定均unknown，不能截断。

credentials根inode前后相同，exp2-installation-id四stat不得改变；auth inode可合法atomic replace，auth/store/cache实际前后delta分别记录。快照时间与公共prepare_launch区间均须落在该case时间窗内，引用/集合/计数严格校验。它能证明所观察区间delta，不是瞬时全写史或writerPID鉴别；persistent history仍not_assessed、目录不删除。准备只读实际27节点控制为4364bytes，不是认证前后直证。

真实exp2.sqlite3已有历史。准备仅用mode=ro/query_only/authorizer的八张公共供给/选择表投影、公开代码和依赖绑定，不读业务行/凭据，不执行真实锁。执行才在新许可下公共compile与同事务CAS选择、恢复真实原baseline；保留追加历史，不清空、初始化或字节回滚。恢复journal末态必须与原选择语义tuple相同，activation_id可因追加历史改变。

## 隔离与回收

应用可见允许集合仍为28.0.0.0/8 TCP443、192.168.44.1 UDP/TCP53，池变停止，IPv6 not_assessed；不使用真实供应商IP、不核上游映射/最终IP/线路或主张出口身份。无TLS中间人仍为owner来源，不新增DNS/TLS预热探针。service/preexec CORE0、NNP、空cap及原IPC/cwd前置保持，不改全机core、resolver、router或其它程序。

模型S要求session/guard全窗口完整且session零写、完整终态和独立删除。已知非session为事件下界，cache内部history不外推；unknown路径/失watch/overflow/alias等阻断。认证目录独立于模型临时agent，刷新完整退出和持久化后验前不arm事件；刷新失败/超时/轮换未知停止，不回滚auth.json。

root只标准库管理封印字节/具名单元和规则，不import可写应用。CG空后按独立binding完整核表再撤表/卸unit，host与DB恢复分别核；未知不finish。清理复用已审Tree/record和严格nsfs/mount parser，NoFollow相对删除，不携旧main/perform/RUN路径。可能因部分安装、归属或清理失败保留本unit/表/树，须所有者仅恢复，不保证一切失败自动清空。关闭sender等收尾完成后才写最终账本，避免stdout与永久状态矛盾。

## 本轮离线验证

新增五个独立未绑定D1：case22、worker24、owner38、snapshot8、bundle23，合计 **115 passed**；加相关resources16和session_observation45组合 **176 passed**。九文件mypy（MYPYPATH=src）、Ruff check/format通过。完整run_case模拟覆盖同一KI、正常提前、明确迟到、非目标异常、publication后故障、公共后验失败及观察不完整；Root三终态和15故障阶段、sender关闭/最终账本一致、生成Tree实际/tmp两树收尾均有回归。计数布尔混同、快照重复inode/旧case时间、错误恢复目标/ACK矛盾及祖先别名反例均先红后绿。

generic cap40未增：旧4个规则附件合成review-rules.json、移除冗余members.sha256，加入3个signal模块及1个精确来源chunk cleanup。新scope专用required集合、40成员/import闭包、两entry/bootstrap、完整driver/unit/四份规则、zip23公共链逐字重渲染均已独立核；runtime当前2284文件/28根绑定有效。生成helper逐字绑定既有源码，不从workspace运行时抽取或fallback。

最终完整近cap owner envelope **69866bytes <131072**、worker **42701bytes <65536**，包括两份16383-byte快照、8份完整kernel fixture和journal，已通过实际LOCAL_RESULT读写往返，无padding或放宽上限。observed/NT/unknown均保持完整，矛盾/错身份/重复键/超界及别名拒绝。

固定系统Python真实Root entry离线加载控制只移除唯一main调用：执行main0、根模块9、成员读取41、主动操作0、workspace fallback0；权限/路径身份为明确synthetic，不等于实际root安装权限通过。另有sealed-copy owner/worker/helper导入与7节点合成快照，app导入/regular credential read均0。bash-n通过；普通宿主用户systemd-analyze对仅替换三处固定代码前缀的/tmp语法副本verify退出0、无输出，未安装/启动原unit。

旧draft1/draft2禁用，最终ddce重封fresh差异终核通过。链接/diff和固定scope含collect审计随本次收口记录；不扩历史分母/required/正式回执，未运行完整离线门禁，未重复合成SIGINT/300秒控制。本轮没有实际Pi/Node、认证、刷新、模型、事件发送、服务/规则或真实数据库写入；公开文档研究是独立只读来源核查。内部配置、metadata、绑定/回执及相关SHA只留本地。

获具体新H1/H2/H3批准后，所有者入口见owner-review的四项确认命令；只在终端输入一次sudo密码，脚本核验并执行。自检不授执行许可，H5及产品接收/人工激活仍待，普通产品缺证据阻断保持。
