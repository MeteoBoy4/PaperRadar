# Extra 审阅修复 D1 与证据适用性

依据 [Extra #150](https://github.com/MeteoBoy4/PaperRadar/issues/150) 的独立双轴审阅。
修复起点为 `d7172aeb0f352fe234cade88aaeebe353e73cf93`。本台账独立记录本次
新增覆盖与重新验证范围,不改写 #152/#153/#154 的冻结证据或历史计数。
正式完整离线门禁仍由最终冻结树的唯一执行者取得;本次未运行完整门禁。

## 公共行为与独立覆盖

`probe_docling_runtime` 的现场平台/安装读取交给私有纯分类函数判断。公共接口、
受控 reason、读取时机、未请求时不探测、stdlib-only 与禁止 SDK 导入均保持。
既有公共 probe、doctor 与冷进程负例保持原字节,不新增公开的内部分类接口。

显式安装 smoke 成功继续输出相同字段的 JSON。缺包、版本不符、安装元数据不可读、
native/SDK 导入或属性缺失、非 CPU torch、禁止 CUDA/OCR 库存均退出 1,
只向 stderr 输出受控原因、中文说明和锁定供给/环境修复下一步,不输出原始异常。
真实 SDK smoke 仍由独立显式命令执行,普通 pytest 只替换安装元数据与 SDK 导入边界。

| 新增未绑定测试模块 | 节点数 | 证明范围 |
| --- | ---: | --- |
| `tests/test_docling_import_smoke.py` | 10 | 首包/后续包缺失、版本、元数据、native 导入、属性、CPU、OCR、库存读取等 9 个失败节点及 1 个成功 JSON 节点。 |

先保留缺包失败的红/绿回归,再保留其余失败分类的红/绿回归。断言具体受控原因、
中文下一步、空成功 stdout 与原始异常不泄漏;成功断言字段及模型/PDF 的
`not_assessed`。此 D1 不进入 A1–A10 的 required、旧成员、分母或回执。

安装 Contract 与 README 的跨 minor 示例共用 `UV_PYTHON` 和
`UV_PROJECT_ENVIRONMENT`,覆盖 sync、smoke、doctor 与后续 run;单独设置环境目录
或只为 sync 传 `--python` 无法防止 `.python-version` 重新选择 3.14。

## 本次实际验证

| 环境 | 锁定同步 / pip check / 真实 import smoke | 公共 probe、doctor、冷进程与新增 smoke pytest |
| --- | --- | --- |
| CPython 3.12.14 + extra + dev | 全部退出 0 | 77 passed |
| CPython 3.13.15 + extra + dev | 全部退出 0 | 77 passed |
| CPython 3.14.4 + extra + dev | 全部退出 0 | 77 passed |
| 独立 CPython 3.14.4 无 extra + dev | 无 extra 的显式 smoke 按预期退出 1,给出 `dependency_missing` 中文下一步 | 77 passed |

三个 extra 环境逐次独占复用已存在的磁盘环境;每次显式固定 `UV_PYTHON` 和
`UV_PROJECT_ENVIRONMENT`,未更换 minor。同步当前 editable 时,唯一库存差异为
`paper-radar` 的 editable 来源从原组合工作树改为本次修复工作树;前后均为 85 包,
所有包名/版本相同。独立无 extra 环境为 35 包,未触碰根工作树的门禁环境。
CLI 兼容组合另在无 extra 的 3.14 环境通过 59 项;Ruff 与本次两个代码文件的
mypy 通过。命令、退出码、解释器/平台、前后库存、原始输出及身份比对保存在树外
`.scratch/issue-150/review-evidence/`。

## 旧证据适用性与固定材料

#152 Markdown/JSON、#153 台账和 #154 工程台账保留原字节。相对修复起点,
`pyproject.toml`、`uv.lock`、权威工具链清单、旧兼容入口、v2 示例与生产 extraction
投影均未变。锁 SHA-256 仍为
`fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905`。
旧安装记录仍证明其当次环境与相同供给材料;本次修改过的 smoke 和 probe 行为
由上表重新验证,不把旧通过结果提升成当前 HEAD 的完整门禁结论。
没有模型、parser/options 或实质解析变化,EXP-3/EXP-8 模型/选项的原适用性边界保持。

基线审计显式使用本地 `main=542265c0971fb0e8bcee4c2a7019295fc9686ac7`。
本次代码与 D1 均未绑定旧组,无需新增哈希重绑;审计没有 hash drift 或
baseline drift。相对 main 的既有 11 项敏感确认需求仍由最终树逐组 S3 审阅:
`pyproject.toml` 的九组、`scripts/a10_scope.py` 与 `uv.lock` 的 A10。
本次不扩大白名单、分类控制数据、required 或旧计数,也不复用旧身份的确认输入。

未验证模型加载、PDF 转换、正文/evidence 质量、四刊/中文 fixture、资源、Read/reuse、
其他 patch/平台、wheel/模型无缓存脱网重建及最终完整门禁。Body/B/F 的责任继续见
[原移交](issue-150-extra-delivery.md#bodybf-承接)。
