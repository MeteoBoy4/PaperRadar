# #168 / #171：证据生命周期与共享读取覆盖

本台账覆盖独立账本上的证据激活、不可逆撤销、时钟水位线、历史合并恢复，
以及消费者共用的读取／分项投影、受保护当前观察和认证/cache 成员元数据摘要。
新增测试独立未绑定，不扩大历史 required、组回执或固定分母；
旧 scope 与中央成员／哈希不变，新增消费闭包和文档分类由 #176 收口。
receipt v1、既有 Frozen Contract、schema1 表定义、业务 migration 与 #167 历史证据原字节保持。

## 公共 seams 与覆盖

| 独立新增模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_live_evidence_lifecycle.py` | 36 | scoped／幂等激活、不可逆撤销、21 组件依赖影响、原时点与精确到期、五路径时钟回退、确认／格边界、历史恢复与损坏拒绝 |
| `tests/test_live_evidence_loader.py` | 4 | 真实账本共享投影、helper 失败持久拒绝、新旧 loader 边界、完整 required 集合与披露 unknown、损坏意图拒绝 |
| `tests/test_live_evidence_owner_cli.py` | 7 | 完整脱敏审阅／短 ID、过期观察与确认等待、实际激活 show、两处新命令冷帮助禁外部 I/O |
| `tests/test_live_evidence_tightening.py` | 10 | helper 动作／参数白名单、账本不可读时仍持久记录并投影待撤销 |
| `tests/test_live_evidence_observation.py` | 7 | 固定受保护来源、完整绑定／组件、UTC／未来／60 秒新鲜度与纯只读 |
| `tests/test_live_evidence_baseline.py` | 5 | 只打开目录 fd、不读成员内容，新增／改名／替换／权限变化与软链拒绝 |
| 合计 | 69 | 独立未绑定工程覆盖 |

支撑 `tests/live_evidence_lifecycle_support.py` 只构造临时 OS fixture 和合成计划／回执。
测试私有替换默认 OS 来源／当前时间／helper 子进程边界；产品没有 uid、信任根、证据或工程授予参数。
测试不运行 sudo、真实激活、认证、模型或网络，不使用用户库／真实凭据。
真实 root、sudoers 与封印来源效果仍须最终现场验证。

## 红绿与开发验证

按 TDD 公共边界逐切片先失败，再做最小实现：激活模块缺失、恢复入口缺失、固定观察缺失、
完整 loader 请求不支持、show 写死 false、账本不可读导致待撤销未落盘，均经过 red→green。
历史恢复回归另外捕获旧 history_received 抢占最新失败事实：修复保留原接收时点／原序，
在线 received 优先，新的 unknown 不回退到旧 verified。损坏 received_at 的 naive／早于原验证时点
同样先失败再改为 ledger_untrusted，防止恢复选择受损坏时间影响。
stat-only 基线接口也由缺失模块的 red 开始实现。

新旧功能组合实测 273 passed in 92.96s（退出 0），包含当时新增 67 节点、全部 Live 分项／回执相关测试、
旧 Pi admission/service、Read admission/resources 和 storage migration 一致性回归。
随后新增两个损坏时点回归及严格受控原因映射，相关 lifecycle＋ledger 为 51 passed（退出 0）。
最终新增六模块 69 节点经独立 collect 核对，与既有 ledger 15／纯 reader 2 组成 86 passed in 2.16s，退出 0。
CLI compatibility 为 59 passed in 116.79s，入口退出 0、含 uv 总耗时 117.46s。
无 skip、deselect 或 incomplete；不以开发检查发布 A1–A10 或正式门禁结论。

schema1 未增加表或修改列；既有 `test_ledger_schema_is_separate_and_newer_version_is_never_written`
继续验证版本、列、DELETE journal 和更高版本拒绝，新 receipt 快照一致性测试仍通过。
业务 `test_storage_migrations.py` 已在上述组合运行，未推进业务 head。
局部 Ruff、23 文件格式检查与 strict mypy 23 文件均通过。
本票只运行 CLI 触发兼容，不运行完整 check-offline、不写正式 run_id。

## 固定材料与漂移

以 integration `dd08fc15411b12840653d8c5b1424e7eb4d19098` 为显式 base／target 的只读 scope 审计退出 1，
baseline_issues 为空；只发现 #170 已带入的 `src/paper_radar/cli.py`、`src/paper_radar/contracts/schema.py`
两条 source_support baseline_drift。本票没有已登记 current_change 漂移，未重绑旧材料。
后继 #176 承接这两项原漂移及本票新增生命周期／观察／基线／helper、测试、支撑与本台账的完整消费闭包。
开发审计是当时本地 dirty 树的诊断，不是最终树正式验收或敏感确认。

## 后继接口与未验范围

- #173／#174 通过 `pi_execution.admission.load_admission_evidence(AdmissionRequest, now=...)`
  或直接使用 `live_evidence.service.load_admission_evidence`，得到同一个 AdmissionProjection。
  旧 EvidenceBinding 缺完整身份／准入用途，继续返回 None；两 service 的私有别名及正式三检查点／静态不可达守卫
  由各消费票与接线同时维护，不能添加产品工程模式、授予参数或 pytest 环境放行。
- #173 集中构造完整当前执行绑定；#175 doctor 复用相同只读构造和共享投影，不能复制能力要求。
  `AdmissionRequest` 没有 privileged_components 或注入证据参数；当前覆盖必须来自实际观察。
- #172 封印采集器写固定 `inbox/current-observation.json`，使用 `CurrentObservation` 与 canonical_bytes；
  当前完整绑定的所有组件摘要、checked_components 与 UTC observed_at 见 Contract。
  owner activate 通过 `load_current_observation` 读取，确认后再次核相同观察及 60 秒新鲜度，
  这不是原能力期限或 verified_at 的重计时。
- #172 接收基线与 #173 当次认证/cache 观测统一使用 `baseline.metadata_digest` 的 auth-cache-stat-v1 算法；
  固定根顺序、stat 字段、容量／深度上限及无内容读取规则见 Contract。
- `service.request_revocation` 先 fsync 用户态追加意图，再请求固定 helper；只有收紧，失败仍拒绝并显示待撤销。
  `request_time_tick` 只让固定 helper 用自身墙钟打点；消费方不能将失败当成已记录。
  helper 实际安装及 sudoers 由 #172 提供，授予始终归所有者输密码的封印入口。
- 独立 backup／restore 只合并受保护历史，保留在线撤销和最大时间、失效全部旧激活；
  不覆盖损坏在线库，不连接业务库，不清 attempt／预算。直接 root 替换整个信任根仍在 root 篡改边界内。

不宣称消费者正式执行、doctor／日报嵌入或真实现场完成；G2 脚本审阅、G3 实际激活和 G4 完整门禁仍保持。
原生 #170 仍 OPEN，本票按用户本地串行计划消费已实现上游，不擅自回帖、关闭或修改任务关系。
