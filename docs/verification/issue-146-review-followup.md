# Issue #146 审阅建议核实与后续覆盖

依据：[#146](https://github.com/MeteoBoy4/PaperRadar/issues/146)，
[r1](../../intent/review/issue-146-wiley-abstract-review-r1.md) 与
[r2](../../intent/review/issue-146-wiley-abstract-review-r2.md)。逐条判断只在两份过程报告维护。

## 基线与边界

起点 HEAD / 本地 target main 均为 `a7df05be0d22a56134b51e0c2bee0f8c77a32652`。
初始 dirty 仅包含用户提供的两份未跟踪审查报告；按用户要求保留原文、追加处置并纳入提交。
基线范围审计没有既有漂移。本轮不推进 migration head，不新增验收组或改旧分母。

新封闭版本模块是审计与两个生产消费者的共同权威；A10 增加它为 source 材料，
不增加任何测试成员或历史证明范围。原 abstract_models 的默认常量导入路径仍可用；
v1 字节解释、旧 check_id、历史版本错误分类和执行身份守卫保持。
精确登记旧新 SHA 见[本轮重绑清单](issue-146-review-rebindings.json)。
已登记 source 哈希只精确重算实际变化；新消费闭包为 abstract_versions →
既有摘要/计划/生产解释与回放。复算脚本和新增回归是独立未绑定覆盖。

## 本轮独立覆盖

| 模块 | 当前节点数 | 本轮增量与观察边界 |
| --- | ---: | --- |
| tests/test_wiley_abstract_v2.py | 27 | 仅为非法规则负例显式标出静态类型越界；原断言和节点保持 |
| tests/test_wiley_audit_versions.py | 2 | 版本映射整理后的 v1/v2 回放与隔离恢复兼容 |
| tests/test_wiley_parser_migration.py | 1 | 原 v1 身份非空迁移回归，未改 migration |
| tests/test_wiley_production_versions.py | 7 | 新增4项：Feed/元数据双向显式版本冲突、无额外 HTTP、原请求回放保持，省略版本精确重试 |
| tests/test_wiley_comparison.py | 1 | 新增：安全字段有独立哈希预期、原计划保持、命令能区分匹配/不匹配 JSON |

新增请求冲突回归已在修复前观察到 DID NOT RAISE，复算工具回归在实现前观察到模块缺失。
以上当前共38项，仍不进入既有回执或固定组分母。原33项交付结论不追溯扩大。

## 可复算的保留材料诊断

输入身份：

- 计划：`b1719ffade06f8ec575d3e64fbe5fc6f3495787278f77ce9689c196a91b34b04`。
- 原冻结汇总：`257965f98447d368dcc402af5e217440d04a41e8de8bba933f6d5f395b9f1ba9`，partial。
- JGR Feed：`9097d9f76c0a8e77380df187f901fae9959e3bd0c003f14437e84e4ee61ced66`。
- QJRMS Feed：`a7f183bf03cd044b5fd6719ad2b8dc445d1aebb766de2c0b77f3b614a10277e1`。

在仓库根执行下列命令；两条本机路径只定位原审计库和保留来源，不是可上传材料。
其他机器须自行提供匹配的合法保留材料；这些字节不入库。

```bash
uv run --offline --locked python -m scripts.compare_wiley_abstracts \
  --database .scratch/exp-1/20261102T113059Z/data/audit.sqlite3 \
  --data-root .scratch/exp-1/20261102T113059Z/data \
  --plan-id b1719ffade06f8ec575d3e64fbe5fc6f3495787278f77ce9689c196a91b34b04 \
  --check docs/verification/issue-146-field-diff.json
```

本轮实测退出0，输出“离线差异与保存报告逐字段一致；原计划未改写，未联网。”
工具只接受 v1 来源计划，用 sqlite backup 创建临时一致副本，在副本升级后读原 blobs；
原库以 mode=ro 打开。重算前后 replay 相同，socket/DNS 入口在调用期间全部拒绝。
不使用 resume 或 reinterpret，不保存瞬时矩阵，不追加 fixture，也不把 partial 改为 complete。
省略 --check 时只输出同结构安全 JSON；报告不同或输入损坏返回1，原报告不覆盖。
原安全 JSON 与本轮实现前的字节 SHA 保持，完整哈希/长度用于精确核对，不含原文。

## 验证边界

本轮开发验证：

- 相关功能、生产服务与历史回放/恢复组合：79 passed；复算命令与证据链接补充组合：5 passed。
- 原 A10 完整性负例与完整恢复：110 passed，原成员和节点数保持。
- CLI 导入兼容组合：59 passed，退出0。
- Ruff lint、全仓库格式检查与 mypy 通过，mypy 检查755个 Python 文件。
- 保留材料只读复算 --check 退出0；旧 field-diff JSON 保持原字节。
- 固定范围以当前 base/HEAD/target/dirty 树核对敏感变化；确认输入在 /tmp，
  本台账不是可复用确认或正式验收回执。提交后另核对哈希登记与工作区状态。
没有运行完整离线门禁、四刊新 live、fixture acquired 登记、Pi、模型、Docling 或 NAS。
本页不是正式验收回执，也不替代最终提交身份所需的完整门禁。
