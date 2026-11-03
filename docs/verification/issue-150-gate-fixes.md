# Extra 最终门禁失败的定向诊断与修复

依据 [Extra #150](https://github.com/MeteoBoy4/PaperRadar/issues/150) 的基础锁保护、
CPU extra 与固定范围裁决。本次起点为 `6c660c26df42c02033b353e7fa463308d533cc0e`。
本台账新增诊断与覆盖说明，保留此前台账、历史 JSON 和正式失败证据原字节。
本次仅运行开发子集，未重跑完整门禁，不取得正式通过结论；
`stage_a_verified=false` 保持。

## 实际失败与红绿回路

正式门禁的 lockfile、format、lint、types 已通过，pytest 失败，contracts 未执行。
固定回执中 A10 isolation 1 个失败，verification integrity 4 个失败；另有未绑定
Pi isolation 的 call 失败。固定回执及辅助诊断不保存 nodeid 或异常文本，不能直接
据此判断异常。失败保留目录将后两类缩小到 4 个进程组中断节点和 Pi 端口隔离节点。

A10 最小命令为
`uv run --offline --locked --extra docling python -m pytest -q tests/test_a10_isolation.py::test_lockfile_and_existing_dependency_semantics_remain_fixed`。
修前失败于旧整锁 SHA 预期；下一项“无 optional-dependencies”也与 #150 明确新增
CPU extra 冲突。修后该节点与既有 3 个独立供给节点通过。

默认工具沙箱中，4 个中断节点在本地 `AF_UNIX` 的 `bind()` 处稳定收到 `EPERM`，
Pi 端口节点在 `socket()` 处收到同类拒绝。改变的唯一变量为执行权限时，前者
4 个通过、后者 1 个通过。启用/不启用正式回执插件均重现相同沙箱失败，排除插件
作为必要条件；不需要前序测试即可复现，未发现全局状态泄漏或资源超时证据。
后续完整门禁须具备这些既有本地 socket 权限；本轮不修改隔离策略或安全负例。
正式运行未保留异常文本，上述环境归因来自最小对照与留存目录的相符状态，
不能将开发重跑的异常当作原运行日志；最终同树完整门禁仍须验证组合行为。

## 冻结测试的精确承接

仅修改 A10 的 `tests/test_a10_isolation.py` 内既有锁守卫：

- 依 #150 决策 7，不再要求整个旧锁文本相等；改为逐项固定原基础六包完整 package
  记录的规范 JSON SHA-256，包含版本、来源、依赖边、制品和哈希。
- 六个人工预期来自实施起点，逐项核对 `main` 的旧锁及实现前冻结六包记录，均与
  当前产品锁完全一致；不从当前锁或供给实现生成测试预期。
- optional extra 的封闭集合仅允许 `docling`；基础六依赖声明、dev 组、旧 scope
  依赖声明、禁浏览器导入与本地帮助/无业务 I/O 断言保持。
- 保持原模块 9 节点、nodeid、参数及旧 A10 成员/分母不变。既有未绑定
  `test_docling_extra_supply.py` 的 3 节点继续证明精确 CPU extra、索引、marker、
  三 minor wheel、禁 OCR/CUDA/完整 Docling，不将它们纳入旧 required 或回执。

独立树外受控变异分别更改 Typer 版本、来源、依赖边、wheel 哈希和增加浏览器 extra，
五种均被修后的原节点拒绝。变异仅注入读取边界，没有修改产品锁或实际安装。

## 敏感登记与证据边界

唯一材料重绑白名单为 A10 的 `tests/test_a10_isolation.py`：
旧 SHA `b53e9972f960cbde722e739385e7a37b765802efbf982998b47588d18b57b25c`，
新 SHA `5c1ba0d451c028a7c3c0d4f0fd26bc62dae2dd48934828878e15e2f03bd06202`。
`scripts/a10_scope.py` 仅更新此项字面量，不改变成员、计数、格式或用途。
该测试字节变化及其 scope 登记按 S3 审阅；审阅理由为上述授权规格冲突和等量承接，
不以测试失败作为放宽其他安全断言的理由。最终提交与集成树须另绑定实际身份确认，
旧确认不复用。

实际开发验证为：相关 5 模块带回执组合 37 项通过；静态修正局部变量名后，
最终 A10 isolation、extra supply、A10 scope 3 模块共 16 项通过。Pi 端口节点
在允许本地 socket 的环境中另重复两次，均通过，pytest 实测各 0.06 秒；
此前权限对照的该节点也为 0.06 秒，未复现超时。Ruff、format 和本次两个
Python 文件的 mypy 均通过。入口产物、回执接线和 CLI 导入链均未改变，
不触发对应兼容组合；固定范围仍独立审计与收集。

开发日志、命令、退出码、耗时、插件对照、受控变异及非正式回执保存在树外
`.scratch/issue-150/gate-fix-evidence/`。它们不属于正式 `verification-runs/`，
不替代单一执行者在最终冻结树上取得完整 `check-offline` 的退出 0 和同次查询。
真实 SDK、模型、PDF、正文/evidence 质量、资源门禁、Read/reuse、Pi live、
四刊 fixture、正式校准和 NAS 均未新增验证，Body/B/F 的既有责任不变。
