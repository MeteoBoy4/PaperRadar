# #168 最终两轴审阅统一修复与离线覆盖

本台账覆盖 `b133d4e...83a60f2` 两轴发现后的同一 fixer 修复，不扩大旧 required 或历史分母，
不修改旧 scope／中央成员或哈希。代码实现不替代所有者实际 v4 部署、权限／cutover／新证据激活，
也不替代 G4 同次完整离线门禁。#176/#168 未在本次修复中关闭。

## 发现与公开行为

| finding | 修复与独立红绿信号 |
| --- | --- |
| Standards S1 / Spec P1：bootstrap源换链泄漏 | 四件来源在密码边界后换成synthetic0600 marker链接，修前marker被复制到staging后才SHA拒绝，4节点red。新入口内嵌确切字节，经stdin冻结并复核，root不再打开用户来源；大于128KiB的payload亦可执行。旧包原字节保留。 |
| Standards S2 / Spec P2：Screening接收层MODEL_MISMATCH漏收紧 | 正式RPC fixture先结算MODEL_MISMATCH但仍可执行而red；保留原结算和一次attempt，事务外只收紧MODEL_IDENTITY，重试不再领取，独立site分项保留。helper能立即BEGIN IMMEDIATE证明未持业务写事务；Read同口径。 |
| Standards S3：readonly复核后沿用旧许可 | 三格完整fixture复核抛observation_stale时原输出仍executable=true而red；改用共享unavailable_projection，executable／qualified／doctor片段同时拒绝。 |
| Spec P3：首次丢失无sources不能持久收紧 | 两消费者×receipt或CurrentObservation物理丢失4节点red；无sources时按闭合格记录截止时点意图，并请求revoke-use。helper只根据root已登记receipts追加本格旧撤销，不读丢失inbox；恢复原字节不能复活。 |
| Spec P4：普通pending可删／截断／回滚解除拒绝 | 攻击前有真实可执行投影，helper失败后delete／truncate／rollback3节点red。按已接受ADR-0056改为root所有、内核只追加的独立日志；攻击破坏或来源失信后共享ledger_untrusted／pending拒绝，OS模型另核同uid各syscall拒绝。 |

资格自然缺口与真实失败分开：60秒观察租期结束、自然到期、未测或未激活只拒绝当次；
两个消费者×4条件8节点先red后green，同事实新鲜观察可恢复适用性，不续verified_at或翻转真实撤销。
未知模型能力不撤销无关已核site分项。物理来源丢失／失信、已知漂移或实际运行失败才不可逆收紧。

## 初始化与所有者边界

初始化+a前暴露0660 inode的竞态已由OS边界模型red复现；改为先持久封闭目录0700，
完成首记录／权限／+a／fsync／fd复核后才公布0755。失败保留private部分状态，不自动补完或重建。
cutover在受保护事务失效旧活并撤销全部旧六格，保原主张、verified_at、失败、stopped和业务预算。
新受信计划／实际新证据必须由本人重新显式激活；日志缺失不是“旧失败不存在”。
日志满、损坏、未知版本／ABI或属性失信均拒绝；I/O失败仍尝试helper，未成功不得假称持久。

owner安全回执原来直接Lifecycle/evaluate绕过否定日志，公开负例先red；现root只读共用相同core，
raw_active与当前active／qualified分列。集成包冻结新计划选择、三次本人手动短ID、产品uid实际操作拒绝，
以及仅子进程NNP使固定sudo helper失败后的持久意图、新进程读取、撤销、恢复和最终再活。
只读平台／CAP／挂载／属性预检尽量在归档旧runtime前拒绝，不能替代真实+a支持证明。
任何未知／失败／中断不写completed安全回执，不自动清理或放宽。
具体可审步骤见[owner方案](../../intent/review/issue-168/closure-owner-plan.md)。

## 独立模块与固定数量

| 模块 | 人工节点数 | 覆盖 |
| --- | ---: | --- |
| `tests/test_final_admission_regressions.py` | 20 | readonly1、Screening结算1、四来源换链4、两消费者首次丢失4、helper无来源1、大payload1、独立资格8 |
| `tests/test_protected_admission_intents.py` | 39 | 文件破坏3、内核syscall模型6、失信／缺失／满等10、cutover新激活1、fsync2、helper无provision1、owner同权威1、集成包1、初始化竞态1、owner成功／中断2、部分封印1、未知ABI1、归档前拒绝3、真实预检谓词OS替身6 |
| `tests/test_live_admission_source_guard.py` | 6 | v4显式39源码清单、同版本改源码／重绑拒绝、v1/v2/v3原字节归档锚 |

旧模块节点数保持：Screening41、Read53、consumer一致性6、披露8、doctor9、closure25、
ledger15、lifecycle36、loader4、helper10、G2入口9、部署8、检查点10、升级27。
全体新消费闭包31模块478节点的当前人工表见[集成台账](issue-168-176-live-admission-closure.md)。
collect只核对这些人工数量，不反填、跳过或扩大旧组结论。

旧Read事务外收紧用例曾以自然到期却要求revoke，与D4冲突；只把刺激改为物理来源丢失，
保BEGIN IMMEDIATE、tick+revoke及零attempt断言，新自然到期回归补位。主代理独立核对该diff。
日志初始即存在后，原is_file断言改为公开投影pending_revocation／executable，保原attempt／failure断言。
工程fixture仅把尚未显式替换的真实ledger／log／helper改为临时拒绝源，防synthetic空sources路径触发真实sudo-n；
现有protected fixture与原业务断言不变，主代理亦独立核对该边界。固定旧登记未被借此改写。

## 验证与尚未验证

- 初始化前阶段：49passed／36.16s、176保留组合96passed／33.61s、完整非特权封印构建8passed／5.71s。
- P4／owner／部署组合123passed／53.77s；v4清单、P4当时33、176原25、Frozen Contract及链接共70passed／19.82s。
- 最终消费者＋共享权威＋doctor＋D7组合：**143passed／211.31s**，无skip或deselect。
- 实际受影响旧工程模块：`test_pi_execution_service.py`32＋`test_read_execution_admission.py`18，**50passed／64.53s**，原断言保留。
- 最后只读预检／包构建改动：3＋8共**11passed／6.45s**；后续仅增加OS工具替身谓词覆盖与定稿校验，不重跑无关消费者。
- 定稿新安全39＋D7六＋链接四＋Frozen Contract二共**51passed／4.17s**；只读预检谓词OS替身六节点**6passed／0.79s**。
- Python统一offline/locked；**31个改动Python文件**的Ruff／格式／mypy通过，**31模块／478节点**逐模块collect核对通过，git diff --check通过，不发布A1–A10结论。

没有业务migration或表定义变化，账本schema1／receipt v1字节保持；Frozen Contract回归已通过。
旧v1/v2/v3清单及摘要锚保留，新v4不继承旧绑定资格。ADR-0055仅状态行加反向指针，
ADR-0056只改接受状态；正文与所有者受审草案比对保持。
旧三源11登记漂移、精确S3／消费闭包候选仍交主代理按最终integration HEAD重建；没有自动写回旧哈希。
兼容组合按主代理要求与登记授权在最终树串行完成，本分支未机械重复已知all65failed／111passed，
不能将旧失败一概归因或声称兼容全绿。未运行完整离线门禁。

所有OS特权／syscall结果在本台账中均为临时无root模型，未执行真实sudo／+a／cutover／采集接收／撤销恢复或激活，
没有认证／模型／网络或读取真实auth/cache/log正文，没有compile／写EXP2或重装Pi。
实际v3非空站点激活仍是历史事实；不能证明v4。最终主树重建新升级／owner包并审阅执行后，
才可保存真实root安全回执；模型／RPC／IPv4／observer和Live/B/H/I承接继续按原边界保持。
