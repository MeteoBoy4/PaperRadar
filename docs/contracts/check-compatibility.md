# 开发期入口兼容检查

`./scripts/check-compatibility {acceptance,cli,all}` 是完整离线门禁之前的开发工具，
不是 `paper-radar` 产品命令。它只运行精选的入口兼容回归，不改变验收合格标准、
Frozen Contract 或既有历史证据。

## 参数与选择

只接受一个组合名：`acceptance` 检查验收入口/回执接线，`cli` 检查 CLI 注册/导入链，
`all` 按 `acceptance`、`cli` 顺序取有序并集。不接受任意 pytest 参数。
选择规则唯一登记在 `scripts/check_compatibility.py::CHECK_GROUPS`；清单及逐项理由由
`selection_documentation()` 派生到 `--help` 和[测试导航](../agents/testing.md#按变更类型运行开发期检查)。
它使用独立精选的公共回归，不自动扩展为所有 scope 测试，也不自动分析变更。
影响面无法确定时，开发者应运行 `all`。

入口先切换到仓库根目录。引导解释器优先取 `${UV_PROJECT_ENVIRONMENT-.venv}/bin/python`，
相对环境路径以仓库为准；仅当该文件不可执行时才查找 PATH 中的宿主 `python3`。
选中的解释器必须通过 Python >=3.12 检查；检查失败即退出 1 并提示准备环境，
不会因项目解释器版本过低或执行失败而再回退宿主。
引导使用 `-I -S -B`，禁用 site 初始化与字节码。

`-h` / `--help` 只打印中文帮助与完整选择清单并退出 0，不启动 uv、测试或文件写入。
无参数、未知组合、额外参数或未知选项退出 2，用中文说明原因及查看 `--help` 的下一步，
不运行测试。解释器检查先于帮助和参数解析，解释器不可用时仍退出 1。

## 执行、输出与失败

真实检查通过 `uv run --offline --locked …` 运行，只向一个 pytest 执行过程传入
所选模块/节点；完整 nodeid 去重，同一参数化用例只执行一次。不以全量 pytest 兜底。
输出先列选择项及数量，收集后列每项实际节点数与去重总数，然后显示 pytest 本地诊断、
结果、退出码和耗时；外层另报告含 uv 的总耗时。无法启动 uv 时输出
`launch_error`、中文下一步和入口结果/总耗时，没有选择收集数量。
uv 自身失败时保留其诊断及非零返回值。输出是终端文本，不提供 JSON 结果或正式验收回执；
分享前核对 pytest 诊断中的敏感输入。

空选择和缺失模块退出 1；缺失节点、空模块、收集失败或测试失败均非零，
不运行未选择的测试。pytest 收集错误会先给出具体模块和错误；未能收集不宣称通过。
返回 0 只表示本次开发期选择的 pytest 执行返回 0；返回 2 也可表示运行中断，
其余非零沿用 uv/pytest（例如 pytest 选择错误为 4）。

## 副作用与证据边界

所选回归使用临时文件、临时数据库及固定 fixture/mock，不访问实时来源、模型或用户数据库；
uv 可能同步锁定环境。测试进程在导入 pytest 前清除继承的
`PAPER_RADAR_TEST_RECEIPT`、`PAPER_RADAR_TEST_RUN_ID`、`PYTEST_ADDOPTS`、`PYTEST_PLUGINS`，
禁用第三方 pytest 插件自动加载、回执插件、pytest 缓存与字节码。
该清理不是对全部环境变量的隔离，也不是 OS 网络/文件系统沙箱；
CLI 帮助回归的 socket/SQLite 拒绝守卫由相应用例显式注入。
不写正式 `verification-runs/` 证据，不发布 A1–A10 结论。
仓库 `pyproject.toml` 的 `addopts` 保留，不在入口复制。
所选回归内部为验证发布语义而产生的文件仅位于测试临时目录。

既有产物数量、历史终端输出和禁网络/SQLite 守卫保持独立预期。
本入口只执行所选 pytest，不运行包含 lockfile、Ruff、mypy、全部 pytest 和冻结契约检查的
完整门禁，也不替代 `./scripts/check-offline`；开发期通过不继承历史验收资格，
不证明阶段 A 完成、live 就绪或校准资格。
完整门禁与历史查询见[离线证据说明](../verification/offline-evidence.md)和
[验证状态契约](verification-status.md)；阶段 A 收口与最终验收责任见
[路线图 A](../roadmap.md#module-a) / [I](../roadmap.md#module-i)。

入口自身的原因受控为 `empty_selection`、`missing_module`、`missing_node`、
`empty_module`、`launch_error`；结果为 `passed` 或 `failed`。标准进程退出码保持整数，
原样保留 uv/pytest 的其他非零返回值，不把外部失败强制归并为内部原因。
这些是入口受控词表，不表示每种 pytest 失败都带一个入口原因码。

## 相关

- 使用导航：[测试规则](../agents/testing.md#按变更类型运行开发期检查)。
- 依据：[入口包装](../../scripts/check-compatibility)、[选择与执行实现](../../scripts/check_compatibility.py)、
  [入口回归](../../tests/test_check_compatibility.py)、[pytest 配置](../../pyproject.toml)。
