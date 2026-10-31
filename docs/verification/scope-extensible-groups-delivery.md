# 验收组扩展机制与一次性测试准备

本台账记录 #135 的机制与 S4(b) 一次性准备。完整逐项材料、旧新 SHA、分母、实际消费组和六冻结模块身份见 [JSON 台账](scope-extensible-groups-delivery.json)。它不改变历史证据、当前 required 集合或完整阶段 A 的结论。

生产声明 `scripts/verification_groups.py::GROUPS` 决定顺序、writer、required、直接前置和回执 scope；writer 在执行时才加载。帮助只读轻量声明，不启动 uv、数据库、业务 writer 或证据发布。回执保留所有显式模块，包括未执行模块的零记录，各 writer 仍独立核对固定分母。现有执行与发布接口不新增测试注入参数。

人工预期 `tests/fixtures/verification_group_expectations.json` 与读取支撑 `tests/verification_expectations.py` 分别声明帮助、组后缀、基础证据/receipt/terminal，以及原始历史 stdout 组。它们不导入生产登记，不读取实际产物来生成预期。两者作为敏感 fixture 经中央登记；轻量生产声明作为 source 经中央登记。历史读者继续独立声明 `SUPPORTED_GROUP_FORMATS`，未知后缀或版本包括可选组都拒绝，生产表不永久加入合成后缀。

## 一次性准备

完整 rg、AST 与生产绑定交叉核对的范围为 **10 个已绑定模块、12 处总份数断言，另 1 处帮助断言**，不是票面最初的四模块。固定测试分母合计 78，不增加、不减少这些模块用例。

| 模块 | 固定分母 | 总份数位置 | 帮助位置 |
| --- | ---: | ---: | ---: |
| `test_a2_full_entry.py` | 7 | 1 | 1 |
| `test_a4_entry.py` | 5 | 1 | 0 |
| `test_a5_entry.py` | 5 | 1 | 0 |
| `test_a6_entry.py` | 9 | 1 | 0 |
| `test_a7_entry.py` | 9 | 1 | 0 |
| `test_a8_entry.py` | 9 | 1 | 0 |
| `test_a9_entry.py` | 10 | 2 | 0 |
| `test_a10_entry.py` | 10 | 2 | 0 |
| `test_verification_run.py` | 5 | 1 | 0 |
| `test_verification_compatibility.py` | 9 | 1 | 0 |

总数断言改为人工预期的完整后缀集合与数量双重核对；失败/中断仍明确缺 pytest receipt。帮助 fixture 除脚本外显式复制轻量声明，仍保持零环境/数据库/证据产物。启动不使用会绕过 `sitecustomize` 的 `-I/-S`；主动注入 socket 与 SQLite 调用确认哨兵仍然生效。

既有 `fake_checks` 是模拟检查执行器的边界 fixture。为使旧 entry 单测能模拟未来已登记组，它只消费独立数据 `fixture_receipt_modules` 中明确的模块与正整数分母；这不证明那些模块实际执行。真实合成链路覆盖该模拟脚本，只把既有旧组 fixture 合入目标真实 pytest 原始回执，绝不回填目标的 collected/passed 或改变其完成/退出事实。

compatibility 只按独立清单排除明确声明的非历史组；原历史 stdout、全部 stderr、退出码仍逐字比较。每个声明组必须按顺序输出且各有一条结论和结果；未知或漏更新组前缀拒绝。原 transcript、发布中断前缀数量及已发布字节核对不改，A10 历史摘录的原文“十四份”不改。

一次性消费闭包新增 28 个成员：10 组 source 登记轻量声明，9 组的 18 个 fixture 成员登记独立数据及读取支撑（A3 的既有 entry 也消费模拟执行器）。中央新增三路径，总计 255 路径；旧测试成员、固定计数与 41 refs 全部保留。未绑定迁移回归只显式加入这些新增成员，仍核对原材料完整集合、固定分母、图和历史展开等价；逐项兼容修改另列 JSON，不重写 132–134 台账。

## 独立新覆盖

`tests/test_extensible_acceptance.py` 共 22 例，required=false。隔离副本在准备后追加一个 required 合成组，提供真正收集执行的两个 pytest 用例、真实 writer/原子发布、terminal 和状态 CLI 查询。正常结果为 passed/verified/same，查询前后证据字节不变。

负例包括 skip、deselect、失败、collect-only 的 incomplete、缺执行、缺模块、缺记录、错分母、缺产物、发布失败、未声明后缀（含可选组）、未知格式，以及生产新增但独立预期漏更新。帮助还使用不存在的 writer/scope 证明惰性加载，并主动检查外部 I/O 哨兵。独立预期数据在公开基线审计中仍为敏感 fixture，涵盖九个实际消费组。

扩展前保存全部 11 个旧 scope 与 10 个准备后测试模块 SHA；只改副本的生产声明、独立预期数据、读者支持声明及其中央 SHA，追加新组专属模块，再逐文件核查这些旧字节相同。旧 entry 单测的模拟执行结果与新增目标的真实执行事实分别记录，不以其中一项替代另一项。

开发期相关组合、兼容 all 与扩展副本旧 10 模块的实际结果见 #135 交接记录。它们均不作为完整离线门禁；#137 负责最终审阅、必要重绑和用户授权的唯一门禁。未运行 live，不提供 #114/#120、四刊、Pi RPC、模型质量、正式校准、Docling、NAS 或完整阶段 A 的新结论。
