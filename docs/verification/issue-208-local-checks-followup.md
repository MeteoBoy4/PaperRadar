# #208 本地检查补充覆盖

本次独立开发覆盖以 `37c7e6548f9437b7d1b05a834d778bf9ff017bc9` 为基线。
保留[首次覆盖](issue-208-local-checks.md)与[集成覆盖](issue-208-local-checks-integration.md)
的原字节，不扩大历史通过结论、required 集合或固定分母。过程判断见
[审阅处置依据](../../intent/review/issue-207-208-review-fix-evidence.md)。

## 独立 D1 覆盖

| 模块 | 基线节点 | 新增 | 当前节点 | 本次验证的公共行为 |
| --- | ---: | ---: | ---: | --- |
| `tests/test_check_local.py` | 18 | 4 | 22 | 缺失/已删除暂存配置各一项，ignored 本机回执一项，树内 TMPDIR 一项；已有 help/状态及 index 拒绝加强精确断言 |
| `tests/test_local_hooks.py` | 4 | 0 | 4 | hook 冲突原因码、用户更改后的安全卸载；从子目录提交、linked worktree、坏 index 阻止提交及原字节保持 |
| `tests/test_local_document_links.py` | 7 | 0 | 7 | 六类受控诊断与链接定位去重后，合成链接、锚点、图片、reference、代码排除等原行为 |

三模块合计 33 节点；既有节点、参数化与断言均保留。它们仍是未绑定的独立 D1，
不进入历史 A1–A10 回执或固定分母。

## 开发验证

环境：Linux、CPython 3.14.4、项目现有锁定离线环境；临时根为树外
`/tmp/paperradar-207-208/review-fix-tmp`。所有 Python 命令使用
`uv run --offline --locked …`，未联网补依赖。

| 验证 | 结果 |
| --- | --- |
| `pytest -q tests/test_check_local.py tests/test_local_hooks.py tests/test_local_document_links.py tests/test_live_document_links.py tests/test_scope_material_inventory.py tests/test_check_compatibility.py tests/test_version_consumer_checks.py tests/test_report_replay_projection.py` | 63 passed，9.49s |
| `./scripts/check-compatibility cli` | 8模块、59个去重节点，59 passed，pytest 76.18s，含 uv 总耗时76.75s，退出0 |
| `ruff format --check src tests scripts` / `ruff check src tests scripts` | 1341文件格式通过；lint通过 |
| `mypy` | 1340源文件通过 |
| `./scripts/check-local` 工作树 | format 0.056s、lint 0.062s、docs 0.572s，含uv总耗时0.764s，退出0 |
| 局部 `MYPYPATH=src … mypy` | 4个本次Python改动文件通过；最初未指定src的局部调用因跨包导入定位失败，最终全仓检查通过 |
| 显式基线 scope 审计及 `--collect` | `issues=[]`，无hash drift/敏感变化；285固定模块、5281去重节点，skip/deselect均0 |

本轮审计目标为稳定本地 `audit/207-208-review-base`（指向上述基线），
不将旧 `main` 基线已确认的依赖/inventory变化带入本轮。没有修改 scope、中央哈希、
inventory、依赖或旧冻结证据，无需重绑或生成新的逐组敏感确认。
提交后的最终 HEAD 与工作树身份由树外审计结果报告，旧身份确认不复用。

## 证明限制

仅在临时Git仓库安装/提交/卸载hook；真实仓库未安装。
三类版本消费者组合的旧计时/定向变异未重跑，原一次性重放摘要已补入上述处置依据，
不把旧运行当作本次树结论；本轮未改它们的注册表或版本语义。
未运行完整离线门禁、live、真实实验根、模型、Docling、NAS或push；
轻量检查、局部回归与只读scope审计均不构成正式验收。
