# CPU Docling extra 安装证据（#152）

本证据固定 #152 的单锁供给与浅层安装兼容，不是完整离线验收回执。依据
[#150](https://github.com/MeteoBoy4/PaperRadar/issues/150)、
[#152 及其库存/支持声明补充](https://github.com/MeteoBoy4/PaperRadar/issues/152)。
机器可读命令、身份、完整发行包库存和六包比较见
[安装记录](issue-152-docling-installation.json)。本次未运行 `./scripts/check-offline`，
最终 extra + dev 同次完整门禁、固定材料审阅/必要重绑由 #154 承接。

## 三类结论

| 结论 | 证明范围 |
| --- | --- |
| 锁可解析 | 同一产品 `uv.lock` 离线求解；`required-environments` 点名 Linux x86_64 CPython 3.12、3.13、3.14；基础 `requires-python >=3.12,<3.15` 不变，无全局 `environments` 或无实际冲突的 `conflicts`。 |
| 实装可用 | 3.12.14 / 3.13.15 / 3.14.4 三个全新独立磁盘环境，实际消费最终产品锁；`uv pip check` 与两个后端、converter、TableFormer、Transformers、cv2、CPU import smoke 通过。 |
| 支持声明 | Linux x86_64、glibc ≥2.28、普通启用 GIL 的 CPython 3.12–3.14；其他 patch 未实测，aarch64、macOS、其他实现及 free-threaded 不支持。marker 跳过不能证明安装成功。 |

环境为 Linux x86_64、glibc 2.43、启用 GIL，uv 0.12.15。安装使用隔离复制的
EXP-8 缓存（wheel、元数据、build 依赖和既有解释器均就绪），不联网，不复用已装探索环境。
`uv sync --offline --locked --extra docling --link-mode copy --python <解释器>`
实际创建每个新环境；默认 dev 组也安装。未验证缓存缺失时的脱网重建。

| 环境 | 安装 / pip check / import | 发行包数 | 定向 pytest |
| --- | --- | --- | --- |
| CPython 3.12.14 + extra + dev | 全部退出 0 | 85，前后库存相等 | 201 passed |
| CPython 3.13.15 + extra + dev | 全部退出 0 | 85，前后库存相等 | 201 passed |
| CPython 3.14.4 + extra + dev | 全部退出 0 | 85，前后库存相等 | 201 passed |
| CPython 3.14.4 无 extra + dev | 安装 / pip check / 根及 config 帮助退出 0 | 35，实际无 Docling/torch/Transformers/pypdfium2/cv2 组件 | 201 passed |

定向选择是新供给模块、v2 工具链模块、四个 extraction 公共配置模块、CLI 帮助/冷导入
与两个基础 doctor 模块。包含前置 v2 示例的真实 check/compile/load，以及两后端显式选择。
本次计数由实际运行取得，不继承探索 253/276 项或历史验收组结论。

普通 `uv run --offline --locked` 未指定 `--extra` 或 `--no-sync`，在三环境中仍保留
extra，import 与 pytest 前后完整库存相等。这与 `scripts/check-offline` 的启动方式一致；
无需修改门禁或减少检查集合。后续仍须在最终冻结树中记录完整门禁前后库存。

## 供给与历史证据适用性

产品锁 SHA-256：
`fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905`。
它与 EXP-8 接受的 `18-optional-typer-threaded-x64` 推荐候选逐字相同；这不是要求
产品新锁复刻探索材料，而是本次实际求解结果。三个新环境完整 85 包库存分别与对应
EXP-8 最终环境全等。CPU 来源由显式官方 `pytorch-cpu` source、`+cpu` 精确版本、
锁中官方 wheel URL/哈希和实际锁定安装共同确定，CPU import 另外核对 CUDA 不存在。
slim 使用 `convert-core`、`format-pdf`、`models-local`，IBM models 使用 headless cv2；
不含完整 docling 元包、OCR、CUDA 或整个 `models-vlm-inline`。

在修改前留档产品起点锁与六包完整记录。以下每项都比较完整 package 记录，涵盖版本、
source、依赖边、sdist/wheel 及哈希；起点与 EXP-8 基线也全等，无已有合法差异需覆盖。

| 包 | 起点与最终版本 | 本次比较 |
| --- | --- | --- |
| alembic | 1.20.0 | 不变 |
| httpx | 0.28.1 | 不变 |
| pydantic | 2.13.5 | 不变 |
| pyyaml | 6.0.3 | 不变 |
| sqlalchemy | 2.0.54 | 不变 |
| typer | 0.27.2 | 不变，未降级 |

EXP-3 的 core 2.101.1 旧身份不升级成 v2；v2 的 core 2.105.0 与两后端适用性来自
EXP-8。EXP-3/EXP-8 模型清单字节相同，本次只读复核启用的 16 个文件 SHA-256 全等，
模型仍为 Egret medium、TableFormer accurate、CodeFormulaV2 对应冻结 commit。
核对 EXP-8 保存的 options：CPU、原生文本链、OCR/代码/图片/图表/远程服务/外部插件关闭，
表结构与 cell matching 开启、Egret medium、accurate、float32、公式裁切 0.18、heading
hierarchy 与 reading order 开启；threaded 后端四个选项与 v2 显式策略一致。
机器模型目录、线程、超时仍是原探索运行配置，不复制或提升旧运行身份。

本票没有 parser/options 生产实现或实质解析变更，不需要补解析变化 smoke；两个后端的
原始结果继续分别解释，不视为相等。模型文件复核只用于历史适用性，不代表新产品环境已
加载模型；新示例含合成哈希，不能充当模型安装清单。

## 独立覆盖与后续责任

新增 D1 未绑定模块 `tests/test_docling_extra_supply.py`：**3 项**，分别覆盖产品 extra
精确声明/最小特性、显式 CPU index 与三 minor 求解要求、单锁 CPU wheel 及禁止组件。
普通 pytest 只读声明，不导入 SDK、不安装 extra、不要求模型/PDF。
`scripts/check_docling_imports.py` 为独立显式 smoke，检查实际库存及公共 SDK 导入，
不纳入普通 pytest。新增模块未扩大 A1–A10 的固定分母或 required 集合。

预期固定材料漂移：`pyproject.toml`、`uv.lock`；README/extraction Contract 为活文档。
相对子票基线 `f6736d2` 的审计另列 #151 的 `extraction_toolchain.py`
source/support 继承漂移；这不是实施起点已有漂移。spec 实施起点 `542265c` 的审计
退出 0，由 #154 以该起点和最终 target 统一分析。本票不修改既有 scope、中央哈希、
冻结测试或历史证据。
新增测试、显式 smoke 与本证据由 #154 统一登记独立覆盖、审阅必要分类/重绑。

未验证模型加载、整篇转换、正文/evidence 质量、四刊或中文 fixture、资源门槛、Read/reuse
准入、其他 patch/平台、wheel/模型脱网重建与最终完整离线门禁；这些不因安装成功而通过。
