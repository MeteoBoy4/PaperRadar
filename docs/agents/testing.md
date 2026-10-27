# 测试

- 修复 Bug 时，先写一个在修复前失败的回归测试。
- 负例必须断言受控的字段路径或错误类别，不能只凭异常类型就判定成功。
  ConfigError 的 AST 守卫仅检查 `match=` 或绑定后断言的形式；仅检查敏感内容未泄漏仍不足以满足此规范，断言的目标原因须人工审查。
- 常规测试完全离线：使用固定 fixture / mock，不访问实时网络、付费 API 或用户数据库。
- Live source 验收通过显式命令运行，且只在用户明确要求、配置和 credential 可用时运行。
- 新增或修改 migration 时，测试从上一 revision 升级到当前 revision；涉及快照或恢复的改动，测试恢复路径。
- 完整离线验证入口与证据格式见 `docs/verification/offline-evidence.md`。

## 按变更类型运行开发期检查

先运行本次功能的相关 `pytest` 子集，再按下面的触发条件运行入口兼容组合，
最后运行 `./scripts/check-offline`。功能测试与开发期组合均不能替代完整门禁。

| 变更类型 | 相关功能测试后运行 |
| --- | --- |
| 新增验收组、调整发布产物/回执接线/终态读取 | `./scripts/check-compatibility acceptance` |
| CLI 注册、帮助或包初始化/服务导入链 | `./scripts/check-compatibility cli` |
| 同时触及以上两类，或无法判断影响面 | `./scripts/check-compatibility all` |

`./scripts/check-compatibility --help` 只打印中文帮助与完整选择清单，不启动 uv、
测试或文件写入；沿用只读工具的项目 Python 引导，项目环境必须已准备。
实际检查统一通过 `uv run --offline --locked …` 运行。入口只接受一个明确组合名，
未知参数返回 2，不支持自动影响判断或任意 pytest 参数。

运行先列出有序测试选择，再报告实际选择的模块/节点数及去重后的总数，最后打印
pytest 结果、退出码和实测耗时（入口总耗时含 uv）。参数化按完整节点计数；
选择为空、模块/节点缺失或某个模块没有用例均返回非零，不会退回全量 pytest。
终端保留本地 pytest 诊断输出，分享前自行核对其中是否含敏感测试输入。

入口清除继承的正式回执/run_id、`PYTEST_ADDOPTS` 与 `PYTEST_PLUGINS`，禁用第三方
pytest 插件自动加载、pytest 缓存和字节码。测试仍会使用临时文件/数据库，uv 可能同步
锁定环境；不访问实时来源或用户数据库。开发期运行不写正式 `verification-runs/`
证据，不发布任何 A1–A10 结论，也不取得完整验收资格。

选择依据为独立精选的公共回归，唯一权威在
`scripts/check_compatibility.py::CHECK_GROUPS`，不是各 scope 的全部业务测试。
复用现有测试不会继承其历史通过结论。原产物数量、历史终端字节、帮助及禁外部 I/O
断言继续独立维护，不从生产输出机械推导预期。新增 CLI 冷进程帮助测试沿用现有
`deny_external_io` 的 socket/SQLite 拒绝守卫。

下表由 `selection_documentation()` 生成，与 `--help` 同源；调整清单时同步生成，
`tests/test_check_compatibility.py` 核对文档未漂移。这里只维护导航和派生清单，
不将详细测试列表复制到根 `AGENTS.md`。

<!-- compatibility-selections:start -->
| 组合 | 测试选择 | 选择理由 |
| --- | --- | --- |
| acceptance（验收入口/回执接线） | `tests/test_a2_full_entry.py` | 一次计划、正常/失败/中断产物与完整入口帮助 |
| acceptance（验收入口/回执接线） | `tests/test_a3_entry.py` | A3 发布中断及发布前字节复核 |
| acceptance（验收入口/回执接线） | `tests/test_a4_entry.py` | A4 必需组失败、发布中断与字节绑定 |
| acceptance（验收入口/回执接线） | `tests/test_a5_entry.py` | A5 必需组失败、发布中断与字节绑定 |
| acceptance（验收入口/回执接线） | `tests/test_a6_entry.py` | A6 依赖、嵌套回执隔离及发布失败 |
| acceptance（验收入口/回执接线） | `tests/test_a7_entry.py` | A7 依赖、嵌套回执隔离及发布失败 |
| acceptance（验收入口/回执接线） | `tests/test_a8_entry.py` | A8 依赖、嵌套回执隔离及发布失败 |
| acceptance（验收入口/回执接线） | `tests/test_a9_entry.py` | A9 Read 独立契约、回执隔离及发布失败 |
| acceptance（验收入口/回执接线） | `tests/test_a10_entry.py` | A10 接线、可选/必需组独立性及最终发布失败 |
| acceptance（验收入口/回执接线） | `tests/test_verification_run.py` | 登记扩展与非法登记拒绝 |
| acceptance（验收入口/回执接线） | `tests/test_verification_compatibility.py` | 独立历史终端字节、退出码和产物数量 |
| acceptance（验收入口/回执接线） | `tests/test_verification_status.py` | 可信终态、历史兼容与失败/中断查询 |
| cli（CLI 注册/导入链） | `tests/test_cli_help.py` | 已安装根命令/契约帮助及禁网络/SQLite 守卫 |
| cli（CLI 注册/导入链） | `tests/test_cli_import_compatibility.py` | 新旧命令冷进程帮助与禁 I/O 导入链 |
| cli（CLI 注册/导入链） | `tests/test_fixture_cli.py` | fixture 注册、查询、帮助与缺失数据库 |
| cli（CLI 注册/导入链） | `tests/test_fixture_pdf_cli.py` | PDF/backend 登记、查询及原字节行为 |
| cli（CLI 注册/导入链） | `tests/test_audit_cli.py` | audit 查询、帮助与无写入边界 |
| cli（CLI 注册/导入链） | `tests/test_audit_matrix_cli.py` | 摘要矩阵命令及安全输出 |
| cli（CLI 注册/导入链） | `tests/test_audit_resume_cli.py` | resume/replay 帮助、继续和只读回放 |
| cli（CLI 注册/导入链） | `tests/test_fixture_audit_references.py` | fixture 与 audit 的完整历史引用 |

`all` 是上面所有组合的有序并集，同一节点只执行一次。
<!-- compatibility-selections:end -->

复现/计时记录保存在被 Git 忽略的 `.scratch/issue-109/`：包含同环境的三个组合、
完整门禁的实际数量/耗时，以及隔离副本中“旧产物预期”和“提前服务导入”两类
受控回归的修前失败、修后通过原始输出。记录仅供开发诊断，不是正式验收文件。

## 开发环境

- 新 worktree 直接执行 `uv run --offline --locked …`，环境自动按锁文件同步，解释器由 `.python-version`（3.14）决定。
- 若 uv 报离线缓存缺包，须先取得用户联网授权，再用 `UV_PROJECT_ENVIRONMENT=$(mktemp -d)/venv uv sync --locked` 一次性补齐缓存，完成后删除这个临时环境；不复制 `.venv`。
- 临时根默认 `/tmp`，不能位于任何 Git 工作树内；worktree 与 `.venv` 放在磁盘上，不放在 `/tmp`。
- 长时间门禁前运行 `./scripts/dev-environment check`（可加 `--json`）。命令只读，不触发 uv 同步；入口优先使用项目环境的 Python（支持 `UV_PROJECT_ENVIRONMENT`，相对路径以仓库为准），缺失时以宿主 `python3` 启动，启动前验证 Python >=3.12。项目解释器实际版本单独通过 `bin/python -I -S -B` 查询，缺失或执行失败时报未知，不会把宿主版本当作项目版本。
- 容量须严格大于 5 GiB；配额读取失败显示“配额未知”并返回非零。配额采用非零软/硬上限中的较小者，保守忽略宽限期。inode 数与 pytest 残留仅报告和提示；不设 inode 数量门禁，残留统计不完整也不导致失败，部分体积附 `size_complete=false` 和不可读条目数。清理命令只可在没有 pytest 运行时手动执行。
- 为保持不写文件，临时根按 `tempfile` 的候选顺序通过目录权限选择，再解析符号链接；不调用会创建探测文件的 `tempfile.gettempdir()`。JSON 与文本均标记 `temporary_probe=access_only`；只读权限检查不能验证实际写入能否成功。未知系统调用 ABI（如 MIPS、x32）仍按“配额未知”处理，不盲用编号 443。
