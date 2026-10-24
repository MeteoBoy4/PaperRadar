# A9 固定范围变更审阅台账

## A9-01（#93）

基线 `04ed7073172fdf6db9427dd68670b169140c2748`。本票只验证结构契约切片，
按已获批准的集成约定不更新任何 scope；#99 按 DAG 一次重绑。下列哈希是本票交付时
的审阅记录，后续修改继续追加相应票的记录，不能以此替代最终工作树审计。

行为验证：178 个测试通过（下列七模块），Ruff format/check 与全项目 mypy 通过。
未运行完整门禁；独立 scope 审计退出 1，原因为预期的 hash_drift，收集阶段为 ok。
受影响组：A1、A2-01、完整 A2、A3、A4、A5、A6、A7、A8。

| 路径 | 变更前 SHA-256 | #93 SHA-256 | 原因 |
| --- | --- | --- | --- |
| `scripts/offline_evidence.py` | `7c2585d4aec8416b496f6b2618e14a81a670b03806b10fc7fb3e48f3c7d08497` | `3c53fd4e272ee346da23b72cd977180b78aeaa55a027064a97f5540ea24d9a28` | 元数据按真实注册 area 取路径，历史计划不变 |
| `src/paper_radar/cli.py` | `c444c4e16c98e8615c2b5268f0f4288144c7aff3a3890f072bf503e66a55a524` | `b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66` | 中文帮助说明五份可选、A1 四份历史范围 |
| `src/paper_radar/contracts/schema.py` | `b90d7d5e0c0cfa4fc17f07aacc356da652c8c479d05ccf90324d94c992dfd118` | `f128e20731ece97f672ce50d9fb760a240abcdbd02b9aae63e83f2849fb0dade` | 注册独立 Read v1 |
| `tests/test_cli_help.py` | `966176a77cc60467198f115468b0dfe95f17e5ea3d09365f5b02faeaaea1d8cd` | `c03c70471575a50a82ae68bca7fea6c5bf3f885921fbac626403f2ce133e4ff4` | 既有无 I/O 帮助兼容新增受控名 |
| `tests/test_contract_cli.py` | `948e62d98e08410fe19fce762366f14f36eef2c812714f18ae792e8a4ddc93c6` | `84b86b8017b4cc94da95311409257fd1fc4ff575f840e3eef90c546893d59eaf` | 保留未知选择负例，更新完整可用名指引 |
| `tests/test_contract_export.py` | `9ddc4d25be516c7af133964cc9603ade8f262d3d5684a302250acf19a3261bc3` | `49dca04977690856bb2e8a14b9acc063d54e3e26182174b6c2164ac7f0e41f9f` | 显式固定历史四契约，保留原分母 |
| `tests/test_contract_schema.py` | `8092fb2390e8f2ada6bfd52b5f2db1ec68403720fe88a7d1221ec4932df8d497` | `9471333e0ab7df64fa135b2587b289059ca935fd45b53e4cc81d173ab931eb9a` | 显式固定历史四契约，保留原分母 |
| `tests/test_offline_evidence.py` | `17224fa2be8f2463c6066d47e0f29153b1490d203b068654b1ed0a44ce531333` | `843308e18b62b0115ba149fc8ad6db1db15a5d01679086e91802b5f153dc5d49` | 显式固定历史四契约，保留原分母 |

固定测试分母均从独立 `audit_verification_scope --collect --json` 收集核对，
没有动态回填或减少原 scope 分母。Read 新模块是独立 A9 范围，尚未接入固定 scope。

| 测试模块 | 原固定分母 | #93 实际收集 |
| --- | --- | --- |
| `tests/test_contract_schema.py` | 11 | 11 |
| `tests/test_contract_export.py` | 22 | 22 |
| `tests/test_contract_check.py` | 32 | 32 |
| `tests/test_contract_cli.py` | 37 | 37 |
| `tests/test_cli_help.py` | 5 | 5 |
| `tests/test_offline_evidence.py` | 11 | 11 |
| `tests/test_read_contract.py` | 新增 | 60 |

新增源码：`src/paper_radar/reading/{__init__,schema,value_types}.py`。
新增根与示例材料：`contracts/read/read/v1/{schema,manifest}.json`、
`examples/contracts/read/read/v1/{schema,manifest}.json`，两处同字节。
Read Schema SHA-256：`1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111`。
原四份 Schema/manifest 与 `src/paper_radar/screening/` 全部保持字节不变。

文档变化：领域词汇、draft 裁决同步、Read 字段矩阵与完整覆盖台账、冻结契约说明、
README 和离线证据范围说明；其中 README、offline-evidence 也在旧 A8 scope 内，
已如实出现在上述 audit 影响组中。新增公共规则文档由后续票继续按交付进度更新。

未验证：真实模型、Pi、Docling、PDF、map 来源、Read 生产接收、NAS 与完整阶段 A。

## A9-05（#97）

本票基于 integration 合并提交 `24a8741ea934fa80ff323229fd2be7bd1718f416`。不修改任何 scope，#99 一次重绑。

最终配置子集在显式加载既有完整元数据后 990 passed；本票独立新增子集 34 passed。Ruff format/check 与全项目 mypy（503 文件）通过。

`audit_verification_scope --collect --json` 退出 1，仅有预期漂移；收集 reason=ok、skip/deselect=0、execution=not_run。受影响组仍为 A1、A2-01、完整 A2、A3–A8。

| 路径 | 本票前 SHA-256 | #97 SHA-256 | 原因 |
| --- | --- | --- | --- |
| `src/paper_radar/config/schema.py` | `31d98d427c1c14922f08d455324a87bd1674749442d80edc4efdd94e29a6417c` | `ef445b8335f8c7b9828921d43a6cf116168cb7f2aea06ac1b6f1985f33570bc4` | 开放 read selector，缺失/null 仍不序列化 |
| `src/paper_radar/config/service.py` | `c9b1e320b42fd840ff091829bcccf8e62e413f006899e6618bd57417e23b1791` | `3f9732e076fe69e3e247d50bf682c519c4f9f6ccd5deb4398908d33a952ac103` | 登记和历史反查 read，沿用原材料校验与事务 |
| `src/paper_radar/config/compile.py` | `61d2537d0066dd8ee0ab1cd7aba0a2be858f69627feae420fbe0c18e801b30ee` | `0579c66ff57664b62269bb7ccfc5ba8f18277a284fd7fedf8cddb09d65eb7b69` | 在原缺项位置判断 Read 契约，配置齐全可 ready |
| `src/paper_radar/config/diff.py` | `920553c48bc661893a6b3a3c23c0df0e051888f6161c010f98dced9d1664da30` | `add553638b26d691e1f8ca7fb69261347a5dfff00b5b34288cf8f866f0810b5d` | 补充两项 Read 契约封闭类别 |
| `src/paper_radar/config/cli.py` | `69f06e69b312af4c4d3ab07652789e20e17bf0d07ee73351ad0d61c2b6872234` | `1bbec637e1017146c595f3aba6bf6b616e067bb20df48581b3d1ac28558c986f` | 中文帮助说明显式契约和配置完整性 |
| `tests/test_config_read_validation.py` | `e76a9b90effb5b516531c370b628dea5da9c238c05d3b787bbb6e1b2a3378035` | `fa9a338476fca43b7b95ff369091064c784394eced54d7841989600234bb61ef` | 保留原参数分母，将已合法 selector 负例改为材料缺失拒绝 |
| `README.md` | `2648fa5452f9f3ec3e3502c56e0755fbf4bb58810a01b29f93523c0039304caa` | `9d3b22bae786fd8696af468b9f86549290b87885f1524a00d3d3a02f503ffe35` | 增加独立 ready 示例并解释旧示例未选择契约 |
| `docs/contracts/runtime-config.md` | `7328c70c65acae06285f352e7b859bc2b0d49d1d75ee66ddf6dde1782fc020b1` | `ee0752fb4215d65e4f1debe600234913fcc80f618af2e963f1a0c2340075582c` | 同步 selector、封闭材料名、缺项与历史回放语义 |
| `docs/contracts/config-projections.md` | `44d9b25b05dcd6d3d8891631f6f5f07f2ffdbb8d9addc31415ede2ea51d92d16` | `854e353a9329971bc5893bcb687d4977a8365a1fbe683725c4b3605d432e9565` | 区分旧 null 身份与新 Read contract 分量 |
| `docs/contracts/config-snapshots.md` | `18d48f7d1d4d36aea8093e3f58347eeabae5a411b352bf8d64d06106f9c4ece0` | `7bd0371f214027cb3288e3c03a3b505007d9c49177e133b27df7fccc61826d96` | 登记 Read 双材料摘要和 diff 支持 |
| `docs/contracts/frozen-contracts.md` | `da03a5cb963f230b10ea78e3ed514406dbcc903b1810a637d7ffe1eedbf9caa3` | `f8a4da25f859cea1013739b936a0a4d845e411d739fed569abed6b5c441f4c07` | 指向已交付 Read 配置准入和历史语义 |
| `docs/contracts/read-validation.md` | `0e012d5d162bd4efa8fe8ca2b3d77be4ee74d805ee3efe85b91e3b5676eea275` | `a1f1dca6a0d05b56c71bd316d9e245112ff4c900b0b5a2352b051909a5638c00` | 标注 #97 已交付与测试覆盖，保留恢复目标边界 |
| `intent/draft.md` | `9e706b76cc4f32d595ff2bd637bf4a736c59db080660d37cd16fe8a3628e9094` | `30eee67eea6008bb9015edb05839237d7d92ea2c0c444570296217bcea9bc539` | 按实际配置交付同步当前说明，保留 A2-06 历史含义 |
| `docs/contracts/adapter-config.md` | `aa2efe84304fba9acd3344a7cab578051854bbec570d4da4a5e3017703509754` | `46fdf72a13ecfb8c6b4f962caeac5f582d7256f1114aa2df9986daadfe5cea0e` | 将 Read 额外配置条件指向已交付契约，保持 adapter 政策 |

固定旧 `tests/test_config_read_validation.py` 分母 28 → 28，由独立审计收集核对；只替换合法 selector 的目标拒绝原因，不删除负例。

新 A9 测试为 `tests/test_read_config.py`（29 项）和 `tests/test_read_config_cli.py`（5 项），支撑为 `tests/read_config_support.py`，独立于旧分母。新增示例 `examples/config/settings-read-ready.yaml`；旧示例、五份冻结契约和投影配方字节不变。

新增测试覆盖显式准入、未选/null、就绪缺项、双材料身份与摘要、Read 单投影 diff、缺失/损坏/错版/手写材料、只读 check、原子回滚、幂等、历史损坏拒绝、删文件后新进程 load 与权威模型演进后的历史 load；不证明生产执行。

独立 config-only 收集曾使旧 `test_upgrade_is_idempotent_and_schema_matches_metadata` 未加载 papers/pi/screening_tasks 表，基线同样失败。显式加载既有真实元数据后该测试通过；不借本票修改旧测试或生产 schema。完整门禁仍由 #99 收口。
