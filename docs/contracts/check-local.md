# 轻量本地检查

## 用途与范围

`./scripts/check-local [check] [--staged]` 是只读开发检查入口。手工调用默认检查工作树，
`--staged` 检查 Git index 的树外临时快照；直接调用独立于 hook 安装。
入口依次显示 format、lint、docs 的结果、失败诊断和耗时，并报告含 uv 的入口总耗时。

## 规则

### 检查与环境

Ruff 参数与路径直接派生自 `scripts/offline_evidence.py::default_checks()` 中的
`format`、`lint` 项；不另维护命令清单。外层以 `uv run --offline --locked` 准备锁定环境，
worker 使用该环境的 Python 调用 Ruff 模块，对所选树运行同源参数。
快照不执行自己的 Python 代码、不另建 editable 环境，Ruff 配置取所选树。

只读指不改被检查源码、index 或提交内容；uv 可能同步锁定项目环境。
Ruff cache 与 Python bytecode 禁用，index 快照在树外创建并在成功、失败后清理。
`TMPDIR` 指向工作树内时 staged 检查受控失败；可设 `TMPDIR=/tmp`。
入口不自动修复、暂存或 stash。坏 index 与已修复的工作树并存时 staged 检查仍失败；
好 index 与未暂存的坏工作树并存时，结果只取 index。文档目标未暂存也不能通过 staged 检查。
向快照外引用的符号链接受控拒绝。

缺 uv、Git、锁定依赖或必需工具时返回非零并给出准备环境的命令；
离线缓存不足时遵循[开发环境准备规则](../agents/testing.md#开发环境)，不会自动联网补包。
入口不读取 credential 或真实实验根，不调用实时服务。

### 活文档链接

来源唯一取 `docs/verification/scope-material-inventory.json` 的
`classification_rules.live_documents.exact_paths`，不递归扫描 Markdown。
目标可以是任意仓库内本地文件，绝对站内路径以仓库根解析；普通相对路径以来源目录解析，
URL 路径与 fragment 百分号解码后核对。外部 URL、mailto 等只识别为外部链接，不联网校验。

CommonMark parser 处理 inline、reference、collapsed、shortcut 链接和本地图片，
链接标签中的 inline code 保留；fenced/indented code block 与 code span 示例不作链接。
非 Markdown 目标只核对存在性，不解释 fragment。Markdown 目标的页内及跨文件锚点
支持中文、大小写、Unicode 标点、标题内 inline code、重复标题与名称碰撞的数字后缀，
以及仓库使用的显式 `<a id="…"></a>`。其他原始 HTML 形式和全文渲染不在范围内。

来源未登记的历史原件、ADR、覆盖台账等不作为扫描来源，保持原字节；
未知 Markdown 同样不扫描，仍按[固定材料规则](../agents/verification-scope.md)处理，
不宣称其链接通过、不自动归入豁免。新增活 Contract 需精确分类审阅。
本机忽略回执没有全局豁免；活文档引用缺失的本机回执同样失败，不能用主工作树文件
满足 staged 快照。历史非活文档中保留的旧引用不转成断链 allowlist。

### Hook 生命周期

仅在用户显式运行 `./scripts/check-local install` 后安装 pre-commit；
hook 只执行 `./scripts/check-local --staged`，复用同一实现、参数与退出语义。
路径通过 Git `rev-parse --git-path` 解析，支持 `.git` 为文件的 linked worktree；
默认 hooks 由同一仓库的 linked worktrees 共用，安装和卸载都会影响这些 worktrees。
仅精确匹配托管内容的重复安装幂等，安装后具有可执行权限。

`./scripts/check-local uninstall` 只删除仍精确匹配的自有 hook；不存在时幂等成功。
工具不写 Git 配置。任何已有 `core.hooksPath` 或非自有 pre-commit（含符号链接）均受控停止，
保持原文件/配置，提示手工集成同一命令或自行处理冲突。用户后来改过的 hook 不删除；
后来设置的 `hooksPath` 也不撤销。工具不提供 chaining、自动合并或自动接管。
Git 原生 `git commit --no-verify` 只绕过 hook，不能解释为检查通过。

## 错误与拒绝

退出 0 表示此次所选树的三个轻量检查通过；任一失败返回非零。
参数错误返回 2，启动/安装/解析/检查失败返回 1 或保留 uv 的其他非零退出码。
诊断含来源路径、行号、原 destination 和 `missing_target` / `missing_anchor`；
无法读取来源、目标或 inventory 分别给出 `source_error`、`target_error`、`invalid_inventory`，
树外目标给出 `outside_repository`，不以解析失败冒充无链接通过。
hook 冲突分别给出 `hook_conflict`、`hooks_path_conflict`；启动失败给出 `launch_error`。
`--help` 纯本地输出，不启动 uv 或检查，缺项目环境时可用 Python >=3.12 的宿主解释器。

## 不提供／不证明

入口不运行 mypy、pytest、入口兼容组合、scope 审计、冻结契约或完整离线门禁，
不发布 lockfile 或正式验收结论，不写 `verification-runs/`。
相关开发回归仍按[测试导航](../agents/testing.md#按变更类型运行开发期检查)显式运行；
完整门禁仅在用户明确授权后运行。通过不证明产品、模型、Docling、真实来源或 NAS 行为。

## 相关

- [README 使用入口](../../README.md#完整离线验证)、[独立 D1 与计时](../verification/issue-208-local-checks.md)。
- 依据：[规格及补充评论](https://github.com/MeteoBoy4/PaperRadar/issues/208)、
  [统一实现](../../scripts/check_local.py)、[链接检查](../../scripts/live_document_links.py)、
  [hook 适配](../../scripts/local_hooks.py)。
