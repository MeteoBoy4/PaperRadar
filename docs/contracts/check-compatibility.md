# 开发期入口兼容检查

`./scripts/check-compatibility {acceptance,cli,all}` 是完整离线门禁之前的开发工具。
它不改变产品 CLI、验收合格标准、Frozen Contract 或既有历史证据。

## 参数与选择

只接受一个组合名：`acceptance` 检查验收入口/回执接线，`cli` 检查 CLI 注册/导入链，
`all` 是两者的有序并集。选择规则唯一登记在
`scripts/check_compatibility.py::CHECK_GROUPS`；清单及逐项理由由
`selection_documentation()` 派生到 `--help` 和[测试导航](../agents/testing.md)。
它使用独立精选的公共回归，不自动扩展为所有 scope 测试，也不自动分析变更。
影响面无法确定时，开发者应运行 `all`。

帮助使用已准备的项目 Python 只读引导，不启动 uv、检查或文件写入。缺少项目
解释器时退出 1，并提示用 `uv run --offline --locked` 准备环境。
无参数、未知组合、额外参数或未知选项退出 2，不运行测试。

## 执行、输出与失败

真实检查通过 `uv run --offline --locked …` 运行，只向一个 pytest 执行过程传入
所选模块/节点；完整 nodeid 去重，同一参数化用例只执行一次。不以全量 pytest 兜底。
输出先列选择项及数量，收集后列每项实际节点数与去重总数，然后显示 pytest 本地诊断、
结果、退出码和耗时；外层另报告含 uv 的总耗时。uv 启动前失败时没有收集数量，
仍以非零退出并打印入口失败及耗时。输出不保存到正式验收证据，分享前核对敏感输入。

空选择和缺失模块退出 1；缺失节点、空模块、收集失败或测试失败均非零，
不运行未选择的测试。pytest 收集错误会先给出具体模块和错误；未能收集不宣称通过。
返回 0 只表示本次开发期选择的 pytest 执行返回 0；返回 2 也可表示运行中断，
其余非零沿用 uv/pytest（例如 pytest 选择错误为 4）。

## 副作用与证据边界

测试使用临时文件和临时数据库，不访问实时来源或用户数据库；uv 可能同步锁定环境。
清除继承的 `PAPER_RADAR_TEST_RECEIPT`、`PAPER_RADAR_TEST_RUN_ID`、
`PYTEST_ADDOPTS`、`PYTEST_PLUGINS`，禁用第三方 pytest 插件自动加载、回执插件、
pytest 缓存与字节码。不写正式 `verification-runs/` 证据，不发布 A1–A10 结论。
所选回归内部为验证发布语义而产生的文件仅位于测试临时目录。

既有产物数量、历史终端输出和禁网络/SQLite 守卫保持独立预期。功能子集通过后运行
适用组合，最终仍须 `./scripts/check-offline` 返回 0，开发期通过不继承历史验收资格。
