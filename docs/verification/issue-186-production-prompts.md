# #186：B 首版公开生产 Prompt 离线覆盖

依据：[#186](https://github.com/MeteoBoy4/PaperRadar/issues/186)、
[#185 决定 11](https://github.com/MeteoBoy4/PaperRadar/issues/185)。
本票不新增 Alembic migration、不新增 CLI 或输出 Schema、不改业务执行代码。

## 材料分类与字节索引

下列新材料沿固定范围规则分类为固定材料，不加入活文档精确路径清单、旧组回执或
required 集合；现有 `examples/`、历史哈希、旧测试及 Schema 保留原字节。
本台账与 `tests/test_stage_b_production_prompts.py` 同为新固定材料，测试为独立 D1，
不绑定 A1–A10，不扩大历史证明；`stage_a_verified=false` 保持。
README、GLOSSARY 和现有 runtime-config Contract 沿既有活文档分类更新。

| 公开固定材料 | SHA-256 |
| --- | --- |
| `prompts/screening/boundary-v1.md` | `38d398890f9fc94c3bf011c25a0075d2d87b0723a8b53cef609df1f0b15acb6a` |
| `prompts/screening/value-v1.md` | `16c16ef34b3eb88dd045ddbe8a330ac178c14c43e2d9ae04d4469bc623ecf3d4` |
| `prompts/reading/v1.md` | `8e10f889152de5787e43d6643d251756387cb2f90d7ca036d492e8d1ae1dfe68` |
| `config/prompts/pi-system-v1.md` | `922722c266808068239a5af55e6a8e6d38ca10db8f35b1ad88db928f919b2b00` |

## 新增 D1 覆盖

`tests/test_stage_b_production_prompts.py`：**10 项**，以真实配置 CLI 为主接缝；
纯调用描述、阶段输入和帧预算沿其公共纯函数验证，不启动任何外部执行器。

| 场景 | 项数 | 观察 |
| --- | --- | --- |
| config check / compile | 2 | 合成 Profile、主题、模型及正文配置下 boundary/value/read 均 ready；登记精确公开材料哈希，终端不回显完整 Prompt |
| 同声明版本换字节 | 4 | 三份业务 Prompt 与系统 Prompt 均经 CLI 受控退出 2，明确版本冲突；旧快照仍可读取 |
| 仅 reading 新版本 | 1 | Read 指纹变化；boundary/value 指纹及校准语义基线不变 |
| 完整请求与系统参数 | 3 | boundary/value/read 首帧及受控修正帧 ≤262144 bytes；Read 最坏修正槽也在上限内；系统 Prompt 通过形状检查且连 NUL ≤131072 bytes；不发送期刊信誉 |

Screening 覆盖全部受控失败修正说明，Read 使用全部 36 类与 192 字符合法路径构造
最坏受控修正，同时验证完整修正槽的保守预留。合成题名、摘要与正文含中文、四字节
字符、引号和换行，使用真实双层 JSON 编码计数；未用字符长度或局部 Prompt 长度代替
完整帧预算。Read 消费上下文直接构造合成 provenance，不调用 Docling。

## 开发验证与证明边界

TDD tracer：新模块首轮因公开材料缺失 **2 failed**；加入四份材料后 **2 passed**。
扩展用例完成后，新模块与 Prompt/配置/调用描述/Read 输入相关回归 **51 passed**。
新增模块及既有活文档链接检查 **14 passed**；定向 Ruff 与格式检查通过，
`MYPYPATH=src uv run --offline --locked mypy tests/test_stage_b_production_prompts.py`
通过（1 source file）。
合入当前 `integration/185-stage-b` tip（Already up to date）后的上述相关回归与
链接检查合并运行 **55 passed**，`git diff --check` 通过。
运行入口为 `uv run --offline --locked pytest`，各次使用 `/tmp` 临时根；
Ruff 与 mypy 使用同一离线环境作定向静态检查。

没有触发 CLI 注册/导入链或验收组/回执变化，无需新增兼容组合；范围审计由本票
执行只读检查，显式以集成分支基线 `6f0c4e9` 审计退出 0、无 issues、
无 affected_groups；后续集成在最终树重新审阅。不存在本票 source/support 重绑白名单，
不为新增 D1 材料机械修改旧 scope 或中央哈希。

未运行完整离线门禁、真实 Feed HTTP、Pi 供给/认证/探测/生成、Docling 解析或任何
真实实验命令；未访问真实实验根、研究材料或凭据。离线结果仅证明公开材料可由现有
确定性边界消费，不证明真实模型输出质量、中文效果、提示注入抵抗、任意正文大小、
真实样本证据正确性或正式校准通过。首次真实 Screening 前的副本核对与冻结、
真实输入预算、逐文档质量及模型结果验收由 B 执行票承接，D 负责正式校准基线。
