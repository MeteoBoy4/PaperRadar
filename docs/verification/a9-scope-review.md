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

## A9-02（#94）

本票新增可靠文本的公共纯接收、只读上下文、严格 JSON、数值规则与安全警告三视图。
不修改任何旧 scope、Screening 文件或冻结契约。255 项 Read 子集及既有严格 JSON、
架构、契约兼容组合共 399 项通过；全项目 Ruff format/check 和 mypy 通过。
完整门禁留 #99 同次收口，当前独立 scope 审计仍为预期 hash_drift。

下表只记录本票改变的既有材料；#93 的已有漂移继续保留，不以本票重复解释。

| 路径 | #94 变更前 SHA-256 | #94 SHA-256 | 原因 |
| --- | --- | --- | --- |
| `src/paper_radar/reading/__init__.py` | `8f38dd4922fa49cf9e7fd5f1e2ca2531cc805bb67fed3c02ea4df8797b3abf3d` | `90f7cfb756c987d71ddc7dc949372e9fea78378a958849ffbdac6a0492c828a3` | 导出单一公共校验、上下文、结果及受控词汇 |
| `README.md` | `2648fa5452f9f3ec3e3502c56e0755fbf4bb58810a01b29f93523c0039304caa` | `e275a8524d0378ba2f1d5e5589edb25c945ea0b09bbfa0dad07c9a72b1c73173` | 披露可靠文本纯接收已交付与后续范围 |
| `docs/agents/llm-evidence.md` | `680bc306afeca76ceab6a3626b9c8c080653d5fee285cfb950f25c31d2fe588a` | `49796d520af0409407fa6fe1a76569a3c56a7e6a7213d57e07e129b3c4724468` | 指向 Read 公共规则而非只给 Screening |
| `docs/contracts/read-validation.md` | `0e012d5d162bd4efa8fe8ca2b3d77be4ee74d805ee3efe85b91e3b5676eea275` | `648875a456d7cc2120b291ebb1f4eef0221e8cb87f4f239089c85dcbcf14ed22` | 公共上下文形状、数值闭集和按票更新覆盖台账 |

新增源码：`reading/context.py`、`errors.py`、`numbers.py`、`parsing.py`、`result.py`、
`validation.py`。新增支撑 `tests/read_support.py`；架构守卫复用既有
`tests/test_screening_architecture.py` 的绝对/相对导入检查，A9 固定范围须将该支撑一并纳入。
以下独立收集只核对执行分母，不代表执行通过，也不动态写回任何 scope。

| 新测试模块 | #94 实际收集 |
| --- | --- |
| `tests/test_read_context.py` | 59 |
| `tests/test_read_validation.py` | 76 |
| `tests/test_read_numbers.py` | 57 |
| `tests/test_read_privacy.py` | 3 |

新增源码/测试目前未纳入历史固定 scope，#99 应作为独立 A9 范围登记。
Read Schema 仍为 `1ac06948024aab610c6b2c1098d0a53596632c940704d32fae860a03ed5d6111`。
未运行 Pi、模型、Docling、PDF、NAS，orig 哈希覆盖及 map 来源链仍未验证。

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

## A9-03（#95）

本票以 integration `c2d38b75a31238261e9056790fa61ab534b19c52` 为基线，接通受限源
字段矩阵；不修改旧 scope、Screening 源码或五份冻结契约。下表是合入并行 #96 前的
本票材料审阅记录，最终合并字节由 #99 一次审计重绑。

346 项 Read/配置组合测试通过；Ruff format/check、全项目 mypy（515 文件）通过。
独立 scope 审计仅有预期 hash_drift，收集 reason=ok、skip/deselect=0、execution=not_run，
受影响组仍为 A1、A2-01、完整 A2、A3–A8。没有发布新的全量通过结论。

| 路径 | #95 前 SHA-256 | #95 SHA-256 | 原因 |
| --- | --- | --- | --- |
| `src/paper_radar/reading/context.py` | `411b3ba87182889e92b97b3533ea784fc1a47b98572d0d12e0c35ea54439a561` | `b107c33613721ecee153051fe1af2e11a77e2fc8be39fbe72946beb22b65d72d` | 移除受限源暂拒，保留种类与闭包验证 |
| `src/paper_radar/reading/errors.py` | `4415bbbb6e6b5b3630e7e2cef116c9992153d705a82f7a5cb155ed566d2c32db` | `89d750bbbac2d8650a7f3bbb43a72284c20ad587306847b667ab67715f2668dd` | 增加受限硬失败类别与安全降级诊断 |
| `src/paper_radar/reading/numbers.py` | `a93fca33e50014e6060d7021bef22ccc3aab9344f524214579bdc8b180b312d7` | `18d543e2a438b2a6e5bd4a3ea479aeee656fd1acadee167a2bd74f21a9811f52` | 限定英文交叉引用左边界并提供受限支持原因 |
| `src/paper_radar/reading/validation.py` | `02d037df5a9d3887fb2e58ede010c1b52a9e95da31564a87648bd11c9491e404` | `c8594426dbe7677bdf64a299d7f1a3bfdf182c58ea596ce076d87afcca7ac66c` | 接通逐字段矩阵并收集全部受限违例 |
| `tests/test_read_context.py` | `6b4b075b946c2356894a5d9517f6131c48513ee29eacaa65048855726919e730` | `1e2bad2d2e6932a61ae0e0b394fcfe2ec9e76c5dc85021896af48a25e248e12d` | 两暂拒负例改三种来源事实正例，保留候选与闭包拒绝 |
| `tests/test_read_restricted.py` | 新增 | `ccae8274a573e7291c643f661a65537aa7959b934ca0684a3ca059a499a8e5f5` | 全字段矩阵、混合来源、英文 origin 及前缀漏检回归 |
| `docs/contracts/read-validation.md` | `dac412d2f895e7cef1449c35192e31147bc169e85ea18872e85d3169a87df5b4` | `d7179c37fe17eeff48da36067208658f0768a5317a48d01492d532e18b318eec` | 更新矩阵交付、错误诊断与覆盖台账 |
| `README.md` | `17f1109319626c056fa5102d79a3c648d57bf3b03f03267b2ee7f8cd5a9d754c` | `7b4d4bceff5a60613534d9869db4c8f59bb28be68d38569b3cac480b580badaf` | 准确声明受限证据已交付 |
| `intent/draft.md` | `30eee67eea6008bb9015edb05839237d7d92ea2c0c444570296217bcea9bc539` | `e05831c241f9bfcd3c5784b4ba149961110e91a70698c7185fca4f24658c6aa3` | 按实际切片同步交付说明 |

`tests/test_read_context.py` 59 → 60：原 table/unreliable 的两项暂拒改为 table/formula/
unreliable 三类合法来源事实保留向量，不减少未知 kind、候选、闭包或定位拒绝。
新增 `tests/test_read_restricted.py` 56 项，归独立 A9，不并入旧组分母。

表格结构、表格数值仅受限命中、公式/不可靠引用、关键局限降级、混合 provenance、
可靠来源同时命中、范围跨切片拒绝、模型警告伪造 origin 和固定优先级均经公共入口
验证。额外修复当前同规则中的窄漏检：stable/intersection 的词尾不再被误识别成
Table/Section 前缀；Table/Section 标签仍排除，规则身份保持 v1。

没有新增迁移、人工复核后门或 attempt；未运行 live，orig 哈希覆盖、真实 PDF 与
科学语义仍未验证。阶段 G 的修正提示和 attempt 结算仍由未来生产接收器实现。

合入 #96 后，保留其 AllowedEvidence、模式/三元组/范围约束，以及本票的受限策略与
失败诊断；388 项 Read/reduce/配置组合测试通过，Ruff format/check、mypy（516 文件）
和显式 read/v1 检查通过。上述 SHA 表保留本票合并前审阅时点，不覆盖 #96 的独立记录；
最终工作树字节和所有必要固定分母由 #99 统一登记。

## A9-04（#96）

本票基于 integration 的 `c2d38b75a31238261e9056790fa61ab534b19c52`。
新增同正文 `AllowedEvidence` 及 single/reduce 约束；原始字节仍由同一验证入口处理。
不修改冻结契约、Screening、配置、migration 或任何 scope。完整重绑与全量门禁留 #99。

| 路径 | #96 前 SHA-256 | #96 SHA-256 | 原因 |
| --- | --- | --- | --- |
| `src/paper_radar/reading/__init__.py` | `90f7cfb756c987d71ddc7dc949372e9fea78378a958849ffbdac6a0492c828a3` | `a7a980453943233f5f40169205e74e22b5d81bfc959196bdbc746fd62c782f3a` | 导出程序侧允许集合，模型 Schema 不变 |
| `src/paper_radar/reading/context.py` | `411b3ba87182889e92b97b3533ea784fc1a47b98572d0d12e0c35ea54439a561` | `9a3e7c7a07d7231c929a72e8e7c4e035b21d10e15b47c67dd1238eee3d56a942` | 冻结集合，核对模式、三元组、重复及未知成员 |
| `src/paper_radar/reading/errors.py` | `4415bbbb6e6b5b3630e7e2cef116c9992153d705a82f7a5cb155ed566d2c32db` | `dd256e8a882e4f3b876e171811f9f3b1aa6dace64a79ec2346fba4d8e18e1a26` | 分开调用方集合错误与模型引用越界 |
| `src/paper_radar/reading/validation.py` | `02d037df5a9d3887fb2e58ede010c1b52a9e95da31564a87648bd11c9491e404` | `3a48b8cf016b576ae38202582a2ae02c8100ec433502835141e9078a7f299632` | 按同一保护字段循环核对允许范围和有效引用义务 |
| `tests/test_read_context.py` | `6b4b075b946c2356894a5d9517f6131c48513ee29eacaa65048855726919e730` | `3096c617684cff38d9e8d6db8a069dcf30b76215df00af7cf8a3bab6bec35144` | reduce 暂拒替换为缺少明确允许集合拒绝，保留负例与原分母 |
| `README.md` | `17f1109319626c056fa5102d79a3c648d57bf3b03f03267b2ee7f8cd5a9d754c` | `941de3d944ee9695b2c76381b4c86c5fba70d1dd0703e175eecef88564fdcaf4` | 说明 reduce 范围已交付及生产来源未验证 |
| `docs/contracts/read-validation.md` | `dac412d2f895e7cef1449c35192e31147bc169e85ea18872e85d3169a87df5b4` | `ca7d85a12adb36f4bd58b3fad65a5ccb618a1f431da6eecc587c9bd7a20e9a51` | 公共字段、错误边界、空集合诊断及覆盖台账 |

新增 `tests/test_read_reduce.py` 共 42 项；原 `tests/test_read_context.py` 保持 59 项。
本票 Read/配置组合实际 331 passed；Ruff format/check、全项目 mypy（515 文件）通过。
scope 审计收集 reason=ok、skip/deselect=0、execution=not_run，退出 1 为既有预期
hash_drift；受影响组为 A1、A2-01、完整 A2、A3–A8。没有动态回填任何固定分母。

42 项通过范围包含：同候选 single/允许 reduce/排除 reduce、三元组各分量不符、
重复/未知/严格 ID、集合类型及防御冻结、空集合双诊断、五类保护内容范围、数值和
模型警告保留、严格输出规则与重新导出同一冻结 Read Schema。
未证明真实 map 来源链、生产正文/模型、完整 Read StageInput、任务或预算；未运行 live。


## A9-06（#98）

本票沿用真实 config/storage/backup 公共服务，不增加 migration、制品种类或 Read 成功事实。
双历史配置与中/英文 × single/reduce 四份合法原始响应经备份、原根哨兵/audit 屏障、
新进程恢复和再次搬迁后逐项一致；上下文由固定常量重建，不是恢复产物。
恢复后还验证允许集合与受限矩阵共同拒绝、截断 JSON 拒绝、Read 材料/引用闭包损坏、
响应 blob 缺失/坏字节和旧/未知 revision 的现有拒绝。无效候选仅在内存修改。

为满足 #92 US39 与 #98 的表示隐私，RuntimeConfigSnapshot.payload_json 仅增加
repr=False；公共 compile/load 隐私回归先失败后通过，持久载荷/ID/投影未改变。
478 项 Read、旧 A2 投影、相关 A3 备份恢复组合通过，Ruff format/check、mypy
519 文件通过。完整门禁与链式 scope 重绑仍由 #99 执行，本票不修改 scope。

| 路径 | #98 变更前 SHA-256 | #98 SHA-256 | 原因 |
| --- | --- | --- | --- |
| `src/paper_radar/config/compile.py` | `0579c66ff57664b62269bb7ccfc5ba8f18277a284fd7fedf8cddb09d65eb7b69` | `58cc5454dfe5e662f0e7eef0f884c2b562891f9ae7b0a709fbf78984eb81654e` | 仅隐藏 RuntimeConfigSnapshot.payload_json 默认表示，持久化/身份不变 |
| `README.md` | `b9c8c43913d215e281c363d0ea8ee57c27a039f18bffe0bdcc25ad6b51aebcba` | `5303b81d481685eb594879048de19d79529e037e698da38842dac4b4a6488afb` | 准确披露 Read 配置/候选非空恢复交付与未验证范围 |
| `docs/contracts/read-validation.md` | `3fda118c47345911d58de8219de664fc90a9c4c9d3c9703e3ea46698b71dcc27` | `21b0be1db867be6f409760a9a76ba5727e62381a285ce1e85a73bbbaf334c3f6` | 记录恢复公共边界、四候选/双快照、损坏拒绝与台账 |
| `docs/contracts/backup-restore.md` | `c9811b91edcf2415ccf41cbd5711c2180b30a2d9c354350e1f944ed21488a6de` | `c8184ad1419f8d0f2840861a838b8c9ccd299e9ee7e655f758029bf5b0c5dfd1` | 指向唯一 Read 恢复范围说明，不改变备份算法或格式 |
| `docs/contracts/config-snapshots.md` | `7bd0371f214027cb3288e3c03a3b505007d9c49177e133b27df7fccc61826d96` | `d7a19be8d2900dde2750f8ddeb3c9c9db5dad77b9e343f1bdd5f34af971a98a0` | 指向 Read 恢复范围并说明快照安全表示 |
| `intent/draft.md` | `8340d8520f04ffe43ec7bd5d3e4eee9fbee532cbc3ba843dd8213755c203f1e8` | `1ededd5db5e6fc83c627b0d07919097a9a29e87eba81efe039783800fd0343f7` | 同步 #98 实际进度与固定上下文恢复范围 |

| 新文件 | #98 SHA-256 |
| --- | --- |
| `tests/read_recovery_support.py` | `b5569cd43e7decdfe914365a0d2dcefb5069c4b26fc50629925904707a1912b9` |
| `tests/read_recovery_worker.py` | `2404ff8fe28da8786c68a9853ce135bd20f13582fa8392ab5aafe115c3ae6f86` |
| `tests/test_read_recovery.py` | `586b2624a6a85edab2d79ba01551f4a1cbaf52a837950d6625c30ded862d50e1` |

新增固定执行分母：tests/test_read_recovery.py 为 11；独立 collect-only 核对为 11，
不动态回填任何 scope。测试支撑还消费 tests/read_config_support.py、read_support.py、
backup_support.py 及其既有 config 支撑，#99 应显式审阅并纳入 A9 闭包。
现有测试文件未修改，原固定分母不变；config/compile、README、backup-restore 等
旧绑定字节变化需按真实 DAG 一次重绑。独立审计 98-scope-audit.json 返回1（预期
hash_drift），collection reason=ok、skip/deselect=0，execution=not_run。
受影响 A1、A2-01、完整 A2、A3–A8；历史结论不覆盖，不以收集代替执行。

未运行真实 Pi/模型/Docling/PDF/NAS；orig 的生产哈希归属、真实 evidence-map、
当前正文选择、科学语义、map 来源链和生产 Read 仍未验证。

## A9-07（#99）固定范围收口

本节以 `04ed707` 为旧范围基线，前六票的行为原因见上述逐票记录。
按真实引用 DAG 一次收口：A1 → A2-01 → 完整 A2 → A3 → A4 → A5 → A6 → A7 → A8 → A9。
A4→A5 来自真实 source 引用。所有旧范围仅更新必要字节绑定，测试文件集合与固定分母
不扩大、不减少；新增 Read 与 A9 协议测试独立登记。以下同路径/同前后哈希合并列出
消费者，清单本身仍为各 scope 的显式字面量，不在运行时按当前文件或 collection 回填。

A9 固定 reading 全包、真实数值/警告机制、配置与恢复边界、原始候选恢复 worker、
架构 scanner、契约/示例及新测试；登记自己的 writer，明确不登记 a9_scope.py 自身。
正常登记审计与 self_reference/cycle 拒绝用例、前后完整工作树身份共同保护该例外。
完整入口合成回执支撑引用的 A4–A8 scope 属于测试材料闭包，不能替代生产直接前置
A1/完整 A2/A3，也不继承它们的通过状态。

| 消费 scope | 路径 | 基线 SHA-256 | 收口 SHA-256 | 原因 |
| --- | --- | --- | --- | --- |
| `a8_scope.py` | `README.md` | `5c40cdd06e82c16b491540d3e1c9340daf2e174abf8b918518e24cb59a6ce54d` | `72c8dc720dba8fa7a8ba76101461ab785b55c1988a3efa3e0670425bc70440a9` | 本批 Read 契约/配置/恢复及 A9 当前范围文档，保留历史语义 |
| `a8_scope.py` | `docs/contracts/verification-status.md` | `91d3bda5e4cc855cb9083d047d82c2cb341a40090aed5a0bab07e3be26ab4b5f` | `ccd6c5f223cee2c7eb4d3f5d65fcc2c056293f6e50210942e7020273dcac1739` | 本批 Read 契约/配置/恢复及 A9 当前范围文档，保留历史语义 |
| `a8_scope.py` | `docs/verification/offline-evidence.md` | `c8f3e3d702dd669b939a0606f1e4816a09075d55c59c9f4eb9c32ac8256e4896` | `f9d266a75322454c1e7ac95ed38e057087b81949ad7cd760e8e0fb91883352b6` | 本批 Read 契约/配置/恢复及 A9 当前范围文档，保留历史语义 |
| `a2_full_scope.py`, `a4_scope.py`, `a5_scope.py`, `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/a1_scope.py` | `e71257263bed5859e4277c8b0ff399c4986c440e8212c8d1a636c559fcc7d428` | `245cf6e6bd9d1dafe3f747561d2518d32583e6154dc4876ff1cc9a5c78152251` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a2_full_scope.py`, `a3_scope.py`, `a4_scope.py`, `a5_scope.py`, `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/a2_full_acceptance.py` | `1240d6ffa62ebc9f7234857e1e9f5bcb709091cd0edc0a6783b40306d54ecb16` | `b90a29fb1b645c47960f7f1ca9db816495225a68d1b6ac60a6e43096f0d40840` | #99 追加 required A9 及直接前置，不改变旧组资格 |
| `a3_scope.py`, `a4_scope.py`, `a5_scope.py`, `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/a2_full_scope.py` | `f48e9af3cf10cdb728b9140d55303559fe3c3b60950b0a0e38be11b156b9855a` | `8022620adb20868eb7d006285baafb04991ce8e40e282d3de85b4b38b96b28e7` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a2_full_scope.py`, `a3_scope.py`, `a4_scope.py`, `a5_scope.py`, `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/a2_test_receipt.py` | `c31cc8385293e915a38419a89886b114be6200b2a43b84935235c1a72d20c401` | `795596859f24d1241c589afd3d28902cbc148724b0aaa25fdbfafeaec4bd1593` | #99 显式记录 A9 固定模块的实际执行 |
| `a4_scope.py`, `a5_scope.py`, `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/a3_scope.py` | `1730f0b2d0350ca75f0c30aedd22aac8059c6cf9de958efc86b7e8dda332a04b` | `3738ed6011aacbf1ce22307dc456c4168caf8a5bef57c07536a014b1451354f3` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a5_scope.py` | `scripts/a4_scope.py` | `a96912d4a82c3a07d85d98b7f411725e956fd39ab6d6f49f65bbbc4ad1c1a132` | `ab2e56ee6084b7dbcc176aefbafeafc0899e61722425949d486432a85d75a948` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/a5_scope.py` | `527f9bd266fce539932ef3610bd67a771e0c54c6e7f47922e60d588366f4783e` | `0da384fa71f01c7ee4be9df86ca51a7ee305b69fe91188469b714046d1578ce1` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a7_scope.py`, `a8_scope.py` | `scripts/a6_scope.py` | `139decc9ce005553cd63759cc11653f042bbc6aaa1b95ed942feaf7b842beada` | `8e1f8380147e5fff1040fcc7589c34e7f12f14738f62c59e6474f828a3390e02` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a8_scope.py` | `scripts/a7_scope.py` | `a5ab4504d3e356e57a7badf00ee2f3d899a931f6b4e429cd725cd020870754e5` | `5e14d94a13cc6978d972bb1b799322d307acddc404a2a5d49f79eb2776442c11` | 前置 scope 同批重绑，按 DAG 传播固定身份 |
| `a2_scope.py`, `a2_full_scope.py`, `a3_scope.py`, `a4_scope.py`, `a5_scope.py`, `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/check-offline` | `aac450ba4bd00f30067dca0ae2ec06129140dae7eebce360b5055e4571f56c84` | `7da9535adf65a7ae809242d556d40412f65851602d6a4cde84426038ec364382` | #99 中文帮助同步十一主要/十三 JSON 与必需 A9 |
| `a2_full_scope.py`, `a3_scope.py`, `a4_scope.py`, `a5_scope.py`, `a8_scope.py` | `scripts/offline_evidence.py` | `7c2585d4aec8416b496f6b2618e14a81a670b03806b10fc7fb3e48f3c7d08497` | `3c53fd4e272ee346da23b72cd977180b78aeaa55a027064a97f5540ea24d9a28` | #93 元数据按受控实际 area 取路径，六检查与 A1 四契约不变 |
| `a6_scope.py`, `a7_scope.py`, `a8_scope.py` | `scripts/verification_status.py` | `7c3b5bf260ff645c3731c79b502dda16df121c62e5e32f13f20df519e5a17786` | `4db5d49e411b45777a2b32a2ac1d739b746274c1cdf7115e62c50c96640630a7` | #99 支持 .a9.json 格式1，保留历史格式 |
| `a2_scope.py`, `a2_full_scope.py`, `a3_scope.py`, `a4_scope.py`, `a6_scope.py` | `src/paper_radar/cli.py` | `c444c4e16c98e8615c2b5268f0f4288144c7aff3a3890f072bf503e66a55a524` | `b5bf7b9f643fc84dcccf1227af608d8602deec167f5aeedff7efdd02d536cb66` | #93 当前五契约帮助与历史四契约范围 |
| `a2_scope.py`, `a2_full_scope.py` | `src/paper_radar/config/cli.py` | `69f06e69b312af4c4d3ab07652789e20e17bf0d07ee73351ad0d61c2b6872234` | `1bbec637e1017146c595f3aba6bf6b616e067bb20df48581b3d1ac28558c986f` | #97 中文帮助区分配置就绪与生产运行 |
| `a2_scope.py`, `a2_full_scope.py`, `a7_scope.py` | `src/paper_radar/config/compile.py` | `61d2537d0066dd8ee0ab1cd7aba0a2be858f69627feae420fbe0c18e801b30ee` | `58cc5454dfe5e662f0e7eef0f884c2b562891f9ae7b0a709fbf78984eb81654e` | #97 显式契约准入/缺项；#98 payload 默认表示脱敏，身份不变 |
| `a2_scope.py`, `a2_full_scope.py` | `src/paper_radar/config/diff.py` | `920553c48bc661893a6b3a3c23c0df0e051888f6161c010f98dced9d1664da30` | `add553638b26d691e1f8ca7fb69261347a5dfff00b5b34288cf8f866f0810b5d` | #97 封闭差异类别新增 Read 双材料 |
| `a2_scope.py`, `a2_full_scope.py`, `a7_scope.py` | `src/paper_radar/config/schema.py` | `31d98d427c1c14922f08d455324a87bd1674749442d80edc4efdd94e29a6417c` | `ef445b8335f8c7b9828921d43a6cf116168cb7f2aea06ac1b6f1985f33570bc4` | #97 开放 read selector，拒绝 reading 别名 |
| `a2_scope.py`, `a2_full_scope.py`, `a7_scope.py` | `src/paper_radar/config/service.py` | `c9b1e320b42fd840ff091829bcccf8e62e413f006899e6618bd57417e23b1791` | `3f9732e076fe69e3e247d50bf682c519c4f9f6ccd5deb4398908d33a952ac103` | #97 历史材料 selector 反查包含 read |
| `a8_scope.py` | `tests/a8_acceptance_support.py` | `26b5602a0ed7594a54aae74de5c8950126a973d84f15e95c27d3cd7e8374dd40` | `2a4516dc9d4f462d4f2a7f6c3106b5b0631e605f9c656e4c91e0fe96b12bd057` | #99 当前完整入口的合成回执补 A9；不扩大旧 A8 固定测试集合 |
| `a2_full_scope.py`, `a4_scope.py` | `tests/test_a2_full_entry.py` | `b85f0328bd9d842c29e4f76f0f7b1845b64651cce56a0bb63188214c50ab0584` | `170e631f6d67bbb1d904d61ecc6a712b1884e1d8407d22dc70458c95485fa16b` | #99 当前帮助及产物计数同步，旧断言目的保留 |
| `a8_scope.py` | `tests/test_a8_entry.py` | `d131e48b2ddb75023374831817d85ba0349620eb41da436bb6f0292dd7a37147` | `673c06d68d92d90b30439dc4ac8bd29d266d6a7a3d84af3c786ced4aa585ecf2` | #99 仅当前完整产物由12→13，A8 失败和中断反例保留 |
| `a1_scope.py` | `tests/test_cli_help.py` | `966176a77cc60467198f115468b0dfe95f17e5ea3d09365f5b02faeaaea1d8cd` | `c03c70471575a50a82ae68bca7fea6c5bf3f885921fbac626403f2ce133e4ff4` | #93 契约/帮助兼容的必要字节变化，原测试分母不变（见首票） |
| `a2_full_scope.py` | `tests/test_config_read_validation.py` | `e76a9b90effb5b516531c370b628dea5da9c238c05d3b787bbb6e1b2a3378035` | `fa9a338476fca43b7b95ff369091064c784394eced54d7841989600234bb61ef` | #97 合法 read selector 的负例改为缺材料，固定28项不变 |
| `a1_scope.py` | `tests/test_contract_cli.py` | `948e62d98e08410fe19fce762366f14f36eef2c812714f18ae792e8a4ddc93c6` | `84b86b8017b4cc94da95311409257fd1fc4ff575f840e3eef90c546893d59eaf` | #93 契约/帮助兼容的必要字节变化，原测试分母不变（见首票） |
| `a1_scope.py` | `tests/test_contract_export.py` | `9ddc4d25be516c7af133964cc9603ade8f262d3d5684a302250acf19a3261bc3` | `49dca04977690856bb2e8a14b9acc063d54e3e26182174b6c2164ac7f0e41f9f` | #93 契约/帮助兼容的必要字节变化，原测试分母不变（见首票） |
| `a1_scope.py` | `tests/test_contract_schema.py` | `8092fb2390e8f2ada6bfd52b5f2db1ec68403720fe88a7d1221ec4932df8d497` | `9471333e0ab7df64fa135b2587b289059ca935fd45b53e4cc81d173ab931eb9a` | #93 契约/帮助兼容的必要字节变化，原测试分母不变（见首票） |
| `a1_scope.py` | `tests/test_offline_evidence.py` | `17224fa2be8f2463c6066d47e0f29153b1490d203b068654b1ed0a44ce531333` | `843308e18b62b0115ba149fc8ad6db1db15a5d01679086e91802b5f153dc5d49` | #93 契约/帮助兼容的必要字节变化，原测试分母不变（见首票） |
| `a2_full_scope.py`, `a4_scope.py` | `tests/test_verification_compatibility.py` | `b8d1938d353bb7799c8cca6914da9b55d07c9455ca91c7f9eaf1e4a9e5841ebc` | `77ddd42b829b2ea9c4cbff486ca54da3d40c9eefc3e27b4682e560841cd7b17d` | #99 继续逐字比较旧 transcript，另剔除新增 A9 输出并更新总数 |
| `a2_full_scope.py`, `a4_scope.py` | `tests/test_verification_run.py` | `fa672e5f2b138a5a4821412aad6053a2dab5d128af4bbd7cccaeedc562a71145` | `65196031de305c040b73b3f7ae832813e1eb2af12db10b10ffe0493393c9a6ab` | #99 额外合成组场景的产物由13→14，资格语义不变 |

### 独立 A9 固定分母

下列分母按各票结果与本票参数化先人工推导，独立 audit --collect 已逐项一致核对。
Read 10 模块共399项；A9 5模块共120项，合计519项。旧组各模块独立收集也全部
等于既有预期，skip/deselect 为0；收集 execution=not_run，不是执行证明。
本记录只证明登记审阅，最终通过仍须本次完整入口、真实回执和可信终态。

| A9 模块 | 固定预期 | 独立核对 |
| --- | --- | --- |
| `tests/test_read_contract.py` | 60 | 60 |
| `tests/test_read_context.py` | 60 | 60 |
| `tests/test_read_validation.py` | 76 | 76 |
| `tests/test_read_numbers.py` | 57 | 57 |
| `tests/test_read_privacy.py` | 3 | 3 |
| `tests/test_read_restricted.py` | 56 | 56 |
| `tests/test_read_reduce.py` | 42 | 42 |
| `tests/test_read_config.py` | 29 | 29 |
| `tests/test_read_config_cli.py` | 5 | 5 |
| `tests/test_read_recovery.py` | 11 | 11 |
| `tests/test_a9_acceptance.py` | 4 | 4 |
| `tests/test_a9_integrity.py` | 91 | 91 |
| `tests/test_a9_entry.py` | 10 | 10 |
| `tests/test_a9_status.py` | 11 | 11 |
| `tests/test_a9_scope.py` | 4 | 4 |

本票新增 writer、回执与 .a9 格式、真实前置/字节/计数反例、完整入口 Read 检查
阻断、发布不可覆盖/中断、终态缺失/篡改和 scope 身份保护。覆盖材料明确映射42故事、
21决策、20测试面及四评论。当前正常产物十一份主要文件加回执/terminal共十三份JSON；
A1 四契约、固定六检查和真实 migration a704_screening_retry 保持。

A9 scope 清单保存所有新源码/测试/材料的显式 SHA-256；本台账不记录自身或
a9_scope.py 的最终 SHA，以避免间接自哈希环。旧证据不覆盖，最终 commit/run_id
放在未跟踪的运行证据与交付记录，不回写固定文档。真实 Pi/模型、Docling/PDF、
orig 哈希归属、map 来源链、生产 Read、NAS、校准和完整阶段 A 仍未验证。

## #92 双轴审查修复

基线为集成提交 `9e44d35105c2a4dad4dc8f39f68e70c5e40c68a7`。同一实现代理处理
Standards 的负例原因断言、诊断类型依赖环和旧能力文案，以及 Spec 的三项数值漏检。
三类缺口均先通过公共 validate_read_output 复现失败，再修复；后续独立向量覆盖
无空格/有空格 ±、缺失或错误误差项、完整科学记法/非支持幂形状，以及范围两端
显式单位冲突与裸前端正例。未变更Schema字节、规则wire身份、投影配方或migration。

安全诊断下沉至 reading.diagnostics；原reading/root、numbers.NumericReason和
result.ReadDiagnostic导出保留相同类型。只读AST导入图审计确认Reading模块无环。
隐私负例分别断言extra_field与invalid_source的准确安全路径，现有3项分母不变。

独立audit --collect的实际DAG仍为A1→A2-01→完整A2→A3→A4→A5→A6→A7→A8→A9；
本轮仅A9有字节/计数漂移，旧组登记、测试集合及分母均无变化，无需改写旧scope。
下面的前后哈希按受控显式路径审阅，最后重绑A9；新模块一并固定，不只固定版本常量。

| 路径 | 审查前SHA-256 | 修复SHA-256 | 原因 |
| --- | --- | --- | --- |
| `intent/draft.md` | `853dd3fea4672faa1d3eb405b8a24a3f57d7035dc1f589a92b8b8350759ed7f5` | `ef685589dab5eb515410c3c87fa95e2efca22442a0b10bf307768a15e7c1e25e` | 当前结构/业务验证/配置/恢复与独立A9已交付的主规格说明 |
| `docs/contracts/read-validation.md` | `91a382371deffe076eefdd1d4b68ed79ed909ad9efa099bc0b02588f8fc114a8` | `78f25a0864060da05f4747729dd673f7e69c90cee5174a77235045972ee76924` | 明确±、完整10幂边界、逐端显式单位与底层诊断归属 |
| `docs/contracts/frozen-contracts.md` | `17f589899d6c840e27a2a61d80477d9395e1fdac01edc5f9c02c5757a3d4bb21` | `a8974bed5a23532e724c4bd1e215670e89950c0020713a47844f460fad1a254a` | 去除A9待交付措辞，保持A1历史证明范围 |
| `tests/fixtures/a9_coverage.json` | `8169c4354d126194a267f6d9bbd5b607e13028e90a291857b9a32f724cf25b63` | `36917e6f63fab382ad9b11afcbfb69b993d2e9e8a125596ee9e1dc09ba681650` | 隐私及数值能力材料闭包增加底层diagnostics模块 |
| `src/paper_radar/reading/__init__.py` | `a7a980453943233f5f40169205e74e22b5d81bfc959196bdbc746fd62c782f3a` | `46abc1b703683085ac1b770f0a431304f2784117daff97656e97e7a04e6cb2d4` | 公共诊断导出从底层定义导入，名称及wire值不变 |
| `src/paper_radar/reading/errors.py` | `f6a94e757422cb48be1ad0c391d7aad4056bfb191e9790e93ef398b295b88a29` | `8cb6363f973b754b944d3246cb370b3ade43cff8c8ab4f99723e941dc445f50c` | 去除对结果层的反向类型依赖 |
| `src/paper_radar/reading/numbers.py` | `18d543e2a438b2a6e5bd4a3ea479aeee656fd1acadee167a2bd74f21a9811f52` | `b11da527e562d6607ad7524f6400a40bbce7a2685d1b7486d823d58fefec5e2d` | 修复±漏检、10幂后缀误归一化与显式端点单位丢失 |
| `src/paper_radar/reading/result.py` | `5a7afb4bf43bb8451a6215e65813f62dbd486cc7b4b880b696b39c1eca4420ef` | `e7ad472d2e0676962ef102412923822533c86b222cb1f494b76a877134e294f4` | 复用底层诊断，保留原导出兼容且消除依赖环 |
| `tests/test_read_numbers.py` | `c857e9eb0196e09bef87b25b2b000e6622479b64b59733af98ca238fbd4b88ac` | `8e13756b89027d36fc0ad5effd2b825f2814741b257134cbfa71fa5f5f17a159` | 新增22项独立公共向量，分母57→79 |
| `tests/test_read_privacy.py` | `4d68a9f788f1b132bfe2c97e84ebaebd37b4505912bc2d29b992f89ff7975983` | `506b760c8bffdb712844473f6c5aecd536a28f7df162c67f22dcc8f014855ea7` | 两拒绝负例锁定准确安全路径及受控类别，分母仍3 |
| `src/paper_radar/reading/diagnostics.py` | `新增` | `5776997b330ac4b41fb93ccb98e50302c47feb8f250e91151bc086c27fcea576` | 新增不依赖上下文/结果的NumericReason与ReadDiagnostic定义 |

数值模块原57项，新79项：新增±负例4项与空格等价正例3项、幂后缀/未支持形状
负例5项与合法句号正例1项、范围显式单位负例5项与合法显式/隐式单位正例4项，
合计22项。预期先由上述参数化人工推导，再由独立collection确认79；其他模块数量
逐项不变。Read当前为421项，A9协议/入口/状态/scope仍120项，A9总分母541项。
独立收集execution=not_run，只核对分母；执行通过仍依据实际pytest与最终集成门禁。

本台账与a9_scope.py自身不在正文记录最终哈希，避免间接自哈希环；A9固定本台账
的实际字节，scope本身继续由完整工作树身份及self_reference/cycle拒绝保护。
最终完整check-offline由integration实际执行，旧提交的中断运行不作为通过证明。
真实PDF/Pi/模型/Docling/NAS、orig哈希归属、map来源链和完整阶段A仍未验证。
