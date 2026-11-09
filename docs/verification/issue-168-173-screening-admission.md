# #168 / #173：Screening 正式分项准入覆盖

本台账覆盖 Screening 正式入口的三检查点、完整只读执行绑定、事务外持久收紧与 D7 开发守卫。
新增模块独立未绑定，不扩大历史 required、组回执或固定分母；不修改旧 scope 或中央成员/哈希。
消费闭包与文档分类交 #176；本票不发布 A1–A10 或完整离线门禁结论。

## 公共 seams 与独立分母

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_screening_live_admission.py` | 41 | 正式入口不触及合成别名；准备后到期；21 组件漂移、失败 helper 与重启；领取内九类时间/账本/来源/观察退化且不重扫树；已派发不中止；打点失败、协议失败持久收紧与预算保持；必需缺项/未激活/已撤销/来源丢失零刷新；披露项待撤销不独立阻断；AST 不可达守卫 |
| `tests/test_current_execution_binding.py` | 1 | 真实本地 host/安装树/stat 基线；纯只读且不刷新；成员变化与显式代理变更改变身份；本地上下文变化不拼接旧特权覆盖 |
| `tests/test_live_admission_source_guard.py` | 3 | 33 文件显式源码清单与策略常量一致；同策略源码编辑及只重绑清单的受控反例必失败 |
| 合计 | 45 | 独立未绑定工程覆盖 |

collect-only 已核对 45 节点；人工预期不从生产登记或输出反填。
`tests/screening_live_admission_support.py` 使用真实临时受保护账本、计划/receive/activate 和共享 loader，
只私有替换 OS 来源/当前时间/helper 子进程。必需能力清单按 ADR-0052 手工枚举，未从生产登记推导正例。
fixture 可传实际组件和 boundary/value 两格供 doctor 复用；这些参数只在测试代码内。
产品没有 uid、信任根、合成授予、工程模式或 pytest 检测放行参数。

旧工程组合保留原断言与节点：`allow_synthetic` 现在在测试侧显式替换完整准入边界，
三布尔负例仍调用原 `admit` 并检查原原因；3 处工程测试仅迁移接缝调用，
Feed 对旧 reader 名称的导入改用 `load_admission_evidence`。支持 fixture 首次任务使用已登记 low 档，
不让旧 off 档工程材料成为产品授予规则，产品对未登记档位继续拒绝。
独立动态与 AST 守卫确认产品不读取 `_evidence_for`。

## 红绿与验证

按公开边界垂直推进：合成别名可达、准备后过期未复核、本地 host 未复核、
旧特权覆盖可被拼接、显式代理未绑定、领取前观察丢失/过期/变化/覆盖撤回等均先出现 red。
领取内拒绝还捕获原业务事务将 ValueError 误映射 corrupt_reference 的边界；
修复在事务内使用专用信号，回滚后映射既有 evidence_missing，未改任务模块或失败词表。

三检查点分别为刷新前完整绑定/共享判定、准备后完整重绑/共享判定、领取事务内廉价重读。
事务内只重读受保护小观察和账本，相关回归确认完整 OS/树观察恰好两次。
持久收紧与固定 helper 在业务事务外；失败 helper 不清理意图，不授予且跨重启继续拒绝。
实际协议失败保持原 attempt 结算；准入过期不新增运行中终止路径。

开发期功能组合 180 passed in 209.15s（退出 0），覆盖新三模块、共享 loader、
旧 Pi 纯判定/service/Feed/恢复/评审回归与 Read admission/resources。
随后补 D7 同策略机械重绑清单反例与披露项待撤销不独立阻断回归，
最终独立三模块 45 节点连同共享 loader 4 节点为
49 passed in 47.66s（退出 0），无 skip/deselect/incomplete。
该末次验证覆盖披露项只展示待撤销、仍以共享必需判定为准的最终修正。
完整相关组合首次暴露工程 fixture 漏替换新增小观察边界（22 failed / 158 passed）；
修复仅补测试侧 stub，原断言和节点不变，再运行相同选择。

CLI compatibility：59 passed in 122.32s，退出 0；入口含 uv 总耗时 123.12s。
局部 Ruff 通过，14 文件格式检查通过，strict mypy 11 文件通过，git diff --check 通过。
未运行完整 check-offline，未写正式回执/run_id；red 或开发期定向筛选不计为验收通过。
最终组合不接受 skip/deselect/incomplete 作为通过。

## D7 与后继接口

`tests/fixtures/live-admission-source-guard-v1.json` 显式冻结 33 个源码路径的 SHA-256，
以及准入 `pi-admission-v1`、既有启动/隔离策略和 1.4.0 RPC profile 常量表。
文件名 v1 表示清单格式；策略变化与新清单字节均须代码审阅。
测试内 REVIEWED_POLICY_MANIFESTS 保存只追加的策略版本→清单摘要锚，
只重算清单、不升版时也失败；后继增加新策略键，保留旧键摘要原字节。
运行时不读取清单或计算 PaperRadar 源码哈希；只把准入策略版本纳入启动上下文绑定。
Pi argv、settings、现有启动/隔离版本常量和协议档案字节保持原值。
#174 对已枚举 Read service 的正式接线必须显式升准入策略版本并审阅更新清单，不能略过守卫。

- `current_binding.build_admission_request(database, EvidenceBinding, *, use, credentials_dir, now)`
  返回 AdmissionRequest；不导入 auth/launcher/执行 service，不刷新、不建会话、不写账本。
- `recheck_admission_request(request, *, now)` 复核固定小观察的新鲜度、绑定和特权覆盖，
  不重扫安装/宿主/认证/cache；供 #174 的事务内检查点复用。
- `local_binding_components` 与 `site_binding_components` 提供 #172 共用摘要算法；
  认证/cache 固定为专用 credentials_dir 单根，stat-only；运行该本地观察须使用产品 uid，
  不把 root uid 的凭据属主核对冒充产品 uid 观察。
- `live_evidence.service.unavailable_projection(use, LedgerError)` 与 loader 共用受控失败原因映射，
  #175 无需另解释账本/时间/来源失效。
- `AdmissionGuard` 保存当次来源/水位线并复用唯一 loader；拒绝后在事务外请求收紧。
  当次来源丢失按已读来源保守处理；落盘失败不能声称持久成功，但仍不执行。

## 固定材料与未验边界

以 integration `6466ebec2f58cda971056f4f78f475f4e8abbaa8` 为显式 base/target 的只读 scope 审计退出 1，
baseline_issues 为空。只报告 #170 的 cli.py 与 contracts/schema.py 两条 source_support baseline_drift；
本票没有已登记 current_change 漂移，没有重绑旧材料。
本票源码、D7 新清单、测试/支撑、Contract 与本台账的完整消费闭包由 #176 收口登记。
旧 Scope、中央哈希、receipt v1、业务 migration、历史回执和 #167 原探索证据不变。

离线合成对端不是实际认证、模型或网络验证；未执行 sudo、实际证据激活、
封印部署/卸载、真实 root/Sudoers/helper 或真实供应商能力核验。
受保护当前观察必须来自实际部署采集；未取得有效、已人工激活的完整必需证据时继续拒绝。
磁盘无法写收紧意图时只能保证当次拒绝，不能声称有跨重启持久性。
G2 脚本审阅、G3 实际证据激活与 G4 完整门禁仍由原流程承担。
原生 #170/#171/#173 仍 OPEN；本票只消费已批准本地实现，不写远端或改原生关系。
