# B 冻结暴露导出工程覆盖

本台账记录独立 D1 合成工程证明，不扩大 A1–A10 历史固定分母、required 集合或真实验收。
实施基线为 `cb1251492db4debe9591727cdaab53cbebb573db`；全部材料位于独占 `/tmp` 测试根。
执行只替换既有 HTTP transport、Pi 合成 RPC、Docling parser 与时钟边界；完整链的根、
所有者豁免、外发授权、选样、决定、PDF、版式核查、Read 与报告沿真实 CLI／公共权威。

## 行为与接缝

- CLI 主接缝：候选空集、失败与换样保留、全部历史请求／attempt 各自版本依据、缺 DOI 受控拒绝、
  PDF 附加失败前的独立确认、prepared/published 报告成员、文件日志及公开／私有输出分界。
- 公共服务仅用于故障与并发；持久事实工厂使用原公共 API，不 mock 内部准入、接收或资格。
  故障覆盖登记、制品与私有视图发布、130 中断、捕获后事实变化、并发相同导出、篡改及冻结遗漏。
- 恢复接缝：真实 backup create → restore verify 子进程 → 冷 Python 进程。
  禁原根／配置、网络、Pi／Read 执行与 Docling；两份新旧清单保持原字节，恢复树库存不变。
- DOI 规范化、权威边三态、两端对称／多跳可达、无关图隔离、重复 assertion、晚发现端点、
  metadata 修订、SQLite VACUUM 与恢复均不依赖临时 Paper UUID 或物理 rowid。
- 无 attempt 的 Read 请求明确是论文级依据；多版本反例不伪造精确历史版本。
  实际 attempt 仍只引用自己的原 metadata revision。

详细现状唯一归属：[暴露导出 Contract](../contracts/exposure-export.md)。
所有者既定边界由 [ADR-0070](../adr/0070-freeze-stage-b-exposure-after-selection.md)记录；不追改旧 ADR／证据。

## 独立 D1 节点

| 模块 | 节点数 |
| --- | ---: |
| `tests/test_experiment_exposure_cli.py` | 2 |
| `tests/test_experiment_exposure_entry.py` | 5 |
| `tests/test_experiment_exposure_faults.py` | 14 |
| `tests/test_experiment_exposure_history.py` | 4 |
| `tests/test_experiment_exposure_identity.py` | 9 |
| `tests/test_experiment_exposure_migrations.py` | 4 |
| `tests/test_experiment_exposure_recovery.py` | 1 |
| 合计 | **39** |

支持文件为 `tests/exposure_support.py` 与 `tests/exposure_recovery_worker.py`，两者均进入静态检查。
最终精确 collection 与逐模块计数保存在仓库外 `200-final-d1-collection.txt`／`200-final-d1-counts.json`。

## 实测

原始离线开发记录保存在仓库外 `/tmp/paperradar-185/200-*.log`，不作为正式验收回执。

- TDD 红：`200-red-empty.log`，1 failed，缺少 `export-exposure` 命令；
  首个绿：`200-green-empty.log`，1 passed。
- 完整主组合：`200-final-complete.log`，**40 passed**，269.59s：38 个新 D1（多跳图补充前的完整并集）
  加独立 Schema 一致性与 migration head 单一归属两节点。
- 新增多跳图：`200-transitive.log`，**1 passed**，1.78s。最终 39 个新 D1 均有实跑证明；
  不把收集当执行，也不声称 39 项在最后同一命令执行。
- 公共组件组合：`200-components.log`，**34 passed**，173.92s：Body facts 13、version relations 13、
  A7 跨版本请求／领取各 1、Read 登记／领取 1、报告决定顺序 4、报告冷恢复 1。
  精确节点为 `200-components-collection.txt`，计数为 `200-components-counts.json`。
- CLI 兼容：`200-cli-compatibility.log`，**59 passed**，89.40s；入口总耗时 90.14s。
  独占 TMPDIR 先创建后设置，无正式回执与外部调用。
- 额外定向检查：视图发布／中断 3 passed、并发 1 passed、晚发现端点与并发组合 9 passed；
  与上述完整并集重叠，不增加分母。
- 全部 **36** 个新增／改动 Python 文件（含全部新 tests/support）默认 strict mypy、Ruff、format 通过。
  路径并集为 `200-static-paths.txt`；不以生产文件子集代替测试支持检查。

Schema 节点的已知 SQLAlchemy 循环外键排序 warning 不使断言失败；未修改该冻结节点。

## Migration 与集成责任

新增线性 `b007_exposure`，父 `b006_reports`；登记及独立冻结范围不可更新／删除。
从含已有 report run 的非空上一 revision 升级，分别注入 CREATE TABLE、CREATE TRIGGER、
stamp 故障后回滚、重试，随后真实标准恢复；Schema 与元数据一致。
人工推进 head 常量、10 scopes、A3 备份格式、生产备份 revision、两 Contract 与两个中央哈希；
旧 migration 保持原字节。

新增 `docs/contracts/exposure-export.md` 按精确路径登记为 live document；这项分类及共享登记变化
仍由 spec 集成收口逐组审阅。普通 source/support 新消费闭包不自动纳入历史 required 组。
以稳定 main `6f0c4e93d43b86cf25e87d90bf5130e7533d19d1` 为显式 base/target 的开发审计保留
67 项 confirmation_required，45 条 hash_drift 边／16 个路径；较先前新增 PaperFacts.service 的
A6/A10 两条源码边。未机械重绑旧 source hash，`--collect` 因 audit_failed 为 not_run。
三个旧 trace 整对象与 D7 两向量的既有差异继续由最终 B 收口处理，不修改旧固定断言。

## 未验证边界

未运行完整离线门禁、真实来源／Pi／Docling、真实论文或现场恢复，不访问真实实验根／私有运行材料或凭据，
未 push、Issue 写入或提前实现恢复布局。Python 冷守卫不是 OS 隔离证明；C 导入、未来合并保留排除、
现场脱网、NAS、真实资源与模型／论文质量由各自后续闸门负责。实验结果不提升、不复用。
