# 轻量本地检查的独立工程覆盖

依据：[#208 与补充评论](https://github.com/MeteoBoy4/PaperRadar/issues/208)。
本台账登记新开发入口与链接检查的 D1 覆盖，不扩大历史分母、required 集合或既有回执。

## 新增 D1 模块

| 模块 | 节点数 | 覆盖 |
| --- | --- | --- |
| `tests/test_local_document_links.py` | 7 | 合成树的 CommonMark 各类链接、中文/重复/显式锚点、代码排除、原目标诊断、无效 inventory/来源/目标、未知及历史来源边界 |
| `tests/test_check_local.py` | 6 | 工作树只读、两向部分暂存、未暂存链接目标、禁网络/SQLite、缺 uv 受控失败 |
| `tests/test_local_hooks.py` | 4 | 隔离 HOME/Git 配置的临时仓库安装/卸载、幂等/可执行权限、冲突原字节、真实提交阻止与放行、linked worktree |

测试 seam 为轻量 CLI（工作树/staged）、临时 Git 仓库生命周期、合成文档树诊断。
三个新增模块独立未绑定。`tests/test_live_document_links.py` 四项原断言和文件字节保持，
继续验证原 evidence-link 范围；新完整链接校验由独立 D1 模块承担。

## 分类与固定范围

仅新增精确活路径 `docs/contracts/check-local.md`，不扫描目录自动放行。
`tests/test_scope_material_inventory.py` 仅给 `authorized_additions` 加这一条，
保留旧基线集合、断言和节点数。现有 inventory 绑定/分母和历史原件保持。
`pyproject.toml`、`uv.lock` 仅显式声明锁内 `markdown-it-py` 4.2.0 为 dev 依赖，
其他依赖版本及锁内分母保持；不依赖 Rich/Docling 的传递安装偶然性。
Ruff 参数直接消费原 `default_checks()`，不改完整门禁计划。
新增分类、依赖身份及守卫变化的 scope 候选由串行集成按[固定范围规则](../agents/verification-scope.md)审阅；
本票不机械重绑历史测试或证据哈希。

## 开发期验证与计时

环境为 Linux x86_64、Python 3.14.4；锁定 Ruff 0.16.8、markdown-it-py 4.2.0。
当前工作树为共同固定点 `50485e2d9ad7d4b68780f24e79ebf9b9ac074202` 加本票改动；
轻量入口实际检查 1340 个 Python 文件和 inventory 的 36 份精确活文档。

| 测量 | format | lint | docs | 入口总耗时（含 uv） |
| --- | --- | --- | --- | --- |
| 工作树直接调用 | 0.061s | 0.063s | 0.586s | 0.784s |
| 临时仓库完整 index 的真实 pre-commit | 0.061s | 0.071s | 0.603s | 1.000s |

hook 测量将当前 2134 个非忽略材料复制到独立临时 Git 仓库，隔离 HOME、全局/系统
Git 配置、签名与凭据；预同步锁定环境后安装 hook 并实际提交。含 Git 自身的墙钟为
1.081s；成功后整个临时库清理。以上测量不设秒数门槛，不代表未来机器性能保证。
原始开发日志保存在树外 `/tmp/paperradar-207-208/`，不是正式验收回执。

相关 pytest 子集 25 项通过（上述 17 个 D1 节点、旧链接 4 项、inventory 守卫 4 项）；
全仓 Ruff format/lint 通过，mypy 1339 文件通过，`uv lock --check --offline` 通过。
`./scripts/check-compatibility cli` 59 项通过，pytest 132.34s，入口含 uv 132.92s。
只读 scope 审计的基线无既有漂移；当前仅 `pyproject.toml`（2 条）与 `uv.lock`（1 条）
出现预期 `hash_drift`，另有 inventory 精确分类与依赖身份共 21 条逐组
`confirmation_required` 候选，由串行集成审阅并只重绑必要精确材料。

## 证明限制

hook 只安装在临时测试仓库，未安装到开发者真实仓库。
没有运行完整离线门禁、发布正式回执或验证任何 live 行为；
相关入口兼容回归是开发检查，不代替最终树正式验收。
