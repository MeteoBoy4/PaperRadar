# #153 Docling 运行依赖探测独立覆盖

本台账登记 D1 新能力，不加入历史 A1–A10 required 集合、固定分母或旧回执。
`stage_a_verified=false`；本票的开发验证不代表 Extra 或完整阶段验收通过。

## 独立模块与数量

| 模块 | 收集数量 | 公共边界与覆盖 |
| --- | ---: | --- |
| `tests/test_docling_runtime.py` | 34 | 公共结构化 probe；显式意图、所选 v1/v2/后端、缺 docling/core/cv2/parse、发现与 metadata 不一致、版本不符、普通 CPython 3.12–3.14、平台/ABI 未知与拒绝。 |
| `tests/test_doctor_docling_runtime.py` | 5 | doctor CLI；settings/历史 snapshot、必要项汇总、非必要 not_assessed、配置非法先分类、未选 extraction、只读树与逻辑库。 |
| `tests/test_docling_runtime_process.py` | 26 | 冷进程帮助、受控平台/库存诊断、真实基础环境、无探测 import、basic/config/历史 load 不查库存、用法拒绝与敏感参数不回显。 |

独立支撑为 `tests/docling_runtime_support.py`（人工库存字面量，版本期望不从生产清单派生）
及 `tests/docling_runtime_guard/sitecustomize.py`（禁止实际 SDK import、网络、子进程及
业务写入；允许顶层 find_spec 与既有只读 SQLite sidecar）。上述共 65 项。
支持平台与库存矩阵是受控事实；不冒称三个解释器的真实 extra 安装或 parser smoke。

## 开发验证与现场边界

- 使用 `uv run --offline --locked`；合并 #152 安装切片后，独立新覆盖及受影响 doctor/config/安装子集共 177 项通过。
- `./scripts/check-compatibility cli` 59 项通过；相关 Ruff 与严格 mypy 检查通过。
- 新增模块先经缺失接口、缺包结果、显式 CLI、消费者下一步、非 POSIX ABI 与
  不可读 ABI 的 red → green 切片；补充矩阵观察相同公共边界。
- 真实无 extra 环境：CPython 3.14.4、Linux x86_64、glibc 2.43；v2 探测结果
  `dependency_missing`，缺 docling-core、docling-ibm-models、docling-slim、pypdfium2、
  torch、torchvision、transformers、opencv-python-headless；Typer 匹配。
- 通过结果仅描述此刻平台元数据、依赖发现与版本；模型、native ABI、fixture/质量和
  资源能力继续 not_assessed。不运行 Docling，不联网或下载模型。

## 固定材料漂移与承接

本票修改 `src/paper_radar/cli.py`、`doctor/cli.py` 与 `pi_supply/cli.py` 的注册/薄投影，
因此现有组对共享 source 的哈希会漂移。README、doctor/extraction 契约、路线图摘要按
当前公共边界同步。新增生产模块、三个测试模块、测试支撑、公共探测契约与本台账保持
独立；不修改共享中央登记、原 scope、历史测试成员/数量、fixture 或历史证据。

以集成 tip `34beefe` 为 base 的只读审计返回 1，记录 15 条登记哈希漂移：
本票 `cli.py` 涉及 A2-01、完整 A2、A3、A4、A6、A9、A10，
`pi_supply/cli.py` 涉及 A4/A10；继承漂移为 #151 的
`config/extraction_toolchain.py`（A2-01/完整 A2/A10）及 #152 的
`pyproject.toml`（完整 A2/A10）和 `uv.lock`（A10）。源码漂移与依赖身份的
fixture 敏感性分别保留，不以本票确认消除继承漂移。未运行 collect 或完整门禁。

#154 在合并最终工具链、安装与诊断实现后审阅实际范围漂移，完成必要白名单登记、
独立 D1 汇总、最终环境与真实产品组合、受影响回归以及用户授权的唯一完整离线门禁。
本台账中的相关子集不替代该门禁。Body 消费结构化结果，在明确请求与必要检查通过后
延迟 import SDK，仍独立处理 import、ABI、模型、解析和逐文档质量/资源失败；
Body/F 承接 fixture、四刊与 Read/reuse 资格，均不由本票授予。

依据：[Extra #150](https://github.com/MeteoBoy4/PaperRadar/issues/150)、
[#153](https://github.com/MeteoBoy4/PaperRadar/issues/153)；
[公共契约](../contracts/docling-runtime.md)。
