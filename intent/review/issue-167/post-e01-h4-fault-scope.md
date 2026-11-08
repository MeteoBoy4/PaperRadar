# #167：E01之后的H4剩余故障范围裁定材料

## 已有依据与本次裁定边界

[E01已通过并恢复](../../../docs/verification/issue-167-e01-result.md)：外部SIGINT触发真正KI、同对象经过公共run_call及prepare/use_install后验、S/CG/DB/host/目录收尾完整。token用量unknown，旧e93/d5的unknown不改。此前[合成工程控制](../../../docs/verification/issue-167-offline-fault-engineering.md)覆盖pump与清理位置的KI，以及一次真实300秒本地对端截止；它不等于实际Pi网络挂起或供应商迟延。

原票H3写“外部SIGINT/KeyboardInterrupt”，规格§7.7/§8.3没有明确要求两个独立触发来源；[原候选计划](field-plan.md)把E02设计成直接注入，且明确各轮另批。不能由候选方法自动增加原强制要求，也不能由agent自行删除E02或记passed。以下差异成本已由两项fresh只读复核；所有者随后明确选择K2/T1。

## 所有者裁决：K2 / T1，只有准备授权

K2：原票的外部SIGINT/KeyboardInterrupt按一条要求处理，本阶段采用E01实际KI与既有pump/cleanup合成KI工程事实作为有限依据，不另备E02。确定点直接注入来自候选计划，增量为冗余确定性；实际Pi的该直接注入形式保持not_assessed，交H5明确范围与后继，不记passed。离线合成KI用例继续作为回归门槛，不删除。普通产品CLI、任务租约及全部异常时点仍未证明。

T1：先准备项目双向INPUT+OUTPUT无凭据合成正负对照，模型请求0；旧单向OUTPUT不当覆盖。机制须单事务切换并保存独立table/CG/完整规则引用，单边/未知归属unknown。具体新包另交H1，机制通过后真实合并案例仍另交H1/H2/H3，最多1 auth CLI＋1 prompt/model，不由本裁决直接执行。

未来真实声明仅为项目诱导双向DROP条件下的实际Pi公共monotonic300秒截止与清理；自然供应商迟延/真实供应商错误不因此通过。300秒前完成、早期连接错误或缓冲命中未触发均记未触发，不重跑、不加任务、不退款。恢复失败/late packet继续unknown并保留，所有者仅恢复，旧判据不降低。新H2按新owner输入或明确条件刷新计划，不沿旧过期/刷新声明。

以下K/T其它选项保留为裁决前比较，不是本轮实施指令或备用余额。

## 裁定一：是否另取E02确定点直接注入

| 选择 | 具体工作与新成本 | 可以增加的事实与保留项 |
| --- | --- | --- |
| K1：独立准备E02 | 新Case/指纹与单格包；最多auth CLI1、prompt/model1、Node2、直接KI注入1，外部SIGINT0。仍另交H1/H2/H3，无重发/退款 | 在确定SessionMeter.pump post-decode/pre-return点、无OS信号地直接raise真KI。E01异步到达只定位eligible窗口，未保存具体Python frame，所以此为独立增量；共用run_call finally主路径，并非新异常类型 |
| K2：本阶段采用已有有限KI依据 | 新模型请求0、宿主变更0；以E01实际KI＋已有合成补偿工程事实作有限依据 | E02 direct-injection实际Pi仍not_assessed，交H5明确有限探索范围/后继，不写E02 passed。普通产品CLI、任务租约、全部异常时点均仍未证明 |

如选K1，InjectionMeter应直接继承原SessionMeter，首个完整prompt/decoded ACK started/agent_start且未settled/closing/EOF窗口直接抛预建同一KI，不安装SIGINT handler、不等待root或伪造sigint_received。捕获仍在prepare作用域外、observer内并显式assert_complete；正常提前只在完整validator/EOF/settled/exit0成立时记未触发。公共后验覆盖KI、非目标异常或缺观察均unknown，不凑通过。

上述两路都不自动履行旧候选中“租约事实”措辞：当前实验走prepare_launch/run_call，普通read_evidence仍阻断，任务入口和租约需要独立工程/证据。

## 裁定二：实际Pi300秒与项目网络挂起如何取证

| 选择 | 新调用与前置成本 | 可声明范围与不能声明的内容 |
| --- | --- | --- |
| T1：合并E03/E04 | 先准备并另批无凭据网络机制验证（模型请求0）；通过后最多1 auth CLI＋1 prompt/model的新真实单格，仍另批H1/H2/H3 | 只取“项目诱导双向DROP条件下，实际Pi公共monotonic300秒截止与清理”。自然供应商迟延及真实供应商错误不因此通过 |
| T2：保留两例分开 | 网络机制仍先验证；自然E03最多1 CLI/1prompt，E04另最多1 CLI/1prompt，总上限2+2且逐轮另批 | E03若300秒前完成则未触发，不扩大任务或再试；E04独立声明项目诱导挂起。两个都不保证触发，不退款/补跑 |
| T3：本阶段保留有限探索 | 新真实调用0、宿主变更0；仅采用已完成合成300秒工程事实 | 实际Pi300秒/网络挂起继续not_assessed，由H4/H5明确接受范围、阻断对象及后继，不把合成事实改为真实通过 |

### 新网络机制为何不是原许可的直接延续

当前项目表只有OUTPUT约束。单向DROP输出不足以可靠挂起：小响应可能已进入接收窗口、Node或RPC缓冲，停止ACK后仍可能完成。候选需要本项目socket/cgroup、TCP443及应用可见池的INPUT＋OUTPUT双向DROP，其他流量默认保持；不改全机/路由器、不使用真实供应商IP。INPUT归属及效果目前只有本机nft文档依据，尚无实测，必须先无凭据合成正负对照和具体新H1，不能直接拿真实模型试错或认为旧规则已覆盖。

触发候选为首个非空decoded text_delta，且同批未terminal/settled/closing，仅存类别/计数/序号，不存正文。ACK/agent_start或packet不能冒充供应商收件；thinking_delta可能包含本地合成换段，text类别更明确。即使已有text_delta，缓冲也可能带完整结果；不停止读stdout、不暂停pump、不加大任务，正常完成仍记未触发。

规则切换必须事务化并保存独立table/CG/完整规则引用；单边切换或归属不明unknown，不能扩大drop范围。先清模型/CG再按原严格绑定恢复/撤规则；late packet或恢复证明失败仍unknown并保留材料，须owner仅恢复，不为使回收成功降低旧判据。

### 期限的固定源码依据

给定Pi1.4.0文档已先按docs/docs.json导航复核。源码core/http-dispatcher.js:3、68–82默认idle300000ms，core/sdk.js:195–203将它传为timeoutMs；openai-responses.js:144–152为SDK maxRetries0。Undici lib/core/connect.js:69默认connect10秒，所以连接前DROP的早期连接错误不是公共300秒证明。

OpenAI client.js:991–1023的fetch timer在headers返回后清除，stream另行读取；已有流的默认idle起点晚于Python总期限。公共300秒仍从factory前开始，不能从DROP时点重置。源码没有证明上游不会更早失败，只有实际公共TIMEOUT、monotonic耗时、挂起参照及完整清理均成立才登记有限结果；更早SDK/网络错误不得冒充该结果。

实际bundle核对到同值传播：chunk-MM3LKT73.js SHA `aa4c8b091657bda611f6fd58343561fa44cda1070ae4cd5dbd09ffe1d9a34aab`，provider openai-responses-I2TBW7OL.js SHA `3b0e4bfe22973f37cc66631d2bef550b1ab17cb1b4b2f2e10417ef13d128a56f`。这是静态可行性依据，不是网络挂起实测。

## 共用前置与仍需H5的事项

E01已经完成认证更新；新批次不得沿用执行前“08:10已过期、必刷新1”声明。新H2必须据新的owner输入，或明确条件计划：单CLI可能不刷新，也可能联网刷新/持久写；独立HTTP仍下界＋unknown，pre/post元数据快照、真实非空DB的CAS/追加恢复与S边界保持。不读取token来猜新到期时间，usage缺失不是零成本。

两项裁定都只是选择后续准备方向，不授权代码安装、规则/网络动作、认证/模型或信号执行；新字节必须另冻结并审H1/H2/H3。供应商实际effort、日期alias/账号限额、自然供应商错误、普通产品CLI/租约、产品接收/激活仍未因此通过，H5不自动完成。保留项的责任与阻断范围须所有者明确接受，不能由agent用“移交”替代本票完成。
