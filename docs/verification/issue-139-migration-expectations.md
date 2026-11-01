# Issue #139 测试迁移预期集中化

依据：[#139](https://github.com/MeteoBoy4/PaperRadar/issues/139)，上游评估 [#138](https://github.com/MeteoBoy4/PaperRadar/issues/138#issuecomment-6553649345)。

## 基线与范围

实际初始 HEAD 与本地 target `main` 均为 `5a3a543fcd5d57e445f28451830ae03b48624590`，
初始 dirty=false。实施分支 `implement/issue-139`，独立 worktree `.worktrees/issue-139`。
重盘当前 head 文本为 46 文件、61 处，与评估完全一致；其中 Python 44 文件、57 处，
两份活 Contract 另有 4 处。唯一 Alembic head 未推进，既有 migration 节点未改。

32 个测试/支撑文件等量替换 34 处 E 和 10 处 F。E 保留实际结果与人工预期的比较；
F 仅插值 down_revision，future revision 名与受控拒绝断言不变。未改生产代码、
刻意保留的历史 revision、fixtures、Frozen Contract、版本、Stage fingerprint 或历史回执。
既有测试函数、参数化与 REQUIRED_TEST_CASE_COUNTS 保持。

## 逐文件处置及字节登记

E = 当前 head 人工预期；F = 人工 future 探针的父节点。旧 SHA 来自上述基线，
新 SHA 为最终文件字节；仅重算这些实际变化材料在中央或单组 scope 中的登记。

| 文件 | E | F | 旧 SHA-256 | 新 SHA-256 | 理由 |
| --- | ---: | ---: | --- | --- | --- |
| `tests/a10_recovery_support.py` | 2 | 0 | `33416bfdb4c224fc1100af5bc053ee3eb563b34de07ac2a6bce8439ffaa2beb3` | `307d14e07db43c270ecd63bce70faaeec2674d3a0477da1b8cc9dad501edad68` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a10_integrity.py` | 0 | 1 | `87060a1084532011f78230314d278030f53dff38245d58ecb64aa13780b3a239` | `49e43ecaec3bedb6c3af819cb599f8d8a7ed8a49aa28745500843ebfa07fb97e` | future 父节点插值，受控拒绝不变 |
| `tests/test_a2_acceptance.py` | 1 | 0 | `a74bab43404c6b38aaed45bbb9cbb4e0f6d47ab2ae96270563f92c0a86ef1fec` | `956c3c35606751d97b01057df5d53c8d00ddcc2a44c0865263a9c4352c54e0c7` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a2_full_acceptance.py` | 1 | 1 | `86a6c0e2657ad4909f01daeebd033c9bd56185c1f637a298573aa2d05c9c254c` | `a6aa253c1a3547b56ce734308d16eb96be90266f79115986a86c43bb356148f6` | 保留实际迁移/恢复/输出与人工预期比较；future 父节点插值，受控拒绝不变 |
| `tests/test_a3_acceptance.py` | 2 | 1 | `b4a1dc2ecd7e0bc93a64e04af1b3962429518e3dd3d611e30f7b3b6ee77ea0fc` | `9f388ea326b86aa2734769629c21d8f47588b7493305c203b7cd88783eedbca3` | 保留实际迁移/恢复/输出与人工预期比较；future 父节点插值，受控拒绝不变 |
| `tests/test_a4_acceptance.py` | 1 | 1 | `6ef2a010b5ef1922b7b43b34b91ff998323d0527116f6ad626ae0a5c8e5795f1` | `56fcf11a518ac89b05a58e6fe41ece955e3ff49e099bab5eaef92b6573ac3894` | 保留实际迁移/恢复/输出与人工预期比较；future 父节点插值，受控拒绝不变 |
| `tests/test_a5_acceptance.py` | 1 | 1 | `68f3686fb54d225d5f76b8e434b55f9709a8f303ccbfcabc9623f3cbd18f2095` | `8f5c500e722b33fb73cb7f36bbef8ef1ff3d43440ab9995833100f15a3ad8445` | 保留实际迁移/恢复/输出与人工预期比较；future 父节点插值，受控拒绝不变 |
| `tests/test_a6_acceptance.py` | 1 | 0 | `828977e575b2bf62ec1e02013d132df6169cfb29a0853ddefe53c6c9b201d8ec` | `1b6ae4f260ac651041d77758de51663501e72b38a4a3860312810b4873170fd2` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a6_integrity.py` | 0 | 1 | `d3783a4fd7a4a0f8a7d7b9b4a478e087c89b182501c45804b469a942e562b31c` | `353e59b22a320811f1fd851d5db94ce4ca074f36603bd8deee6469c8ddbda646` | future 父节点插值，受控拒绝不变 |
| `tests/test_a7_acceptance.py` | 1 | 0 | `22309eec15893a1d9f34bc11bd6221662c6bf7b55f7a8e3c5e5a87b78ced29bd` | `bc517972142a5ad9336897cb97344e2e31cbcf3e2a7ab5c80c1bee9c66b7cfa2` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a7_attempt_migrations.py` | 2 | 0 | `6b1e5db3b2301a16153ac758e4eec8f352c3566fe126fba6a5a2cdffdb44d24a` | `198f4cf315700145032410d49b3b07fe1ab3fe51e5fb131da45f2ba24b26ca53` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a7_integrity.py` | 0 | 1 | `d10c7561392bc841925f565b11b8ef6c3977e5d66d091e2b2532862c0feb68b0` | `8a25915cbac7927c8a1b9f1ab6d4a47595628c4119772cff520f46a0fca95986` | future 父节点插值，受控拒绝不变 |
| `tests/test_a7_registration_migrations.py` | 2 | 0 | `b54875c45c1cd9b3568165841f345aed3eaf73f76dc1ec5d2a4d1b6b37f8c9ad` | `686efabe18a0b5920dabe6fb600c9f07758b295c163252df071b46a9948f27ad` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a7_retry_migrations.py` | 2 | 0 | `b2894320c179083c01789e0595779a1fa6ab8ea4c896e7d3570329471af891dd` | `64a8c97a09769a0b039aa6e77794a8438f27b2af7dc4c1b2fac3817ed2fa5b54` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a7_success_migrations.py` | 2 | 0 | `b00c27c92ebbafef9ae933baa076bb01e07195f627f880853cf11a296dee4385` | `05b70f51724e9d4771042aec3a5fef7b7ca34232b1d76859f076bebc1ee6b20e` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a8_acceptance.py` | 1 | 0 | `246d46f5ce30ebfa6797dc7badf31d5ee8ed057c499bced60588c45707803058` | `41331ea0537acfcbf4713d705f766290ce2b1fae8b741c026e5e139ae57bb934` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a8_integrity.py` | 0 | 1 | `92aba8745d851129c287b4d1e06655ccd6c7a25b55f88feafcfacb7f4f1521e3` | `b55a9d690e0b968c72caece31696aa42c8abf1c3b45e392682d1769a8a4cf33e` | future 父节点插值，受控拒绝不变 |
| `tests/test_a9_acceptance.py` | 1 | 0 | `2cbd937ba93b0cf1de2ef1fe3c5ef2ffd023c22bf5d983d22668368bef3a96cf` | `7571198f0b5c9d1ba03a7a0168966d24b4aa67c65d3c8426703c5ffb63dcc2e6` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_a9_integrity.py` | 0 | 1 | `ebc1181bcc35320fc097cb2ccae6422372c3fff2e58c795472b12bff10cce1fe` | `db80392c0fc68b630b71b9efecb92140b6551b061e9c1207018d85ef339ee873` | future 父节点插值，受控拒绝不变 |
| `tests/test_backup_failures.py` | 0 | 1 | `18f12ea21f0368d17f1eb4913fdda2705ac163f02ed3b1ad6134269c3d89a153` | `8f9ac9003640285f24c6f24bdc751ce96031006cc37fa6b217795b5aee1d6817` | future 父节点插值，受控拒绝不变 |
| `tests/test_feed_metadata_recovery.py` | 1 | 0 | `78b129e9bdbd6764797d0d7b4f5d5e1dc7dc074902fdb35bd0393fb5755314db` | `c308ca075aae6f0b0355831c78ebdab614bd7d092681e54effe90321b11e1dd3` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_fixture_recovery.py` | 2 | 0 | `11606ce5c3c7528c3d1411ab4ce7c8a29c096124b0c39ef68c31e6c7e6af7cc0` | `fb1ca60549b486a4157be0ac4476722bb1e7b4c6fa778797115c4b5c481b0922` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_pi_supply_activation_history.py` | 1 | 0 | `3681d91c936e3a56f1c98b47e228a127102dbf13119a597de675db1d2969a4ad` | `724aec9beed606ceea0593dd8496c376b3e06676f844babd6e5659780a48a993` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_pi_supply_cleanup_execute_history.py` | 1 | 0 | `13c8c0e44fc1ed99c895646a213f4577871e88151ea3fb0bb0980b059ffb22f0` | `c973bc2602619c959cff3caad2ecfc9de5fc17652526c2b67e637ae748f3e3f8` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_pi_supply_cleanup_history.py` | 1 | 0 | `a92978df3e34b386fb8632766831cfe3669fc67cbdc71631e0b752c64841338e` | `066ed18b293b186d960d52afcb8ec5896540acab9c4626909eb6443067fecb41` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_pi_supply_history.py` | 1 | 0 | `c24d20749f95a2e1424c81a0239757d960f4920a9fee17ddf2b3d0c4e63c2632` | `c4551e147ccf2c30cf3f2a7cb499dadd26552619301f602953a8a2a271da4d2c` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_pi_supply_rebuild_history.py` | 1 | 0 | `59cf8dabfc4bb74614d6e21e634947b7486ca07fa1e714c637873f814b428f73` | `b814f1e692608b5e00c6d0886791cf6282143ef9164390e2b03b082729b146d5` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_restore_service.py` | 1 | 0 | `c7011496dd054ffb561e42267bf02e3ea1b97c36e3950314e28e116643527180` | `4efb6f4378aa966e26826112f4931c7bb7af9180d9fbb08ffb0ba34cc43de023` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_source_backup.py` | 1 | 0 | `ad48b6ecea65191f6f576fe451c0fe3daada00011dd1e66270c1441e94d639e6` | `05d2756b4707d7553da72b45f779a5210c8c312b464885e2b14b0ecd8401a80a` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_source_migrations.py` | 1 | 0 | `f6611c4eb3cec0afceb8f4773088aba3579269b6d22c0834cb564a58405540e1` | `b55a61641ccd82d09861b82d7aaa94ebfd9eea2a403aa544ece700e3c815283f` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_storage_migrations.py` | 2 | 0 | `495bf2467b7d0c5082f6df126501a4debafa5cd982a662eb4552594b06e0d315` | `aa0f739ec2395e30476067f2f26c64d953ae7fe016feb57ebc8ff59f25f323e2` | 保留实际迁移/恢复/输出与人工预期比较 |
| `tests/test_version_relation_migrations.py` | 1 | 0 | `3fb7bafe4c9a773b98fc97168ae86b3cb24bbc9bbc0796164662743d660f811c` | `bbde4bb1cfb06ceda609c26d78e70ed5c4b9048ecb052148ac0c7db04a10b698` | 保留实际迁移/恢复/输出与人工预期比较 |

`tests/test_feed_metadata_recovery.py` 未登记到既有十组，仍修改并执行。
31 个登记测试/支撑文件的原组成员资格不变；不修改固定计数。

## 新增成员资格

新文件 `tests/migration_expectations.py` 只有人工字符串常量与维护约束 docstring，
没有生产代码、scope 或 Alembic 导入。中央登记新 SHA：`df2c2df234a8dcc6029befaff39df032327a093c560805b2ca2bf6bef93a6c8f`。

| 组 | kind | 用途 |
| --- | --- | --- |
| A2-01 | source | 独立人工迁移预期，约束测试与 future 探针 |
| 完整 A2 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A3 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A4 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A5 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A6 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A7 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A8 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A9 | fixture | 独立人工迁移预期，约束测试与 future 探针 |
| A10 | fixture | 独立人工迁移预期，约束测试与 future 探针 |

A2-01 沿用历史 writer 的 source 检查路径，不修改 A2_01_GROUP 或 a2_acceptance.py。
其余九组按 fixture 登记；任一组 fixture 用途使该路径对全部十组敏感。
新增成员不进入测试分母，不修改审计分类规则。

## D1 与验证边界

独立未绑定模块 `tests/test_migration_expectations.py`：1 个用例
`test_current_migration_literal_has_single_owner`，扫描 tests 下除 fixtures 子树外全部
Python 文本，仅允许人工常量文件出现当前 head 字面值。初次运行检出原 32 文件并失败，
集中化后通过。它不扫描 scripts/src/docs，不约束历史 revision，不进入既有组回执。

实际恢复支撑闭包由 `rg` 核实：`test_a10_behavior_coverage.py` 直接调用，
`test_a10_complete_recovery.py` 直接调用并通过 `python -m tests.a10_recovery_reader`
跨进程消费；其余 scope/integrity/status 的文本引用并非新增运行消费者。

## 后续推进 head

人工更新集合实测保持评估的 14 个既有文件、17 处文本：10 个 scope 的
MIGRATION_REVISION（10 处），A3 backup_database_revision（1 处），本票新建人工
常量（1 处），生产 BACKUP_DATABASE_REVISION（1 处），两份活 Contract（4 处）。
另维护两个中央哈希点：人工常量及生产备份声明。新 migration 的 revision/down_revision
另外登记；不得改写旧节点、历史 fixture/证据或刻意作为升级起点的旧 revision。

首个 Body/B migration 开工前核实本票完成；关闭前创建则原生 blocked-by 依赖本票。
实际争用 Alembic head 的票保持线性串行。仅更新常量仍须对 A2-01、完整 A2、A3–A10
全部十组逐项 S3 敏感确认，确认绑定最终 base/HEAD/target/完整树且置于树外。
该串行约束不构成 B/Body 对 Scope 的功能依赖。

本台账不宣称完整离线门禁、完整阶段 A 或 live 就绪；没有执行网络来源、模型、
Docling 或 NAS 验收。最终身份的审计 JSON 与确认材料留在被审计树外。

## 开发验证实测

- 31 个直接测试模块、两个实际恢复消费者与 D1（共 34 模块、1012 用例）均已取得通过结果。
  首次组合为 1011 passed、1 failed（505.54s）：补写本台账期间触发 A4
  `test_every_predecessor_must_independently_bind_and_pass[status-full]` 的
  `identity_changed` 保护；材料稳定后该具体用例复跑通过。A4 独立复跑另为 84 passed。
  这里不把首次组合记为退出 0，也不把组合结果当作完整离线门禁。
- `./scripts/check-compatibility acceptance`：117 passed，退出 0（214.00s）。
- `uv run --offline --locked ruff check .`、mypy 均通过；mypy 检查 712 个文件。
  改动 Python 文件的 Ruff 格式检查通过；32 个既有文件仅内联新常量后 AST 与旧版完全等价。
- 默认审计及 `--collect` 的登记核对无漂移；285 个去重模块、5281 个固定用例，
  `collection_skipped=0`、`deselected=0`、`reason=ok`，固定计数未改。
  显式 base/target 的敏感变化按具体路径、用途和全部传递影响组逐项审阅；最终确认
  绑定最终提交及树身份放在 `/tmp/issue139-confirmations.json`，不复用中间身份。
- 临时将常量改错：E 的成功/失败/kill 三分支及 F 探针全部失败；恢复后与 D1 共五例通过。
  临时在测试文件写回当前 head 文本：D1 失败；改动已恢复，不提交探针。
- 仅改常量的审计实测：变化为 `sensitive/fixture`，要求 A2-01、完整 A2、A3–A10
  十组确认；没有修改分类规则。探针报告 `/tmp/issue139-constant-only.json`，属于开发诊断。
- 独立双轴代码审阅：Standards 0 项、Spec 0 项；D1 最终精确排除 tests/fixtures 的调整
  经 Spec 轴复核通过。完整 `check-offline` 与 live 未执行。
