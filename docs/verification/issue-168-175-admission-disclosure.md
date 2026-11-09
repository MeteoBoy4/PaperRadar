# #168 / #175：doctor 与日报共享分项披露

本台账覆盖共享 AdmissionProjection 的结构化行、中文片段与只读 pi-exec 诊断。
新增测试独立未绑定，不扩大历史 required、组回执或固定分母；旧 scope 与中央成员/哈希保持。
新消费闭包、文档分类与必要重绑由 #176 收口；本票不发布 A1–A10 或完整门禁结论。

## 公共 seams 与独立分母

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_doctor_admission_disclosure.py` | 8 | 空论文报告仍显示缺口、健康且披露 unknown、原 not_assessed/verified 与依据/范围/时点、混合缺项和精确到期、待撤销、时钟回退、Pi token=0 与请求下界来源/窗口、账本失信映射、Read 不借 Screening 格 |
| `tests/test_doctor_live_admission.py` | 9 | 真实临时账本与两格正式 CLI 健康退出 0 与真实 cache 成员漂移保留原状态/分项原因；六类必要项/失信退出 2；披露项待撤销不独立阻断；禁止凭据内容读取、子进程、网络与 helper，文件树和业务库逻辑不变 |
| 合计 | 17 | 独立未绑定工程覆盖 |

collect-only 已核对 17 节点，人工预期未从生产登记或执行结果反填。
既有独立 `tests/test_doctor_pi_exec.py` 保留 31 节点及全部只读、冷导入、敏感内容与失败断言；
仅将 5 个“固定无证据”旧预期改为本票明确要求的 invalid/ledger_untrusted，新增 result 断言。
没有修改冻结测试、历史计数或 required 组。

## 权威与展示边界

- `doctor.admission.admission_rows` / `render_admission_fragment` / `projection_checks`
  只消费唯一 AdmissionProjection，不维护另一份能力分类、期限或资格判定。
  result 四态与 evidence 三态分字段，原核验状态在 original_state；缺原记录显示 absent。
  当前 use/call_site、basis/scope、evidence_at/verified_at/expires_at、接收/激活/撤销、适用性、来源与下一动作保留。
  披露型 unknown 可同时 result=passed，健康和空论文报告不省略其行；不适用不独立阻断。
- pi-exec 延续原 Screening 快照范围，当前档位 boundary/value 分别构造请求，两格与工程必要项
  均通过才 executable=true / 退出 0；Read 此命令未选择、未诊断的说明始终可见。
  公共片段也支持 Read 请求，测试确认不借用 boundary 的原记录，不将未选 Read 归为 D3 不适用。
- 正式路径复用 `build_admission_request`、`recheck_admission_request`、`AdmissionGuard.check`
  与共享 `unavailable_projection`；读取失败为 invalid/ledger_untrusted，时钟原因保留。
  不调用 guard.tighten、时间打点、prepare_launch、认证刷新、Pi 或网络，不写账本/待撤销意图。
  transient 只读安装保护限于本地整树核验，不持执行生命周期保护。
- `UsageDisclosure` 保留请求可证下界及观察层/来源/窗口、精确请求数 unknown 与 Pi 自报 token。
  隐藏重试/预热/刷新仍可能不可见，缺失或 totalTokens=0 不代表零成本。
  Apport/core 仅消费按次绑定投影，不新增独立长期漂移诊断。
- 片段不参与论文选择，不计入每日五项/全文三项；本票没有实现整套日报。
  B 首个日报票验收最小/健康/空日报嵌入，H 承接完整日报。

正式 CLI 测试复用 #173 的真实临时计划、受保护账本、receive/activate 和共享 loader。
OS 站点观察固定为当次只读快照，隔离并行 pytest 对共享 /tmp 祖先元数据的干扰；
安装树、凭据元数据和 stat-only cache 基线仍经真实 local_binding_components 计算。
这些替换限于测试 OS/时间/helper 边界，产品没有信任根、证据、工程放行或 pytest 授予参数。

## 红绿与开发验证

首切片因 doctor.admission 模块缺失出现 red；全局失败检查项因 projection_checks 缺失出现 red；
用量来源/窗口新字段因接口缺失出现 red；正式健康 CLI 先以原始固定 evidence_missing 退出 2，
接线共享构造与权威后变为退出 0，同时保留 unknown。
组合首次捕获 fixture 自身新建目录/并行测试改变 cwd 祖先元数据，修复只稳定测试 OS 观察，
没有减弱产品绑定或当前覆盖。最后以真实 cache 成员变化捕获过早 recheck
将分项 binding_drift 折叠为全局失败的问题；修复先消费权威投影，仅在可执行时
只读 recheck，因此已拒绝分项仍保留原 verified 和精确原因。旧诊断组合的 5 个原因预期失败按本票新契约更新，节点不减少。

最终相关组合：62 passed in 42.85s，退出 0，包含上述新增 17、旧 pi-exec 31、
doctor readonly 7、共享 loader 4 与 D7 3；无 skip、deselect 或 incomplete。
随后结构化行补充当前 use/call_site，新增 17 与 basic/config 冷进程回归合计
52 passed in 32.63s（退出 0）；没有增加分母。
精确下一动作与真实 cache 漂移修正后，新增两模块最终 17 passed in 12.59s（退出 0）。
局部 Ruff、10 文件格式检查与 strict mypy 10 文件通过，git diff --check 通过。
CLI compatibility：59 passed in 106.20s，入口退出 0；含 uv 总耗时 106.80s。
它是开发期检查，不替代最终树完整门禁。

## 固定材料与后继责任

以 integration `8a1c1941fac9919479855611ff68f0cab539f485` 为显式 base/target 的只读 scope 审计退出 1，
baseline_issues 为空。既有 #170 两条 source_support baseline_drift 为 cli.py 与 contracts/schema.py。
本票唯一已登记 current_change 为 pi_supply/cli.py 的中文帮助，属于 mechanical source_support：
直接 A4/A10，下游 A5–A9；没有修改成员、分母、旧登记用途或中央哈希。
审计针对当时 dirty 开发树，不是最终树正式验收；所有三条漂移交 #176 精确重绑。

新增 doctor/admission.py、两个独立测试及本台账，连同既有 doctor 三模块、pi_supply 帮助、
README、doctor Contract、规格 §14 的完整消费闭包由 #176 收口。
`issue-167-index.md` 只原地更新 §6 一处当前机制现状句；其余历史字节及 #167 原探索证据保持。
既有 Frozen Contract、receipt v1、业务 migration 与 D7 策略/清单未改。

未运行完整 check-offline、sudo、真实激活、封印部署/卸载、认证、模型或网络调用。
合成测试不证明真实 root/Sudoers/helper、供应商能力或实际日报嵌入；G2/G3/G4 保持。
原生 #175 在本次验证时仍 OPEN，上游 #171 已 CLOSED；最终远端回帖与关闭由主代理按用户新授权处理。
