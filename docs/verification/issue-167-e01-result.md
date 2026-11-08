# #167 E01：外部SIGINT、实际KI传播与恢复通过

## 授权与身份

所有者批准并执行了[单格待审包](issue-167-e01-preparation.md)，批准范围见[过程记录](../../intent/review/issue-167/e01-authorization.md)。run=`4e01c7a3b962`，review-seal SHA256为 `ddce0ec03ecbb819d124c94d92babf1d4d75420dcd97ff6972bb6bf9152e3646`，manifest为 `fa93c2512eb380510186240704b20476d30209b5b34c57a5512e240e059bebde`。

受控results/owner-run.json SHA256为 `8344b3768ae2890af849767513885295ba06ddb095bb717d3791231efbaa93a7`，93465bytes。外层及内层均 **observed_expected_and_restored**，单格为observed_expected。fresh独立核对40成员、完整driver、两entry、生成cleanup、23材料及纯validate_result/reconcile_delivery均通过，没有重跑案例。

冻结plan内authorization=not_granted是准备材料的静态字段，不是执行许可来源；本轮许可来自上述所有者明确批准，不能用任意JSON或此字段自证授权。

## 目标与信号实际事实

本轮仅合成value/low，固定openai/gpt-6.1-sol、prompt_only/provider_default、chatgpt_subscription，模型argv/env及产品LAUNCH/pi_protocol未改。case UTC为2026-11-08 04:04:29.851716至04:04:39.522094，monotonic耗时9.670392192秒。

| 观察 | 实际结果 |
| --- | --- |
| 发送attempted / syscall返回 | 1 / true |
| 收到 / 有效 / 迟到SIGINT | 1 / 1 / 0 |
| marker / model factory / prompt完整写出 | 各1 |
| prompt ACK / agent_start序号 | 10 / 11 |
| decoded agent_settled / agent_end | 0 / 0 |
| 同一真正KeyboardInterrupt传播 | true |
| public terminate返回 | true |
| partial candidate accepted / normal candidate validated | false / false |

pidfd固定的controller PID/starttime/CG dev+inode在发送前重核；intent/delivery及marker引用与worker ready、独立CG binding、case fingerprint一致。信号只发目标controller，未向unit/进程组发送，不用cancel()代替。

这证明外部SIGINT进入实验controller的eligible窗口，handler抛出的同一真正KI穿过公共run_call及prepare_launch/use_install后验并完成清理。marker仅为decoded ACK/start观察，不证明RPC内核消费时点、供应商收件、具体Python frame或供应商计算已停止；不扩为普通产品CLI和任务租约通过。

tokens=null、token_status=unknown，不能当零成本。已消费本轮auth CLI1、prompt/model factory1和外部SIGINT1，不退款/补跑；独立模型/刷新HTTP仍下界0、上界unknown。没有凭中断假定上游请求取消或无额外计费。

## 持久认证目录pre/post

快照是受审程序对relative文件集合及mtime/size/inode/ctime的两遍稳定metadata观察，不读取内容。fresh第二项独立审查核对exact字段、27节点、unique inode、固定top4、cache边界、16KiB及journal引用一致。

| 区间（UTC） | 实际时点 |
| --- | --- |
| pre快照 | 04:04:33.795540–04:04:33.798744 |
| public prepare_launch（含认证） | 04:04:33.798939–04:04:37.158122 |
| post快照 | 04:04:37.158363–04:04:37.159809 |
| 观测到auth/root新mtime | 2026-11-08T04:04:37.113355939+00:00 |

pre/post均27节点，文件集合无增删。仅根目录与auth.json的mtime/ctime变化，inode及size未变；**没有观测到auth inode替换，不能把本轮写成已证明atomic replace**。exp2-installation-id不变；models-store四项metadata不变、前后size2；cache共23节点均无前后metadata delta。不能从这些结论推断瞬时全写史、内容未变或独立writerPID身份。

认证CLI完成、认证阶段allowed packet从0增至11，和计划联网刷新/持久更新吻合；metadata变化直接落在受控prepare区间内，不是刷新HTTP1或键值内容检查。模型临时树的store/cache事件不能混入此持久目录。此前“持久cache已写回非空”的前提仍撤回，不因本轮模型临时写入而恢复该前提。

本轮agent与元数据采集器没有读取新的expires值；实际认证CLI按批准读取/刷新并持久化OAuth。执行前“08:10:14已过期”只用于本轮起点，后续批次不能继承为当前事实；下一轮须有新的owner声明或明确条件刷新计划。认证目录持续保留，history/writer_identity仍not_assessed。

## S文件观察与规则

session/guard/terminal/cleanup均完整，session mutation0、unknown mutation0、settings严格语义成立；终态session及unknown成员0，独立directory_deleted=true、post-terminal assessed write0。终态baseline为regular1/directory3，auth store与model store各regular1，compile cache directory2/regular0。已知非session边界事件下界分别auth3、model3、compile1、control_settings12、store_lock30；不外推缓存内部全写史或整个attempt零写。

持密前IPC七类control允许/目标拒绝及backend初始化完成。8份完整kernel快照按独立binding验证，reject始终0：

| 阶段 | allowed packets |
| --- | ---: |
| created_deny / preauthentication_complete / activated | 0 |
| auth_complete_1 | 11 |
| before_external_sigint / after_external_sigint | 16 |
| signal_case_complete / post_stop | 17 |

post-stop未增加。绑定CG dev30/inode858166，table handle30，完整identity及handles随本地回执保留。packet不是HTTP/DNS次数；允许集保持应用可见fake-IP池及路由器DNS，IPv6not_assessed。本机不核上游最终映射/出口身份，不新增真实供应商IP主张。

## 数据库、退出及恢复

选择journal为original activation8→batch activation9→restore activation10；最终snapshot/root/supply/install语义与原选择相同，历史追加保留。主代理另以mode=ro/query_only/两表authorizer只读当前公共选择表，确认实际current activation10与报告一致、语义恢复；没有读业务/凭据行或写库。

严格退出记录gate write_complete、wait complete、CG空，卸载前manager active/exited/success、ExecMainCode1/Status0/MainPID0及空ControlGroup。恢复为host_policy_restored、table/unit absent、resolver before/after相同，restoration_stage complete、successful_artifacts_removed、永久账本保留。

fresh和主代理只读lstat确认代码/runtime两树、精确unit文件及CG缺失；普通用户manager查询也为not-found/inactive/dead、MainPID0、CG/fragment/drop-in空。当前默认Result不反推原成功，原退出证据来自卸载前投影。

永久ledger仅lstat：普通宿主用户核UID/GID0、0600、nlink1、46459bytes、inode1052845；默认工具的UID/GID65534映射不当实际owner。公开结果派生预期SHA为 `9c947614685ae2fc376a99263624aab21b7a3e6cafecba9fc11453be585bcb97`，不冒充agent读取过0600正文。原e93/d5回执SHA和unknown不变；本轮只读复核未读取真实凭据、进程环境、日志或core。

## 适用范围与后继

此结果仅支持该固定绑定、value/low、实验controller eligible窗口及其KI/回收路径。E02无OS信号的确定pump点直接注入、实际Pi300秒/网络挂起、真实供应商错误、参数效力/日期映射/当前账号限额仍未由本例证明。E01与既有合成KI的重叠和独立E02成本交H4，不由agent自动追加调用或将未测项改passed。

此前准备115项/相关176项验证保留原阶段，不登记为本轮重跑。本轮执行的是纯validator/规则/引用/metadata和独立只读恢复核对；新增结果独立未绑定，不扩历史分母/required/正式回执。链接/diff与固定scope审计随本次收口记录，未运行完整离线门禁。H5及产品接收/人工激活仍待，普通产品缺证据阻断、Live待探索保持。内部配置、认证元数据、绑定/回执及相关SHA仅留本地。
