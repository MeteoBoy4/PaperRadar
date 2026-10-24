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
