# Issue #36 阶段 A4 全量审查（Standards / Spec 双轴）

- 固定点：`main` = `7c177b8919ba2b7695a66ebcd55611a91cd7a532`
- Diff 命令：`git diff main...HEAD`（98 文件，+16643/−93）
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
- 规格来源：GitHub Issues #36（父票正文 + 三条裁决评论 issuecomment-6243720810 / 6243820754 / 6243849006）与子票 #37–#45（A4-01 至 A4-09）
- 标准来源：`AGENTS.md`、`CONTEXT.md`、`docs/agents/{python-conventions,testing,refactor,cli-output,invariants,scope,documentation}.md`、`docs/verification/offline-evidence.md`、`docs/adr/` + Fowler smell 基线
- 审查方式：Standards 与 Spec 两个 `delegate` 子代理并行（均带 Bash/git/gh 只读权限，明确禁止改文件与建 commit），仅聚合不混合排序；本次审查未修改代码、未创建 commit

### 聚合者抽查注记

聚合者对两轴各自最重的发现做了 shell 复核，均属实：
- Standards #1：`git diff main...HEAD -- intent/draft.md` 确认在合法供给布局/A4 结论改动之间混入 `EvidenceRef`/`SupportedStatement`/`ReusablePoint`/`ReadAnalysisOutput` 类间纯空行格式改动。
- Spec (a)1：`src/paper_radar/pi_supply/models.py::RequestEvidence.shape` 对 `evidence_file` 仅校验 `bool(self.path)`（非空），`service.py:384` 以 `request_path.parent / item.path` 拼接——pathlib 语义下绝对路径整体替换基目录、`..` 可越界，与 #38「证据路径相对请求解析」的收紧意图不符，且未见拒绝测试。

以下两节为子代理报告原文（仅排版微调）。

## Standards

审查方法说明：全量 stat 清单 + 重点逐 hunk 审查；子代理具备 shell/git 只读权限，直接运行 `git diff main...HEAD` 及分路径 diff。

**覆盖范围**：全量 stat 清单 + 重点逐 hunk 审查 `src/paper_radar/pi_supply/`（21 个新模块）、5 个 migration、`scripts/a4_*`、backup/cli 接线、docs/ADR、intent/draft.md；测试按支撑文件与迁移用例抽查。

### 成文标准符合性（未见硬违规的主干）
- python-conventions.md（httpx 规则）：`transport.py` 显式超时、`follow_redirects=False` 逐跳 `checked_url` 白名单、`trust_env=False`、流式 `download_limit`——合规；httpx 入 pyproject+uv.lock。
- invariants.md：a401–a405 经 Alembic、历史只追加、备份 revision 同步 bump（`backup/manifest.py`）。
- documentation.md：CONTEXT.md 术语、ADR-0028/0029、`docs/contracts/pi-supply.md`、README、offline-evidence.md、a4-requirements.md 均同变更更新。
- testing.md：迁移有「上一 revision 升级」回归（a401/a402/a403/a404→a405）；测试全离线 fixture；bugfix commit 均带回归测试。
- cli-output.md：help/错误全中文、含原因+下一步，`--help` 纯本地。

### 发现
1. **边界越界（偏硬违规）**：`intent/draft.md` diff 混入与 Pi supply 无关的纯空行格式改动（`EvidenceRef`/`SupportedStatement`/`BoundaryOutput` 等类间双空行）。违反 AGENTS.md「改动范围以任务所需为界；拆分、整理只在本次触及的模块内进行」。
2. **Duplicated Code（判断题）**：`scripts/a4_acceptance.py` 是 `a3_acceptance.py` 近似逐行复制——`_reason`/`_environment`/`_migrated_revision`（50–166 行）仅 A3→A4 改名，`write_*_conclusion` 骨架同构。底层原语已共享（verification_checks.py），这三个 helper 未提取；offline-evidence.md 允许各组自管判据，属判断题。
3. **Duplicated Code/Message Chains（判断题）**：`instance.path.parent.parent` 出现 17 处/6 文件（protection.py:73,384、cleanup.py:147,221、cleanup_execute.py:87、repository.py:380,601 等）——安装根概念靠目录层级导航，宜在 `InstallInstance` 上建 `root` 属性；`.trash/<install_id>` 派生散布 3 处。
4. **Data Clumps（判断题）**：`data_root/config_root/material_root`（+install_root）结伴穿越 `prepare_supply`/`rebuild_supply`/`create_cleanup_plan`/`safe_roots`/`check_cleanup_root`/CLI 选项/plan 字段（各约 30 处），一个 roots 布局类型想出生。
5. **Primitive Obsession（判断题）**：`re.fullmatch(r"[0-9a-f]{64}"/"{32}")` ID 校验散布 11 处（service.py:108、cleanup.py:380、cleanup_execute.py:234、protection.py:166、repository.py 5 处等）；models.py 已有 `Hash` annotated 类型未复用。
6. **Middle Man（判断题，已缓解）**：`pi_supply/__init__.py` 20 个薄转发 wrapper；docstring 声明理由（延迟 I/O 使 help 不加载数据库/网络模块），支撑 cli-output「--help 纯本地」，可接受。
7. **Speculative Generality（轻微，有 ADR 背书）**：`use_install`（按快照取当前选择）生产零调用、仅测试使用；ADR-0029 明确描述该使用方协议，为未来 RPC 预留，点名但不判违规。

未发现 Mysterious Name、Feature Envy、Repeated Switches、Shotgun Surgery（a2_scope 等哈希重绑是文档化流程）、Divergent Change、Refused Bequest 的显著实例。

## Spec

**覆盖范围**：`src/paper_radar/pi_supply/` 全部 20 个模块、CLI、a401–a405 迁移、backup/adapters/check-offline 改动、a4_scope/a4_acceptance、spike 文档、Contract/ADR/invariants 及测试清单（抽查约 80 个用例名，未逐行读全部测试体与 1494 行 lock fixture）。

**(a) spec 要求但缺失/半成品**

1. D5 `evidence_file` 路径未约束相对性：`service.py::_freeze_d5` 用 `request_path.parent / item.path`，而 `models.py::RequestEvidence.path` 只查非空。绝对路径会整体替换基目录、`..` 可越界，把任意本机 ≤4MiB 文件原字节冻结入库。#38 验收要求「证据路径相对请求解析」，且未见拒绝测试。轻微（用户显式请求、属非秘密审计材料），建议补拒绝规则与测试。

除此之外未发现缺失：prepare/verify/rebuild/activate/保护/gc plan+execute/export/doctor、六项裁决（单选择全槽比对、`<supply_id>/<install_id>` 布局、证据三态+baseline、derived-lock-v1+ADR-0028、三源白名单+显式代理、a302 批次不放宽）、第二补充各项（并发幂等、install-policy-v1、`.trash` 单列、arch/libc 探测拒绝、statvfs 预检、导出固定命名）均已在代码/测试/文档中对上；#45 六份结论、capabilities、`live_install_verified=False` 齐备；#37 spike 有 1.3.0 正负例（EINTEGRITY）记录。

**(b) scope creep**

未发现 spec 外能力（无 task 框架/RPC/业务表）。`local_filesystem`（mountinfo 拒网络盘）、`renameat2` 不覆盖发布、`read_state` 每次查询全量语义回放均是对应裁决的收紧落实，非扩大。

**(c) 实现方式疑点**

1. `filesystem.py::check_space` 用固定 512 MiB 下限（错误提示也写死）。第二补充第 10 条建议「staging+发布树两份的粗略下限」；若未来双树+Node 归档超 512 MiB，预检失去前移失败作用。低风险，可改为按归档/树规模估算。

其余重点核对（白名单逐跳、树哈希规则、四棵保留窗与 scope 分离保护、计划事实绑定与 trash 重入、export 碰撞拒绝、doctor 退出码）实现与 spec 一致。

**剩余风险**：真实下载/安装 live 路径未在本审查运行；重定向 6 跳上限为实现自定值（spec 未定数）。

## 汇总（分轴，不跨轴排序）

- **Standards 轴**：7 项发现（1 项偏硬违规 + 6 项判断题/注记）；最重为 #1 `intent/draft.md` 混入与任务无关的空行格式改动（AGENTS.md 任务边界规则）。
- **Spec 轴**：2 项发现（1 缺失/半成品 + 1 实现疑点，无 scope creep）；最重为 D5 `evidence_file` 路径未约束相对性（#38「证据路径相对请求解析」）。
