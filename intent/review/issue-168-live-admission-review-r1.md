# Live 准入双轴代码审查（r1）

- 固定点：`main`（`b133d4eb333530f6c017b821d588a1087d6123ba`）
- 审查命令：`git diff main...HEAD`
- 规格来源：GitHub Issues `#168`–`#176`
- 范围说明：仅记录本次已产生的子代理结论；未修改产品代码，未创建 commit。

## Standards

Standards 子代理启动失败，未产生审查结论：当前 Kimi Code 套餐不支持该子代理配置请求的 1M context（HTTP 403）。因此本轴为**未完成**，不能解释为“无发现”。

## Spec

已审 `main...HEAD`、#168–#176 及 ADR-0052–0056。发现两项；未运行测试。

1. **实现错误／部分：D7 可绕过，且续行授权代码漏出守卫。**  
   #173 要求：“**准入/RPC 相关实现变化而策略版本未升则失败**”。但 `a925a45` 修改 closure/deployment 代码后仍保持 `pi-admission-v4`（`current_binding.py:22`），同时重写 v4 manifest 及锚（`tests/test_live_admission_source_guard.py:78-81`）；`test_manifest_rebinding_without_policy_change_fails` 仅篡改内存副本，无法发现锚被替换。另两个执行撤销、恢复和激活的 `issue176_resume_after_backup*.py` 未列入 `SOURCE_FILES:56-64`。影响：相关改动可在不升版时通过守卫。最小修复：升为新策略、追加新 manifest/锚并保留 v4 原字节，将续行脚本纳入守卫。

2. **实现错误：混合“漂移＋普通资格缺口”会误撤销无关能力。**  
   #171 要求：“**逐组件漂移或失败撤销受影响资格……无关历史状态与原验证时间不改写**”；ADR-0056 进一步明确自然到期只当次拒绝。`admission_guard.py:89-105` 却把所有带任意 reasons 的必需项加入 `failed`，再在 `:122-134` 作为 `failed_capabilities` 持久撤销。因此一项绑定漂移伴随另一项到期／未激活时，后者也被不可逆撤销，需新回执才能恢复。现有漂移测试与 `test_ordinary_qualification_gaps_do_not_revoke_independent_evidence` 仅分别覆盖单一场景，混合场景**未覆盖**。最小修复：只把漂移依赖项或明确失败项送入收紧，并新增混合回归。

其余未发现可证实的缺失或 scope creep；B/H 日报嵌入属明确下游交付，不计缺失。

---

汇总：Standards 未完成（无结论）；Spec 共 2 项发现，其中本轴最严重的是 D-7 源码守卫可绕过。

## 本轮逐项核实与处置（追加，原报告全文保留）

核实基线为 `integration/168-live-admission@5b97d7603a5d011bc57449390f41c79beca84d06`。
独立实现者重新读取 #168–#176 正文、全部评论及完整原生关系；父 #168 仍 OPEN，子票关闭不作为本轮验证结论。
执行 diagnosing-bugs／tdd；实际 root、保护来源、凭据、认证、模型和网络行为均未运行。

| 项目 | 核实结论与依据 | 采纳／拒绝与具体实现 | 回归与关联 Issue |
| --- | --- | --- | --- |
| Spec 1：D7 与续行脚本 | 属实，包含两种缺口。续行脚本不在旧显式清单；历史也确有同版本重绑：独立 `git show` 核得 `3de64e7` 的 v4 manifest SHA 为 `a155a511f9556c1a346644686e04dd5c88f22ba93b846525b62d9607d3ffe548`，`a925a45` 变为 `ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1`，两提交的 `ADMISSION_POLICY_VERSION` 均为 v4。这是 D7 升版／审阅流程缺口。测试无法防止改测试自身是额外的同 uid 源码威胁边界，不是否认该旧流程问题的理由。 | 采纳新策略、显式扩充与磁盘反例；当前源码升 `pi-admission-v5`，新增独立 v5 manifest／摘要锚，显式覆盖 46 源，包括两续行工具、共享检查点、collector、site_tree、owner CLI 与产品 tree_hash 来源。历史与现已部署 v4 不回写，旧 v1–v4 manifest／锚原字节保留，v4 SHA 仍为 `ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1`。后继须升新策略并追加新锚，不以重算旧键覆盖审阅约束。 | 新增磁盘源码改变、磁盘重绑 manifest 两个冷进程反例，均核对具体拒绝；新增 v4 原字节断言。当前 v5 与部署 v4 不同，须所有者重新审阅新包及部署／新证据激活，不实际执行。Refs #168、#172、#173、#176。 |
| Spec 2：混合漂移与普通资格缺口 | 属实。`tighten()` 把带任意 reasons 的必需项归为 failed；真实两消费者在 cwd 漂移伴随独立 RPC 到期／未激活／unknown 时会将 RPC 一并持久撤销，违反 #171 与 ADR-0056。 | 采纳。只把明确的绑定／材料漂移项加入受影响集合，显式运行失败仍沿现有失败集合收紧；物理来源失信仍整体保守收紧。普通资格不足只拒绝本次，不转成不可逆失败事实。 | 两正式入口 × 三缺口共六例经过真实账本／共享 guard，原错误筛选下全部在无关项 `revoked` 断言 red，修后保持无关资格、原 claim／verified_at 与回执字节，受影响项持久收紧。原来源失信／helper 失败／事务检查点回归保留。Refs #168、#171、#173、#174。 |

实际命令、结果、当前节点与冻结边界见[本轮独立 D1](../../docs/verification/issue-168-176-review-r1-r2-fixes.md)。
本追加没有补做 r1 的 Standards 审查，也没有将其“未完成”改写成通过；没有重跑 code-review 或完整离线门禁，没有沿用旧树的同 run 结论。
