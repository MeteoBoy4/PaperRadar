# #167：最小观察 loader 的离线参考验证

依据所有者本轮H4明确授权，设计与实现安装树外的最小观察参考模型。设计及原型审查标签只在[审查文档](../../intent/review/issue-167/loader-design.md)中维护；没有新增产品启动策略/协议注册/供给身份。本次不运行Node/Pi、不联网、不读取凭据、不发送认证或模型请求，也不写安装树。

## 方法与实际结论

代码 `scripts/issue167_loader.py` 实际替换两个合成peer的可调用transport接缝；前台、预热、重试和auth刷新由这些调用口驱动，独立peer在自己发送口累计参照。它不是把已有事件表直接送入RequestLedger，也没有通过预设全部passed的布尔值跳过调用过程。

| 验证 | 实际方法与结果 | 限制 |
| --- | --- | --- |
| 安装前后调用 | attach包装实际dispatch callable；发11个合成操作，连续sequence、分类count与独立peer相符 | Python模型，不是Node loader |
| 预热/重试/刷新覆盖 | 同model口前台、预热、retry分别触发；auth独立peer | 不把这些合成dispatch计数登记为真实HTTP |
| 漏计/旁路 | 从合成peer未包装口绕过，或安装后替换dispatch，独立参照不匹配 | 最终unknown、禁止消费及后续dispatch；不证明真实出口都可挂钩 |
| 独立参照 | 缺参照、缺类别、bool计数、与观察计数不匹配均unknown | 参照由合成peer提供，不是供应商权威 |
| 输出故障 | sink抛异常、缺序号ACK、错ACK或bool，在转发前unknown并阻断 | 不导出外部异常文本；ACK不证明真实持久化 |
| 窗口/重复 | 晚加载、只装一个角色、重复安装、结束后再派发/再次finish均不产生新通过 | 不允许检测失败后恢复成complete |
| 发送口执行前故障 | 安装前已有transport函数实际抛错,peer未执行而loader已记尝试1次,参照不符 | unknown并阻断,不把调用尝试当实际发送 |
| 下游已发送故障 | 合成peer记一次操作后抛受控故障，观察仍计1次 | 不解释为模型成功/零计费 |
| 数据最小化 | 所有观察输出只有category/sequence/count/completeness | API没有请求/headers/body/token字段，未知类别不转发 |

运行中事件均为unknown，最终只有合成独立核对完整才complete；`require_complete()`在任何缺失/故障后拒绝。角色信息只从合成loader的明确配置生成，输出用闭集类别区分模型/auth，不从请求内容推断。

## 本轮未证明

没有运行JavaScript或Node。未来global fetch包装与底层dispatch/diagnostics是不同观察层，onResponse无法覆盖响应前失败；完整说明见[设计](../../intent/review/issue-167/loader-design.md)。真实未知transport、动态绕过、独立参照、收集持久性、固定client所有发送路径和现场事件丢失均未验。Python模型的complete不能注入产品或登记真实兼容通过。

是否采用新启动策略身份、采用后EXP-2现场证据如何重测，保留给所有者H4终局；本轮没有作出选择。当前产品read_evidence缺失仍阻断，core与其他现场门禁独立成立。

## 开发验证

命令均为 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked …`：

- `pytest -q tests/test_issue167_loader.py`：24 passed。
- `ruff check`、`ruff format --check`：两个新增Python文件通过。
- `MYPYPATH=src … mypy scripts/issue167_loader.py tests/test_issue167_loader.py`：2 source files通过。

24项是独立D1未绑定测试，不进入历史分母、既有required/回执或Live生产准入；没有运行完整离线门禁。未修改前轮冻结证据字节。由主代理另作完整工作树固定范围只读审计。

本轮按所有者指定 `docs/docs.json` 导航复核SDK、extension请求hook顺序及custom-provider setup/onPayload/onResponse语义；具体行段和不能外推的理由见[审查设计](../../intent/review/issue-167/loader-design.md#按固定文档导航复核的公开接口)。生产-ne与现有默认SDK隔离约束保持。以下只标识读取的文档，不追加到旧冻结分母。

| 文档 | SHA-256 |
| --- | --- |
| `docs.json` | `fc0bccd6bf66716ad1067d4fbf7258f674d89c89a12cb0b2587a027b9d7fdc49` |
| `sdk.md` | `d9034ccbf2219a58712d8dd4fcdf47e687d77131e71dd5d119d8a71e9bd2a2e8` |
| `extensions.md` | `46fc0baeb00db8ca8db399e33e0f506e86e425693b291258357e8063e2f3353c` |
| `custom-provider.md` | `fe926ed6194756c85ab6b56b7bfd12e81abe385acf39e0bb2a470eb6c70b8c59` |

独立审阅发现外部Mapping读取异常会泄漏原文且允许换参照恢复。新增回归先复现失败，再修复为保护整个参照快照/校验：items、迭代、索引读取失败均sticky unknown，恢复参照也不能complete；KeyboardInterrupt保留中断语义并标失效。所有返回仍仅四字段，无外部异常文本。
