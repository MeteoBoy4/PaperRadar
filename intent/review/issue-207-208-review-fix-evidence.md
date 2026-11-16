# #207 / #208 审阅处置依据

本轮以 `37c7e6548f9437b7d1b05a834d778bf9ff017bc9` 为基线，在原
`integration/207-208` 分支修复。两份审查报告原文保留，处置逐项追加在各报告末尾。
审查意见不是新规格；依据为两票正文与所有者补充评论（评论优先）。

## 冻结证据与旧确认

`docs/verification/issue-208-local-checks-integration.md` 是已交付的按次冻结证据，
不原地删除过程段落或追改其当时的待确认状态。其信息归属问题在后续记录中纠正，
本轮过程只写在 `intent/review/`，新增覆盖另建台账。

树外 `208-final-scope-confirmed.json` 已记录旧树 HEAD `37c7e65`、target
`integration/207-208` 当时的 commit `c1ad601`，四类变化的 22 条逐组确认均有对应组，
`issues=[]`；`integration-final-scope.json` 的结构/字节审计也为 `issues=[]`。
因此报告 r2 的“尚未完成确认”对旧树已过时。这些文件不能证明修复后的树；
本轮使用稳定本地 `audit/207-208-review-base` 指向 `37c7e65`，重新显式审计，
不以 `main` 为基线重新引入旧变化，也不复用旧确认。

## #207 旧缺陷重放的仓库内摘要

以下为原一次性隔离重放的核对结果，不是本轮重跑或正式验收。
`207-replay-results.json` 的三个 `selected_by` 与本轮当前 `select_tests(group)`
逐项相同，且各自包含下表节点所在模块。原脚本先确认这一成员关系，再只对该节点调用
既有 runner；这是组合目录的可达性加窄节点重放，不声称对变异运行了整组。
两票允许一次性验收材料，不入库变异或通用 mutation-testing 框架。

| 组与节点 | 变异、实际失败边界 | 原重放结果 |
| --- | --- | --- |
| renderer：`tests/test_report_replay_projection.py::test_report_replay_rejects_changed_registration_across_calls` | 当前 renderer 2 的负例改回替换 1；`assert altered != original and len(altered) == len(original)` 失败 | red 1、green 0；1 failed / 1 passed |
| source-guard：`tests/test_live_epoch_upgrade.py::test_changed_source_copy_refuses_stale_guard` | 准备真实存在的 v28 manifest；`assert 'pi-admission-v28' == 'pi-admission-v29'` 失败 | red 1、green 0；1 failed / 1 passed |
| migration：`tests/test_experiment_exposure_migrations.py::test_nonempty_reports_revision_upgrade_failure_retry_and_restore[None]` | 合法 v1 升级后真实追加一条 renderer v2 历史；降级到达 `ValueError: renderer_v2_history_present` | red 1、green 0；1 failed / 1 passed |

原日志均含上述精确 `FAILED` 节点；red 无 `FileNotFoundError` 或
`ModuleNotFoundError`。原日志 SHA-256 如下，原始材料保存在树外
`/tmp/paperradar-207-208/207-replay-{group}-{red,green}.log`。
摘要可随仓库复核选择关系与边界；原始隔离执行仍依赖一次性材料，不等于可直接复现的框架。

| 组 | red SHA-256 | green SHA-256 |
| --- | --- | --- |
| renderer | `495aead2be5d711d9f5aeccaeb44afbe754f8b54057dd5140f9c8885ba75fee8` | `e449d027c8da4a1bdd60c85d8af7a6e28aaf40bb67728e716a49b50fc072ff06` |
| source-guard | `cd05286742aa1a267b48abcb072f98477ee58d9d3b84a3e6fafe60176eb00385` | `fa053b95b0bf7f49c45ca5dce2c010a8839eaf0c694f05bbd1bad00e8745e550` |
| migration | `6cafbb517182e0cf3eb370d3b6d8d66979ffad736f2c8274126d5be05d38e293` | `79290859cc5bc679ef9c04ead47dcbafe9f46617b2dd7396975d616c994b6016` |

## 本轮判断与验证方法

已确认的公共 seam 为本地 CLI、临时 Git 仓库安装/提交/卸载、合成活文档根、
兼容组合选择/帮助/计数/退出，以及隔离副本重放。本轮故障先红后绿：
hook 冲突的精确前缀、中文 help、staged 缺配置两例均在修复前失败。
ignored 回执和树内 TMPDIR 是既有安全行为的补充覆盖，初跑即绿，不虚称为新故障。

临时 hook 提交从 `src/` 子目录运行，另保留 linked worktree 安装/提交/卸载；
真实开发仓库没有安装 hook。缓存/字节码禁止、index 与工作树保持、deny_external_io、
旧 links 四项及 inventory 检查均在受影响子集中验证。

模块拆分建议仅采纳当前局部重复；跨入口 bootstrap/Parser、私有 index tuple 的全面重构
没有本轮错误证据，不新增模块或扩展公共接口。`manage_hook(root, install=...)` 的关键字
已表达意图，无需为单个调用改成一套 action 框架。
显式 HTML 锚点仅承诺仓库已有 `<a id="…"></a>`；多属性 HTML 被所有者明确排除，
不能以审查建议扩大范围。现有中文/标点/inline code/重复后缀/碰撞用例继续通过；
本轮不宣称完整 GitHub 渲染等价。

intent-to-add 只有空 blob，不能代表已暂存目标；非 UTF-8 路径不能如实解析并诊断；
submodule 不含其文件树、unmerged 没有唯一 stage-0 内容；外向或成环 symlink 不构成
封闭快照。这些拒绝服务于“只查 index 且不借工作树补齐”的安全边界，保留并说明理由。

验证数量、命令与限制见[独立覆盖台账](../../docs/verification/issue-208-local-checks-followup.md)。
本轮全程未运行完整离线门禁、live、真实实验根、模型、Docling、NAS、联网补依赖或 push。
