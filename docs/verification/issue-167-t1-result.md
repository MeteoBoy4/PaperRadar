# #167 T1：双向DROP已发生，公共300秒未触发，恢复完成

## 单次执行与结论

所有者按[单次H1/H2/H3批准](../../intent/review/issue-167/t1-authorization.md)运行了[封印待审包](issue-167-t1-preparation.md)，run=`8b31f0a9d672`。review-seal SHA256 `b47a6945ed485280180c633b292a66b217bebcd7904ba772b0b7e9db9374673d`、manifest `dc4ef368e719c9ceda7940301ba550681c391c6182a05f54f552e081cba3e8e4`、driver及40成员均未漂移。

受控 `results/owner-run.json` SHA256为 `ad2502f5879e2e5dbab24d66c2dee16858c9eb53b7ecf0b5fe9de79b896c6b3f`，落地pretty JSON为190110bytes。外层、内层均为 **not_triggered_and_restored**，单格not_triggered。主代理及fresh独立只读重算一致，没有重跑认证、模型、规则或服务。

本例已发生有效marker及项目双向DROP，但公共调用在84.206621752秒以stop_reason返回，未到300秒。它不是TIMEOUT通过，不证明自然供应商迟延或真实供应商错误；按照所有者T1，不补跑、不加任务、不退款。实际Pi公共300秒能力仍未取得现场证明。

## 触发、返回与用量

| 观察 | 实际结果 |
| --- | --- |
| case UTC | 2026-11-08 07:30:55.145489–07:32:27.932562 |
| case总耗时（含认证及后验） | 92.787076462秒，不用于300秒判据 |
| public monotonic耗时 | 84.206621752秒 |
| prompt完整写出 / decoded ACK / agent_start | 各1，ACK序号10、start序号11 |
| 首个有效非空text marker | 1，序号23，完整性complete |
| 双向切换attempted / completed | 1 / 1，确认发生在原300秒截止前 |
| 公共reason / assistant error终态枚举 | stop_reason / 1 |
| 正常候选验证 / 候选提交 | false / false |
| public terminate返回 | true |

public开始4725597.003508909，factory进入4725597.003565365，marker4725610.498455722，切换意图4725610.565664136，确认4725610.656827431，public返回4725681.210130661。持续pump，没有重置总期限或提前resume。最终协议81记录、message_update63、agent_end/settled均0；仅保留类别/计数/序号，没有读取或保存原始错误正文来推定原因。

这些事实证明受控双向DROP后观察到了assistant error终态，不能定位为某个SDK计时器、上游故障或供应商HTTP状态，也不能把本机诱导事件冒充真实供应商错误验证。tokens=null、token_status=unknown；不能当零成本或供应商停止计算。消耗本轮auth CLI1、model factory/prompt1和双向切换1，无外部信号；独立模型/刷新HTTP继续下界0、上界unknown。

落地pretty JSON大小不代表原131072byte输入限制失守：受审LOCAL_RESULT已经接受该envelope；对同一已读JSON的紧凑重序列化为88987bytes，仅作形状参照，不宣称还原原stdout精确字节。

## 双向规则、S与恢复

8份完整kernel_state逐份重算通过，deny0→allow1→stall2引用链完整，独立target PID/CG与ready/binding一致。绑定CG dev30/inode860403；PID3169081/starttime472558633及完整规则/handle仅留本地回执。INPUT与OUTPUT只针对项目socket/cgroup，TLS DROP范围保持应用可见fake-IP池，DNS仍按冻结范围允许。

| 阶段 | allowed in/out packets | dropped in/out packets |
| --- | --- | --- |
| created deny / preauthentication / transaction allow | 0 / 0 | 0 / 0 |
| auth complete | 15 / 13 | 0 / 0 |
| before stall | 49 / 43 | 0 / 0 |
| transaction stall | 54 / 48 | 1 / 0 |
| before exit / post stop | 54 / 48 | 19 / 11 |

最终dropped bytes为28348/572；全部unexpected packet/byte始终0。完整post-stop原始快照已留存，六类packet及byte均严格等于独立before_exit基准；不是仅凭布尔完成声明。部分非终态计数比较参照来自受审gate/collect中的未命名核验，不要求它与上一份留存快照相等；所有参照均单调，收尾基准仍严格冻结。allowed含DNS，不当TLS或HTTP计数，不主张上游映射、最终IP或出口身份，IPv6not_assessed。

S的session/guard/terminal/cleanup完整，session及unknown mutation0、post-terminal write0，settings语义成立、目录删除成功。已知非session事件下界为auth_store3/model_store3/compile_cache1/control_settings12/store_lock30；不扩成整个attempt零写或缓存内部完整历史。

严格退出为gate write_complete、wait complete、CG空，卸载前manager为active/exited/success、ExecMainCode1/Status0/MainPID0及空CG。恢复为host_policy_restored、table/unit absent、resolver前后相同、restoration_stage complete、两树清理完成及永久记录保留。原双向DROP保持至收尾，没有resume阶段。

## 持久认证元数据与数据库

pre快照07:30:59.309906–07:30:59.313080UTC，public prepare_launch（含认证）07:30:59.313283–07:31:02.788407，post快照07:31:02.788682–07:31:02.790262。快照均27节点，集合无增删，仅根目录和auth.json的mtime/ctime变化；inode/size不变，不能称已观测atomic replace。模型临时树与持久认证目录分开记录。

models-store仍为size2且四项stat无变化，cache23节点和安装marker四项stat均无变化；这不是内容检查或瞬时全部写史，也不推writerPID。旧owner确认过的空store事实按其原时点保留，本轮不新增内容主张。认证完成并有受控区间内metadata delta，和条件计划相容，但不据此分配独立刷新HTTP1。未读取新expires，后续不得沿旧过期声明；持久目录保留，不回滚认证。

DB journal为original10→batch11→restore12，恢复原snapshot/root/supply/install语义并保留追加历史。主代理另以mode=ro、query_only及只允许两张公共选择表的authorizer核当前activation12与报告一致；没有读取业务/凭据行或写库。独立结果存 `results/post-run-selection-readonly.json`。

主代理普通宿主只读lstat确认 `/etc`、`/run`精确unit文件、CG及code/runtime两树缺失；具名单元manager为not-found/inactive/dead、MainPID0，CG/fragment/drop-in/User/Group空。永久记录root:root、0600、nlink1、88770bytes、inode1052847；仅读stat，未读内容或计算实际内容摘要。table absent采用封印控制器核验后的恢复回执，本轮未另提权读取规则。

## 后继与验证口径

本轮只读重核封印、schema/结果、8份完整规则、3段引用、target/时间链、认证metadata、公共DB选择及恢复状态；准备阶段197项不登记为本轮重跑。没有代码变更、重复物理KI/300秒控制或完整离线门禁。按D1保留旧分母、required、历史回执、unknown和消耗。

下一步仅提交[有限探索范围与H5审阅材料](../../intent/review/issue-167/post-t1-owner-review.md)，不自动接受残余缺口或以“移交”宣布本票完成。普通产品CLI/租约、准入接收/人工激活、自然供应商迟延/错误、实际参数效力/日期alias/当前账号限额及IPv6等保留项仍按各自缺口阻断。H5未签收，Live未完成，未自动闭票或激活。
