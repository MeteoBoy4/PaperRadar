# #188：新增 D1 严格类型复查补充

本次补充基于 integration `bb40265`，保留原候选视图台账，不追改旧验证记录。
原实现的定向 mypy 只检查生产模块，不能据此推断新增测试已通过严格类型检查。

## 修正范围

仅修改 `tests/test_experiment_candidates_cli.py` 的测试支撑类型：
Feed 替身的状态和 CLI 回执使用明确 TypedDict，fixture 及回调补齐返回／参数类型，
CLI JSON 使用已锁定 Pydantic 的 TypeAdapter 解析到所消费的回执形状；可空论文和冲突身份
在使用前显式收窄。visibility 观察器使用公共 HiddenCondition／Visibility 类型。
不修改生产语义、测试函数、参数化成员或原 18 项分母；不新增 migration。
没有放宽 strict、使用 ignore、cast 或 Any。

## Red 与验证

- 在合并后的 `bb40265` 单独运行
  `MYPYPATH=src uv run --offline --locked mypy tests/test_experiment_candidates_cli.py`，
  修前复现 15 条错误；修后单文件检查通过。
- 最终定向 strict mypy 显式包含该测试以及
  `src/paper_radar/experiment/candidates.py`、`src/paper_radar/experiment/cli.py`、
  `src/paper_radar/storage/artifact_contract.py`，共 4 个直接检查文件。
- 本票 pytest 仍为 18 项；Ruff、format 与 diff 检查的实际结果见本次外部交付报告。
  不把本次检查解释为全仓 mypy、完整门禁或 #189 新测试通过。

所有运行只使用临时根及既有 HTTP 替身，没有真实来源、Pi、Docling、真实实验根或凭据访问。
原 live 与恢复边界不变；没有新增现场验收结论。
