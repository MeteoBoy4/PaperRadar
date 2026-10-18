# Issue #36 阶段 A4 全量审查（Standards / Spec 双轴，r2）

- 固定点：`main` = `7c177b8919ba2b7695a66ebcd55611a91cd7a532`（`git rev-parse main` 已确认）
- Diff 命令：`git diff main...HEAD`（98 文件，+16643/−93，非空）
- Commit 列表（`git log main..HEAD --oneline`，31 个）：
  - `6d18861` Merge issue #36 reviewed Pi supply corrections
  - `a33aad0` Fix Pi supply doctor protection and reconcile review findings
  - `a977b4d` Merge issue #45 same-run A4 lifecycle acceptance
  - `1965a19` Implement issue #45 same-run A4 lifecycle acceptance
  - `699d32f` Merge issue #43 audited Pi cleanup execution and recovery
  - `63e7497` fix(pi-supply): preserve tree execution bits during cleanup permission repair
  - `905ae19` feat(pi-supply): execute immutable cleanup plans with retirement recovery
  - `78e7bfb` Merge issue #42 immutable Pi cleanup planning
  - `6e2e90b` Reject unreadable installation trees instead of silently skipping entries
  - `600def8` Reject ambiguous retired locations and preserve consistent plan queries
  - `8d1d0ad` Merge latest integration with Pi material export
  - `70249b8` Format retired cleanup projection
  - `0c3d957` Add immutable Pi installation cleanup plans
  - `ebc1ed6` Merge issue #44 fixed supply export and isolated history restore
  - `13e739e` Merge branch 'integration/issue-36-pi-supply' into implement/issue-44-export
  - `46d4d5f` Merge issue #41 inherited flock installation protection
  - `7e58ae0` test(pi-supply): align CLI process substitutes with inherited descriptors
  - `afae703` fix(pi-supply): separate exported materials from registered runtime roots
  - `f263b4b` feat(pi-supply): protect installation use with inherited flock handles
  - `3bf36ac` fix(pi-supply): reject unavailable safe export capabilities cleanly
  - `aec9ef8` feat(pi-supply): export fixed materials and prove isolated history restore
  - `0188999` Merge issue #40 atomic Pi selection and read-only diagnostics
  - `728c8ba` feat(pi-supply): activate one execution selection and diagnose supply read-only
  - `6407c49` Merge issue #39 Pi instance verification and frozen rebuild
  - `7e9fbde` test(pi-supply): align acceptance and restore fixtures with a402 head
  - `394586a` feat(pi-supply): verify instances and rebuild from frozen materials
  - `2812396` Merge issue #38 immutable Pi supply preparation
  - `b8047c6` fix(pi-supply): reject normalized source escapes and persist root parents
  - `10c67ee` feat(pi-supply): prepare immutable supplies and audit install instances
  - `e952e18` Merge issue #37 Pi 1.3.0 supply spike
  - `3faea6c` docs: record Pi 1.3.0 supply mechanism spike
- 规格来源：GitHub Issues #36（父票正文、实施前补充、六项裁决、第二补充、Pi 1.3.0 更正）与子票 #37–#45；本地抓取 `/tmp/review/spec/issue-36.md`…`issue-45.md`，另用 `docs/verification/a4-requirements.md`、`docs/contracts/pi-supply.md`、`docs/verification/offline-evidence.md`、`intent/draft.md` 对齐。
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/{python-conventions,testing,refactor,documentation,invariants,cli-output,scope}.md`、`docs/verification/offline-evidence.md`、`docs/contracts/{pi-supply,backup-restore}.md`、`docs/adr/` + Fowler smell 基线。
- 审查方式：Standards 与 Spec 两个 `delegate` 子代理并行（均带 bash/grep/read 与 `gh` 只读权限，明确禁止改文件、禁止 commit），本文件只做聚合与复核，不混合两轴排序。本轮未修改代码、未创建 commit。
- 与既有文件的关系：`intent/review/issue-36-a4-full-review.md`（同固定点、同规模的上一轮，目前未跟踪）内容相近；本轮为独立复跑，并对两轴最重发现做了 shell 复核。

### 聚合者复核（保持两轴分离，仅校正证据与定级）

1. **Standards #1 降级**：`git diff main...HEAD -- docs/adr/` 显示 ADR-0029 是本分支新增（`/dev/null → b/...`），`905ae19` 只是同一未合并分支内的修订，且以「2026-10-18，Issue #43 安全更正」段落显式记录了语义翻转与理由。这不同于改写已合入 `main` 的 ADR，不构成 `docs/agents/invariants.md` / `documentation.md` 的硬违规；只剩「分支内 ADR 反复改写、读者需读到底部更正」的可追溯性判断题。
2. **Standards #2 部分纠正**：`intent/draft.md:908` 的 `.tools/pi/<supply_id>/<install_id>/` 是父票裁决 2 明确要求并按 `documentation.md` 同步的改动（`issue-36`「布局改为 `<install-root>/<supply_id>/<install_id>/`…按 `documentation.md` 同步修改 §6」），不是越界。真正的范围越界只有 3 处纯空行（`intent/draft.md:661`、`:1049`、`:1062` 附近）。
3. **Spec #3 降级**：`docs/contracts/pi-supply.md:150` 明确写「list/show/export 只回查历史，不检查现场」，且 `src/paper_radar/pi_supply/cli.py:217` 显式披露「未核验现场」。因此这不是漏核验，而是父票 Decision 10（「查询不能只信历史登记而跳过现场核验」）与本 diff 自家 Contract 的口径分歧，需用户裁决措辞；`service.py:103/107` 的纯库读本身属实。
4. **Spec #1 维持**：父票评论已自述「仍有 1 项规格范围待用户裁决…原生 Windows 未实现/未验证」，父票保持 OPEN；`export.py:165-167` 的 `hasattr(os, flag)` 能力门属实。
5. **Spec #2 维持（本轴最高优先）**：`models.py:39-41` 的 `RequestEvidence.path` 仅 `bool(path)` 非空校验，`service.py:384` 直接 `request_path.parent / item.path`；绝对路径会替换基目录、`..` 可越界，测试无逃逸反例。
6. **其余抽查属实**：Standards #3–#8（`repository.read_state` 职责聚合、`models.py` 两处 `shape` 校验近乎逐行重复、`cli.py` 10 处 `except SupplyError`/5 处 `KeyboardInterrupt` 样板、`__init__.py` 转发别名、三根结伴传参、`a4_acceptance.py` 硬编码跨阶段 scope/issue 对）；Spec #4（`cleanup_execute.py:127-144` 的 `active` 在 `_assert_facts`/第二轮 `_check_item` 失败时停在末项）、#5（`cli.py:423` 无「需要后续语义评估」输出）、#6（`<db>.pi-supply.lock`、`.root.lock`、`.prepare-*.lock` 均未写入 Contract，`pi-supply.md` 只登记 `.locks/<install_id>.lock`）、#7（`pi_app` 与 `supply_app` 共用 `GROUP_HELP`，`pi --help` 列出只存在于 `pi supply` 下的子命令）。

> 下两节为子代理报告原文（仅排版微调）。其 #1/#2 的「硬违规」定级以上节复核为准。

## Standards

审查基准：`git diff main...HEAD`（98 文件）。子代理自述硬违规 2 条，其余为 Fowler 基线判断题；成文标准优先。

**1.〔硬违规·文档〕既成 ADR 裁决被原地改写**
`docs/agents/invariants.md:3`「有意偏离时先新增 ADR」、`documentation.md:12`「架构决策…新增 ADR」。但 `905ae19` 在 `docs/adr/0029…flock.md` 内直接替换原文：`-本决策不实现退役、trash 或删除` → `+Issue #43 的退役、trash 与删除继续遵守…`，并把「执行路径可为历史缺锁实例安全初始化」改成相反语义，只在文末追加「安全更正」段。历史读者无法分辨 #41 当时的裁决，也无法按 supersede 关系回溯。应新增 ADR 或显式标注 supersede。

**2.〔硬违规·范围·轻〕`AGENTS.md`「改动范围以任务所需为界」**
`intent/draft.md` 的 4 处新增仅为类间空行：`intent/draft.md:661`、`1048`、`1062` 附近（diff `@@ -657` / `@@ -1045` / `@@ -1057`），与 Pi 供给无关；同文件 `:908` 的 `.tools/pi/<supply_id>/<install_id>/` 属行为表述变更，`documentation.md` 要求已获用户允许——本 diff 无该证据，列为待确认。

**3.〔判断题·Divergent Change / Long Method〕** `repository.py:105 read_state` 一个函数承担材料回放、激活引用闭包、清理计划、执行历史、重建失败五类校验（`repository.py:105-430`），模块 647 行同时含事务写入（`commit_supply`/`commit_install`/`commit_activation`）与查询；`service.py` 853 行同层。对照 `docs/agents/refactor.md`「每个模块职责单一…Agent 只读单个模块即可完成该模块内的工作」，新增 `cleanup_history.py` 已拆分而 `read_state` 未同步。

**4.〔判断题·Duplicated Code〕** `models.py:47-57` 与 `103-117`（`RequestEvidence.shape`/`Evidence.shape`）、`71-77` 与 `131-137`（`complete`）近乎逐行重复；`cleanup_history.py:141-145` 与 `212-216` 两个 `rows()` 完全相同；`cleanup.py:365-376` 与 `cleanup_execute.py:201-230` 共享同一「两次读 facts + 校验」骨架，`show_cleanup_plan`/`show_cleanup_execution` 同为线性扫描+同错。

**5.〔判断题·Duplicated Code + Shotgun Surgery〕** `pi_supply/cli.py` 9 个命令各写一遍 `except SupplyError→exit 2 / KeyboardInterrupt→130`：`:139-144`、`177-179`、`218-220`、`246-251`、`312-317`、`357-362`、`403-408`、`562-569`、`663-668`；另 `:618`+`:626-628` 取全部执行记录后在 CLI 侧过滤 `plan_id`，该查询应下沉。

**6.〔判断题·Middle Man + Mysterious Name〕** `__init__.py:50-234` 20 个纯转发，别名不揭示作用（`list_supplies as discover`、`show_cleanup_plan as show`、`available_installs as available`、`probe_install as probe`）；`execution.py:66-70 retention_protection` 仅转发 `retention.retention_protection`（别名 `_retention_protection`）。

**7.〔判断题·Data Clumps + Long Parameter List〕** 三个实际根恒同行：`filesystem.py:26 safe_roots(database, install, data, config, material)`、`cleanup.py:77 check_cleanup_root(..., data, config, material)`、`cleanup_execute.py:88-95` 再拆成三个 `Path(plan.*)`；`service.py:628 _build_tree` 9 个位置参数。测试侧同类：`tests/pi_supply_support.py:155` 返回 `tuple[Path, str, Path, Download, Run]` 被 `source[0]`/`source[1]` 索引约 640 次（`test_pi_supply_cleanup_execute.py` 105 次、`test_pi_supply_protection.py` 111 次），`tests/a4_acceptance_support.py:19` 是 8 元组。

**8.〔判断题·Repeated Switches / Long Method〕** `scripts/a4_acceptance.py:167 write_a4_conclusion` 约 190 行，其中 `:225-260` 一段 40 行 OR 链硬编码 `"a1_screening_authoritative_contracts"/13`、`"a2_versioned_config_snapshots"/25`、`"a3_artifact_backup_restore"/35`，与 `a1_acceptance.py:326`、`a2_full_acceptance.py:217`、`a3_acceptance.py:227` 重复同一知识；A3/A2 scope 改名将迫使 4 文件同改。

**一句带过**：`service.py:60-61` 以 `as _platform`/`as _check_root_marker` 导入公开函数（名不副实）；`repository.py:360` 函数内 import `selection`，而 `selection` 不依赖 repository（无循环，属多余延迟导入，与「依赖扁平」相悖）；`materials.py:45` 条件表达式直接充当 if 条件；测试新增 94 处函数内 import（main 为 30）；未发现覆盖退役/trash 不可撤销删除的 ADR。文档同步抽查合格：`CONTEXT.md`、`README.md`、`docs/contracts/pi-supply.md`、`docs/verification/offline-evidence.md`、migration head `a405_pi_cleanup_execution` 与代码一致。

## Spec

**子票 #37–#45 验收判定**

| 子票 | 判定 | 一句话依据 |
| --- | --- | --- |
| #37 A4-01 | 已实现 | 1.3.0 spike 文档 + fixture，按 AC 只交付调查记录 |
| #38 A4-02 | 部分 | prepare/list/show、派生锁、a401、备份回放齐备；证据路径约束缺失（发现 2） |
| #39 A4-03 | 已实现 | verify 逐实例追加检查；rebuild 只回放冻结材料、新随机实例、a402 |
| #40 A4-04 | 已实现 | 唯一选择+只追加激活事件、全槽匹配、doctor 显式 scope/未知退 2、a403 |
| #41 A4-05 | 已实现 | 树外 flock、pass_fds 继承、真实父子进程与竞争用例 |
| #42 A4-06 | 已实现 | 不可变计划、库级四实例窗口、实际树身份、a404 |
| #43 A4-07 | 部分 | 退役→trash→删除与强杀恢复齐备；失败归因有偏差（发现 4） |
| #44 A4-08 | 部分 | 七类文件导出、非空 WAL 隔离恢复；export 平台/能力未收口（发现 1） |
| #45 A4-09 | 已实现 | 30 模块/346 例与静态用例数逐一对齐，六主文件+回执、十能力、live 恒 false |

**发现（按严重度）**

1. **[a｜高] export 仍受平台/安全文件能力限制，与"不受平台限制"未收口。** #36 第二补充 §9："list/show/export、备份恢复与隔离查询不受平台限制"；#44 验收："list/show/export 及备份恢复查询无平台/Node/Pi/网络前置"。代码 `export.py:165-167` 缺 `O_DIRECTORY/O_NOFOLLOW/O_NONBLOCK` 即 `export_failed`，原生 Windows 未实现；`docs/contracts/pi-supply.md:197-199` 自行降级为"受控失败"。父票评论已列为待用户裁决，故 #44 只能判"部分"。
2. **[c｜中] evidence_file 路径未限制在请求目录内。** 补充一 15："D5 依据和证据文件的路径相对请求文件解析"（`a4-requirements.md:126` 同）；#38："证据路径相对请求解析"。`models.py:32` 的 `path: str` 无校验，`service.py:384` 直接 `_read_small(request_path.parent / item.path)`——绝对路径或 `../../x` 会被读取并冻结成 D5 证据（≤4 MiB）；测试只用 `evidence.txt` 相对名，无逃逸用例。
3. **[c｜中低] list/show 不核现场，与 Decision 10 口径冲突。** #36 Decision 10："安装存在性属于本机事实，查询不能只信历史登记而跳过现场核验"。`service.py:103/107` 纯库读，`cli.py:217` 自述"未核验现场"；现场核验只在 doctor/activate/句柄（`protection.py:67`），历史查询与"当前可用"易被混读。
4. **[c｜低] 清理执行的前置失败被记到"最后一个候选"名下。** #43："逐项记录完成/失败/未运行……不把部分完成说成成功"。`cleanup_execute.py:130` 初始化 `active=plan.candidates[0]`，首轮循环后 `active` 停在末项；随后 `_assert_facts`（133）或第二轮 `_check_item`（142-143）失败时，`_record_failure` 记到最后一个候选，非实际对象，逐项审计失真。
5. **[a｜低] D5 `may_change/unknown` 未在 CLI 显示"需要后续语义评估"。** Decision 17："'可能改变行为''无法判定'都显示需要后续相关语义评估"。`cli.py:423` 只打印 `decision/basis`，无分支；该语义仅存在于 `pi-supply.md:49` 文档，show/doctor 输出无法体现。
6. **[b｜低] 数据根新增持久 `<db>.pi-supply.lock`，规格未要求且无清理。** `service.py:494/535` 在数据库旁建锁文件；Decision 10/21 只授权 SQLite 事实，README 未提该文件，`cleanup.py:_manual` 只扫安装根，属未受管副作用。
7. **[b｜低] `paper-radar pi --help` 复用 supply 组文案，列出 pi 级不存在的子命令。** `cli.py:55/92-98` 中 `pi_app` 与 `supply_app` 共用 `GROUP_HELP`（"prepare 准备；verify……"），但 `pi` 下只有 `supply`；与 Decision 24"根与所有新层级中文 help……完整"的准确性不符。

**残余风险**：发现 1 为已知待裁决阻断；发现 2、4 无测试覆盖；子代理未运行 pytest/`check-offline`（只读约束），判定基于 read/grep 与静态用例数核对。

## 汇总（分轴，不跨轴排序）

- **Standards 轴**：8 项发现（子代理标 2 项硬违规 + 6 项判断题；经复核仅剩 1 项可判硬违规——`intent/draft.md` 三处纯空行属任务范围越界）。按结构风险最重的是 #3：`repository.read_state` 与 `service.py` 把材料回放、激活闭包、清理计划、执行历史、重建失败塞进 647/853 行模块，与 `docs/agents/refactor.md`「单模块可独立完成本模块工作」相悖。
- **Spec 轴**：1 张子票判定表 + 7 项发现（2 项缺失/半成品，2 项 scope creep，3 项实现疑点）。最重的是 #2：`RequestEvidence.path` 未约束相对性，`service.py:384` 的 `request_path.parent / item.path` 可被绝对路径或 `..` 逃逸（#38「证据路径相对请求解析」），且无拒绝测试；#1 的 export 平台未收口是父票仍 OPEN 的已知阻断，非新发现。
