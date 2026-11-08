# #167：采用六格有限事实后的剩余案例准备

所有者已裁决[H4 A](live-six-exit-decision.md)。六格的RPC、业务validator、S文件观察、Pi报告usage可作后继输入，原整批仍unknown；[仅清理已闭合](../../../docs/verification/issue-167-live-six-cleanup-result.md)。本文件是新的准备矩阵，不是H1/H2/H3许可、调用余额或完成声明。单格E01已按[单次批准](e01-authorization.md)执行并恢复，见[结果](../../../docs/verification/issue-167-e01-result.md)；此前封印与离线验证见[待审包](../../../docs/verification/issue-167-e01-preparation.md)。E01已消费，不重跑、不退款；其余候选不继承此许可。

## 当前可独立推进

1. 无认证/模型的监督接缝：已执行一次原phase_gate(exit7)、atomic write与wait_exit，严格退出和unit/CG恢复成立，见[监督结果](../../../docs/verification/issue-167-live-exit-probe-result.md)。后续独立[18节点仅清理已完成](../../../docs/verification/issue-167-live-exit-cleanup-result.md)，原整轮仍unknown，不回写或重验服务。
2. 合成本地RPC对端的真实信号/异常/墙钟截止：已沿run_call/PipeSession验证一次外部SIGINT、两个真正KeyboardInterrupt位置及真实300秒截止，见[工程控制](../../../docs/verification/issue-167-offline-fault-engineering.md)。其工程事实与真正Pi、供应商迟延和任务租约分开，不替代下表案例。
3. 独立核对下表各主张的可安全触发方法及证据缺口。固定供给、产品启动策略/协议身份、原core/计数/出口终局不重开；没有默认增加调用。

E01执行前认证输入已由所有者重新核查：models-store仍为空、models.json缺失，先前“六格后已有可信cache写回”前提撤回；当时access过期，按批准计划联网刷新。所有者以精确时间窗/结构及排外声明将07:13持久更新归属e93批次，见[认证附账](../../../docs/verification/issue-167-auth-input-refresh-ledger.md)；不宣称具体CLI/HTTP1，不重复加算或退款。E01已有新认证更新，但新expires未读，未来不沿旧过期声明；按新owner输入或条件刷新计划另冻H2。后续保留credentials pre/post纯元数据快照和非空实验库真实CAS基线，不假定空库。

所有者已[裁决K2/T1](post-e01-h4-fault-scope.md)：不另备E02，实际Pi直接注入not_assessed，离线KI回归保留；无凭据双向过滤验证已由所有者执行并[通过恢复](../../../docs/verification/issue-167-duplex-result.md)，模型请求0；结果只限IPv4 loopback机制，最终post-stop原始快照未留存的限制明确保留。合并实际Pi300秒/网络挂起案例已按独立单次批准执行，[结果not_triggered_and_restored](../../../docs/verification/issue-167-t1-result.md)：双向DROP已发生，公共84.21秒stop_reason返回，300秒未触发；收尾完整，不补跑、不退款。自然供应商迟延/错误及300秒能力仍未因此通过；剩余范围已获[H4/H5有限接收及三修正](h5-acceptance.md)，原[待审候选](post-t1-owner-review.md)保留原字节；产品机制交#168，不自行追加调用。

## 下一真实案例的候选范围

| 主张 | 最小候选及上限（尚未获批） | 触发与停止条件 | 仍不能证明 |
| --- | --- | --- | --- |
| 外部SIGINT | E01已执行：1 auth CLI、1显式prompt、1模型exec、1外部SIGINT | 信号发送者在controller外；只向已绑定本unit/PID生命周期的controller发送一次SIGINT。按封印时点触发，检查无候选接收、清理、S完整性与CG回收；不重发 | cancel()不能替代外部信号；本机回收不能证明供应商计算停止 |
| KeyboardInterrupt | K2：不另备E02；新调用0 | 采用E01实际KI与合成pump/cleanup有限依据，合成回归保留；确定点直接注入实际Pi保持not_assessed | 不记E02 passed，不证明普通产品CLI/租约/全部异常时点 |
| 真实墙钟300s | T1单次已执行，public84.21秒stop_reason返回；300秒未触发，不补跑/退款 | 原monotonic截止；不得从DROP重置、不加任务/假时钟/重跑；提前结束/早期错误/缓冲未触发均未触发、不退款 | 只声明项目诱导条件下的实际Pi300秒，不证明自然供应商迟延 |
| 项目网络挂起 | 无凭据机制已通过；T1真实单格marker后双向DROP成立，INPUT19/OUTPUT11，完整恢复 | 新机制单事务、独立CG/table/完整规则引用；单边/归属不明unknown。实验phase恢复正对照与最终host恢复分开；最终CG空后严格核归属/late packet，不放宽回收 | 旧OUTPUT不当INPUT覆盖；本机DROP非供应商错误，packet/ACK非HTTP，用量缺失非零成本 |
| 真实供应商错误/刷新失败 | 优先在另外获批的自然调用中观察，不为此额外默认申请次数 | 未出现则not_assessed；不得损坏凭据、耗尽额度或发超额请求。没有独立HTTP状态来源时，不凭RPC错误认定供应商错误 | 本机SIGKILL、断网、合成响应均不能冒充真实供应商失败 |

以上每例的端点、材料、时点、PID绑定、超时、参数、请求计数下界/unknown、当前认证状态及恢复还需具体冻结，不能据本表执行。原四个候选4 CLI/4prompt只是计划数量，不是剩余获批额度。故障、取消、用量未知均不退款；当前access是否需刷新不能沿用旧过期声明，不能为判断而读取真实令牌。刷新可能发生及持久轮换窗口须进入每轮H2和停止条件。

所有者已选择同一项目诱导挂起观察300秒，证明范围仅“本机诱导双向DROP条件下的真实墙钟截止”，不替代自然供应商迟延/错误。具体新包另批；不得降低timeout、换模型、额外重复或修改产品启动策略凑通过。

## 参数、模型身份与限额的证据成本

fresh只读核查先按所有者给定Pi文档根的docs/docs.json导航，再复读models/providers/RPC及固定源码。绝对根为 `/home/meteoboy4/.pi/agent/install/releases/1.4.0/node_modules/@earendil-works/`：

| 固定材料 | 有限源码事实 | 证明缺口 |
| --- | --- | --- |
| pi-ai/dist/api/openai-responses.js，SHA256 `002f15414b7c7b62a32610a8a915bdf1a01eed930b8b45d7691e8a5c475fa9b5`，80–88、113–120、290–300行 | 当前ChatGPT OAuth分支不用configuration_update；providerThinkingLevel从请求options派生，reasoning.effort为请求侧映射 | 请求回显不是供应商实际效力确认；不能因六格均成功就填passed |
| pi-ai/dist/api/openai-responses-shared.js，SHA256 `eed025a4821b1e017dd024b930caf8fa11c7fe053a81efe11bd7d846fdc641d3`，499–541行 | finalizeResponse映射usage/id/status，没有将response.model或effort投射为可信模型/参数证明 | 只限定当前接缝，不声称供应商永远不可验证；optional responseModel缺失/不符不能私加alias白名单 |
| pi-coding-agent/docs/models.md及当前pi-rpc Contract | catalog、支持档位和映射可以说明请求准备；当前Contract明确请求回显与optional responseModel边界 | catalog上下文上限不是当前账号订阅额度；成功一次也不是限额核验 |

实际参数效力、日期alias与当前账号限额仍unknown。新的[官方资料研究](provider-authority-review.md)已取得精确模型、low/high公布支持及开源订阅OAuth的直接依据，公开资料已支持与当前运行验证分别登记；它没有补当前账号余额或日期映射。可由所有者提供不含秘密的账号界面枚举/重置时间声明；agent不自行认证访问。两次输出差异、耗时差异或长任务不构成充分证明，额外真实调用有成本且仍不保证消除缺口。

后续H4需在“接受本阶段这些bounded unknown、逐项保留阻断与承接责任”和“保持对应探索阻断、先取得独立权威材料”之间明确裁决；H4 A本身没有预先接受这些新缺口。不因准备文档或合成测试自行降低原判据。

## 任务租约与H5

正常六格实际走prepare_launch + run_call，实验DB只做配置选择及恢复；并非PiExecution.run_attempt。普通admission.read_evidence仍None，产品入口仍阻断，不能为现场故障patch准入。未来若声明租约/任务预算事实，必须明确实验task入口及合成数据库，与实际Pi清理分别证明，不能继承不存在的生产租约覆盖。

H5最小审阅材料需分别列明：六格有限事实；原整批unknown及清理闭合；新监督接缝的有限结论；各故障通过/未触发/未测；参数/alias/限额/供应商错误缺口的明确接受范围、阻断对象及下一动作；产品证据接收/人工激活/30天硬到期与漂移失效等工程。所有者未明确接受有限探索范围前，不以“移交”替代本票完成；H5也不等于产品激活。
