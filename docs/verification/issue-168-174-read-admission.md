# #168 / #174：Read 正式分项准入覆盖

本台账覆盖 Read 正式入口的三检查点、与 Screening 共用的分项权威、独立业务资格、
领取前零副作用、收紧持久性及 D7 策略升级。新增模块独立未绑定，不扩大历史 required、
组回执或固定分母；旧 scope 与中央成员/哈希不改，消费闭包及文档分类交 #176 收口。
本票不发布 A1–A10 或完整离线门禁结论。

## 公共 seams 与独立分母

测试边界采用本票 AC 已授权的 `ReadExecution.run_attempt`、`ReadTasks.task/analyses`、
共享 `load_admission_evidence` 投影，以及产品不可达 / D7 开发守卫；不新增产品授予参数。

| 独立模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_read_live_admission.py` | 53 | 旧工程别名动态/AST 不可达；准备后硬到期；21 组件漂移及 helper 失败/重启；领取内 11 类时钟/来源/水位线/撤销/恢复/观察退化且不重扫树；回滚后 helper 可立即获取业务写锁；已派发跨期继续结算；打点失败、协议失败、实际模型不符收紧；四类必需缺口不刷新；正文质量/租约/两次预算/代际/输入预算独立；实验根不获生产消费；业务恢复不退款/不复活；内容失败保留安全修正机会；披露型待撤销不独立阻断 |
| `tests/test_consumer_live_admission_consistency.py` | 6 | 同一冻结账本驱动两个正式消费者，对应同格输入的来源、分项状态、适用性与原因等于共享投影；双格有效、分别单格有效、仅 high、未激活及单独撤销 Read；格/档不互借 |
| `tests/test_live_admission_source_guard.py` | 4 | 33 文件显式清单与策略一致；同策略源码改动及仅重绑清单反例仍失败；新增旧策略清单原字节归档守卫。原三节点与断言保留，本次追加一节点 |
| 合计 | 63 | 独立未绑定覆盖，不进入旧分母 |

collect-only 已核对独立分母：Read 53 + 一致性 6 + D7 4，共 63 节点；预期数为人工登记，
收集只核对，不从产品登记或实际输出反填。
真实临时受保护账本/receive/activate、固定观察和模型能力来自 #173 的
`tests/screening_live_admission_support.py`；只在测试侧替换 OS 来源、时间与 helper 进程。
19 项必需能力仍由该支撑按已接受 ADR-0052 手工枚举，合成协议对端不证明真实能力。

旧工程 `test_read_execution_admission.py` 18 节点与 `test_read_execution_resources.py`
7 节点原断言、数量保持，只将三处工程注入改用测试侧完整边界替换；
`tests/read_execution_support.py` 保留旧三布尔负例调用原 `admit` 及原原因。
产品 `_evidence_for` 留作不可达守卫，正式入口不读取它；没有工程模式、
pytest 检测、合成授予开关或公开证据参数。

## 行为与验证

先以正式入口回归捕获旧 alias 可达的 red，接入共享权威后转绿。
实际模型不符的独立回归随后捕获「已结算但下一次仍复用旧能力」的 red；
修复先保留原 `model_mismatch` / 一次 attempt / 一次预算结算，再于事务外请求收紧。
内容 `output_invalid` 保持既有两次安全修正纪律，不一概撤销能力。

三检查点分别为刷新前完整绑定及共享判定、准备后完整重绑及共享判定、
领取事务内廉价重读当前受保护小观察/时钟/账本/来源/水位线及同一判定。
事务内只抛非 ValueError 的专用拒绝信号，穿过回滚后映射既有 evidence_missing，
不会被业务事务误分类为 corrupt_reference；helper 与收紧意图均留在事务外。
相关回归核对完整本地观察恰好两次，无领取、失败行或新增分析；
正文质量、根用途、完整帧预算、任务代际、租约、两次尝试和显式 retry 的原权威不变。

验证命令均使用 `uv run --offline --locked …`、
`PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`、pytest `-p no:cacheprovider`。
开发中第一次 UV_NO_CACHE=1 命令在 pytest 启动前因离线缓存缺 mypy wheel 退出 1；
去掉 UV_NO_CACHE，使用既有缓存离线同步成功，没有联网或改 lockfile。
一条组合命令误写不存在的 `tests/test_live_evidence_service.py`，pytest 退出 4、零测试；
改用实际 `tests/test_live_evidence_loader.py` 重跑，不将该失败命令算作通过。
早期局部类型/格式检查和新一致性测试的 tuple 顺序假设已修正；完整绑定按组件映射比较。
定向开发期 deselect 不计验收通过，以下最终组合均不接受 skip/deselect/incomplete。

功能组合：197 passed in 441.37s（退出 0），覆盖新增模块、全部旧 Read 执行、
Read 前置/租约/恢复、Screening 三检查点、完整绑定及共享 loader。
随后新增事务外 helper 写锁回归单节点 1 passed in 3.45s（退出 0）。
两次均无 skip/deselect/incomplete。
合入 #175 当前 integration `bd1598e759e9ffcd8d14fe938e76e19dfb994b32` 后，
Read/D7 最终独立 63 节点 + doctor 独立 17 节点 + 旧 doctor 31 节点组合
为 111 passed in 197.61s（退出 0），无 skip/deselect/incomplete；
合并树 collect-only 再核对独立 63 节点，退出 0。

CLI compatibility：首次 59 passed in 128.48s（退出 0），入口含 uv 总耗时 129.33s；
合入 #175 当前 integration 后，59 passed in 123.51s（退出 0），总耗时 124.29s。
局部 Ruff 通过，8 文件格式检查通过，strict mypy 8 文件通过，git diff --check 通过。
未运行完整 check-offline，未写正式回执/run_id。

## D7 与 #172 承接

Read guarded service 已接入正式权威，因此准入策略显式升为 `pi-admission-v2`。
当前 33 文件清单为 `tests/fixtures/live-admission-source-guard-v2.json`，其 format_version
仍为 1；文件名的版本标识区分清单代次，不把 JSON 清单格式升级冒充策略身份升级。
当前清单 SHA-256 为 `aa3cb3836b4072a8e6d66b6c99f3181f901f90aa8015e59dc24a3c82d8244ac4`。
原 `tests/fixtures/live-admission-source-guard-v1.json` 原字节保留作为 pi-admission-v1
归档向量；原摘要锚 `695c4e9bc933b06bb211663796bb1dd89db52d000881c8590e82ac4e57e1a2f0`
保持，REVIEWED_POLICY_MANIFESTS 只追加新策略键。新增守卫检查归档实际字节。
运行时只绑定策略版本，不读源码清单、不做 PaperRadar 源码哈希。
既有 `pi-launch-1.4.0-v1`、`pi-landlock-v1`、1.4.0 RPC profile、argv 与 settings 不变。

#172 继续使用 `current_binding.build_admission_request`、`recheck_admission_request`、
`local_binding_components` / `site_binding_components` 与 stat-only metadata_digest，
签名与 #173 交接相同；采集本地组件必须使用产品 uid，不能把 root 的凭据属主观察冒充产品观察。
封印采集必须使用最终 `pi-admission-v2` 启动上下文身份；旧策略证据不能跨该组件漂移借用。
站点采集仍不能补供应商/RPC 必需能力；真实部署审阅、sudo 和激活仍由 G2/G3 承担。

## 固定材料与未验边界

以 integration `8a1c1941fac9919479855611ff68f0cab539f485` 为显式 base/target 的
只读 scope 审计退出 1，baseline_issues 为空，仅有 #170 的 cli.py 与 contracts/schema.py
两条 source_support baseline_drift；本票无已登记 current_change 漂移。
合入 #175 后以当前 integration `bd1598e759e9ffcd8d14fe938e76e19dfb994b32`
为显式 base/target 再审计，退出 1，baseline_issues 仍为空；另有上游 #175 的
`pi_supply/cli.py` 一条 source_support baseline_drift，共三条，均交 #176 收口。
本票仍无已登记 current_change 漂移。
旧 scope、中央哈希、回执格式、业务 migration、正文 evidence 表和历史回执不变。
本票 Read Contract 未列旧活文档，新增测试/清单/台账与完整消费闭包交 #176 显式分类审阅。

实际模型不符的 Read 收紧已覆盖；Screening 同类接收层失败是否也须收紧交全系列一次
code-review 与单个新鲜修复者核对，本票不改 Screening 任务内核或另开任务。

本票未执行真实认证、模型、网络、sudo、证据激活、封印部署/卸载或 root helper。
离线合成正例只证明共享判定消费与工程结算，不证明真实站点或供应商能力。
受保护当前观察仍须来自实际部署采集；helper/磁盘故障继续拒绝，
收紧意图无法落盘时不能声称跨重启持久成功。
原生 #173 由主代理按最新授权已关闭；#174 保持 OPEN，
由主代理在合入并验证后统一回帖关闭，本实施分支不写远端。
G4 完整门禁及最终收口仍由原流程承担。
