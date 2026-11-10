# #177 完整离线门禁回归修复

本台账是新工程修复记录，不改写既有台账或正式门禁历史。起点为
`8977713e123fcb49e0342a42be8ec07698030712`，本地目标 `integration/issue-177-live`。
本轮使用独立 worktree 与独立锁定的 35 包 `.venv`，没有复制或共享主树 85 包环境；
只做离线开发验证。完整离线门禁、现场准入和实际认证/模型均未执行。

## 根因与实际改动

1. Live evidence v2 扩展全局 `ContractVersion` 后，旧 A1 计划测试错误要求全局只有 v1。
   保留旧四契约精确集合、数量与中文帮助断言，改为明确断言计划版本仍是 v1，
   且命令只有一次 `--version v1`。未扩大旧 A1 计划或 required 集合。
2. 配置构造将“该类没有所选版本”的 `KeyError` 与构造失败混为一类。
   现在 `read:v2` 等未注册组合仍给“所选版本尚无权威契约”，保持旧配置拒绝、
   无部分登记和敏感内容不泄漏断言；Live v2 不授予其他契约 v2 支持。
3. 原内核摘要 `tuple(platform.uname())` 会懒求 processor，冷进程启动 `uname -p`，
   导致无副作用 guard 在打开 `/dev/null` 或启动进程时退出 97。
   改为 `os.uname()` 五个原生内核字段，并推进独立 admission v12；
   摘要维度变化不继承旧资格，launch 仍为 `pi-launch-1.4.0-v8`。
4. 旧 core 负例只 patch 父进程 `resource.setrlimit`，新 wrapper 已是独立解释器。
   现在经测试专用 OS spawn 接缝在真实 wrapper 内注入第二次及以后零 core 设置失败，
   保留 socket、ptrace、隔离与 exec 路径。故障记录精确核 `RLIMIT_CORE,(0,0)`，
   exec 日志证明 auth 失败时没有 peer exec，model 失败时只有先前 auth exec。
   真实 auth/model 正例仍核软硬限额均为零和父进程限额不变。
   auth 负例原因改为此真实握手边界的 `placement_exec_failed`，model 保持 `startup_error`。
5. 旧资源测试误把模型领取前的阻塞 wrapper Popen 当成真正模型执行。
   正例改在真实内核 exec-stop 后观察 `/proc/<pid>/cmdline`，核先 armed 后 model；
   真正 peer 就绪、原 lease FD 唯一继承、目录删除、mutation/history 与内容不泄漏断言保持。
   启动失败负例在 wrapper 的真实模型 `os.execve` 注入 `OSError`，核故障命中、
   `startup_error`、窗口完成与已 arm 资源删除，避免提前握手失败空过。
6. 冷 CLI 不继承 `service_inputs` 的父进程 monkeypatch；机器存在默认现场账本时，
   原“缺失 Live”用例会受真实旧记录影响。本轮诊断发现该隔离缺口后停止现场源探针，
   专用 `sitecustomize` 现在在 OS stat/lstat/open/SQLite 边界拒绝
   `/var/lib/paperradar/`，原 `ledger_untrusted`、凭据不读取、无进程/网络/写入守卫保持。
   新 D1 单独验证公开宿主采集无外部子进程，防止隔离补全后丢失原 uname 回归覆盖。

上述测试维护已获功能范围内授权；验收含义不变，由后续独立 reviewer 复核强度。
未改正式 writer、超时、未知状态语义、旧 evidence schema、旧 JSON 或旧 v1 基线。

## 冻结源码向量

- 新 `tests/fixtures/live-admission-source-guard-v12.json`：71 成员，SHA-256
  `cd2bb0f609180552ad722c5e5f3e9f8f0c76ada71cfd59a218a3e5fa9290cef6`。
- v1–v11 JSON 与原锚保持字节。v11 当前源码逐成员比较转交新 v12 D1；
  v11 测试继续核原 SHA、admission/launch 和 71 成员，v12 继续逐成员核当前源码。
- 新 D1 `tests/test_live_gate_regressions.py` 2 节点：公开内核五字段/禁 subprocess；
  v12 独立 SHA、71 成员及逐文件比较。新模块不进入历史组分母或回执。

## 模块与实际验证

| 模块 | 本轮实际节点 | 既有数量变化 |
| --- | ---: | --- |
| `test_offline_evidence.py` | 11 | 不变 |
| `test_read_config.py` | 29 | 不变 |
| `test_doctor_pi_exec.py` | 31 | 不变 |
| `test_issue167_core_wiring.py` | 7 | 不变 |
| `test_issue167_live_resources.py` | 16 | 不变 |
| `test_live_review_policy.py` | 2 | 不变 |
| `test_live_admission_source_guard.py` | 13 | 不变 |
| `test_live_bundle.py` | 11 | 不变 |
| `test_live_gate_regressions.py` | 2 | 新增、独立未绑定 |

- 修前最小反馈：14 节点，7 failed / 7 passed（4.67 秒），与原 7 个失败一致。
- 新宿主 D1 在旧实现上：1 failed（0.20 秒），准确命中 `uname -p` 隐藏 subprocess。
- 原五失败模块加首个 D1：95 passed（26.71 秒）；无 skip/deselect。
- 最终 v12 树原五失败模块加完整新 D1：96 passed（26.62 秒）；无 skip/deselect。
- 新 D1、源码/历史锚、bundle、placement、metadata 与 doctor 组合：110 passed（52.42 秒）。
- 配置/冻结契约六模块：157 passed（27.58 秒）。
- 全仓 mypy：1125 source files，通过；Ruff check 与 format check 通过。
- `check-compatibility all` 选择 176 节点；敏感测试旧 SHA 保留时，A1
  `test_scope_mismatch` 向下游传播。按负责人指示停止这一已知不具备通过前提的组合：
  46 failed / 20 passed，退出 2（中断，153.95 秒）；不是通过，也不代表其余 110 节点已验。
  该组合开始于普通 source 重绑之前，日志还包含当时 config source 的已解释漂移。
  审阅、精确重绑与合并后必须完整重跑 all；不复用本轮失败或局部通过。
- 原正式 gate 的 wheel 失败由独立只读诊断者核验，85 包与正式插件/顺序探索下未复现；
  本轮不改 wheel 测试、实现或超时。原 gate 前 2293 节点实际执行副作用仍未排除，
  新门禁若失败需树外精确诊断，不从原清洁输出补造 trace。

## 登记白名单与待 S3

只精确重绑普通 source `src/paper_radar/config/service.py`，成员、用途及计数不变。
直接登记组为 A2-01、完整 A2、A7、A9、A10；全部受影响组为
A2-01、完整 A2、A3、A4、A5、A6、A7、A8、A9、A10。

敏感 `tests/test_offline_evidence.py` **旧 SHA 暂不重绑**；直接登记组 A1、完整 A2；
全部受影响组 A1、完整 A2、A3、A4、A5、A6、A7、A8、A9、A10。
独立 reviewer 确认旧四契约/v1 计划与断言强度后，由集成人在最终合并树逐组生成
当次 base/HEAD/target/dirty identity 的 S3 确认并精确重绑。当前候选不能复用到后继身份。
只读基线审计无既有漂移；带 `--collect` 的审计因待 S3 失败而不执行收集，
上表来自独立显式 collect-only，不声称已完成正式审计收集。

| 实际修改材料 | 旧 SHA-256 | 新 SHA-256 |
| --- | --- | --- |
| `scripts/verification_scope_materials.py` | `5b018a7ababce06a9b36ce3a70fbcedd4471df771eb49a3923d5268e07695c96` | `524b6151380581e77369c477958ba4520104c7984b785f9039154ad633307d11` |
| `src/paper_radar/config/service.py` | `dc3841724b49d2eab9cfa11adb0905078e314423f7c7f657aea112afa0e68aaf` | `c23f3b4cec16ed28974ee9f6ffa20c0d0aae8e9334e81c4a2096694180955ee8` |
| `src/paper_radar/pi_execution/current_binding.py` | `60acb6e3e494cccf91c259940e1081d94aa4208bb05d07345457a685df6a207f` | `38b9561cfb4ad7cc506193b7fe4f473ba139a3ef154cd000fd7eb7783741663b` |
| `src/paper_radar/pi_execution/site_binding.py` | `e74472408b541fbb607bdde0d91f176147c4a131e0341bd12b9df9b556f062f0` | `43bdff6f69e69e6254af10490acaa6a503fc1f4364b84ea43557b0ad49fc6e0f` |
| `tests/doctor_pi_exec_guard/sitecustomize.py` | `2a6b8c64de65fad87ad72f67efbf61c6ddc1d38525dbc67315315e0044b6bafd` | `84be5148284a67d8ff36a354f3b5619430c423ef248f9ae37cee9c6f6e76797c` |
| `tests/pi_placement_support.py` | `40d723e8b25995303f7bf4657357981d275e3e43cdad8da33da63b0c84688f60` | `692206a3fdf4e5364f848baa1691a6574b90478f9c709ad2870e1c46b71f6002` |
| `tests/test_issue167_core_wiring.py` | `cdecdbfe387b24ae7a7764f218d36775bf7bb89624b0afbbd0851855f652b6ae` | `1d93c9011b38b18812fbf6643b8a8ed4a490aa337bc2ea04211690fa1aaf4756` |
| `tests/test_issue167_live_resources.py` | `fdbcd5b232320b2d82cfa12d6b58e18030df57243a43d60de43df1fdf9a1b454` | `01f4f987a2067c0573749682ca0b44fc6553dfd3b3ac9fae42e8eb1194f5f0ec` |
| `tests/test_live_admission_source_guard.py` | `50d9048fe99d492d637bf0a1cc58fe3aa2c7215b04af1e46e452a63fe4127934` | `5fecfc81fbdaf049387eef59ea326d8adf81dceea3ede8a061200f129a8f5352` |
| `tests/test_live_bundle.py` | `9f24cece3e2d7c84b7c1f0085c1e8073c55affea6e03a9d24f38f6af09126c32` | `40248d108bf7eb2cf4a7d6fdf93c5c040c96a63a3951afe1ededd4ac778f3818` |
| `tests/test_live_review_policy.py` | `da218c482fc624e25c5c2ba388e1699261c03db15019299de0b52275350f6ab3` | `2c8fdf64b9f1477b19c2a007b72e107fef0f09b571151fd247e5bdf43e2f685f` |
| `tests/test_offline_evidence.py` | `843308e18b62b0115ba149fc8ad6db1db15a5d01679086e91802b5f153dc5d49` | `4ad550638171513903050c053c5eadfede3f600475c6a515ca52aaea3f6fc28f` |

## 未验边界

本轮不取得完整离线门禁通过、同 run passed/verified/same、现场部署、auth 刷新、
真实模型、网络窗口或 owner 现场配置资格；已有异步 auth/自然到期裁决仍待处理。
没有 migration/table 变化；本轮无需 Schema 迁移验收。临时 pytest 清理对本机历史失败目录的
非空警告未改动或清理这些无关目录，不影响本轮已完成测试的断言结果。
