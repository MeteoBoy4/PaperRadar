# Pi 外部审阅后独立覆盖摘要

依据 [#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 与外部审阅后续范围。
这是新的 D1 覆盖台账；本地集成基线为
`main=e0f8e39d1aff8b57eadfe60de44b8570423c1d40`。

## 当前工程边界

- 新写 pi_rpc 审计为格式 3，使用 `channel=prompt_only`；格式 2 严格只读回放，
  保留 `protocol`、原审计字节及 submission_digest。规则属于
  [任务接收 Contract](../contracts/screening-tasks.md#10-原始候选接收与派生查询)。
- 启动超时接受有限正数，拒绝 bool/NaN/无穷/非数值；执行服务各 RpcLimits
  还受默认上限约束。两者均在领取、认证或模型进程创建前拒绝。
- `PreparedLaunch` 一次性行为仍映射既有 startup_error/executor_error。
  预绑定与受保护启动共享身份构造；代理审计不扩大准入/校准绑定。
- doctor 读取同一已验证模型槽，当前准入证据固定缺失，没有 passed/admitted
  或外部证据输入入口。供给、cwd 元数据与内核能力各自的 passed 不授予执行资格。
- 未绑定 pytest 失败可输出模块与受控阶段；详细规则唯一归
  [辅助诊断 Contract](../contracts/offline-pytest-diagnostics.md)。
  正式 receipt v1、固定成员/计数、terminal/readers 与正常十四份 JSON 保持。

## 独立新增 D1 分母

| 未绑定测试模块 | 数量 | 公共 seam 与范围 |
| --- | ---: | --- |
| `tests/test_pi_execution_external_review.py` | 47 | 新写通道；独立字面量 format2 的查询/完整性/备份恢复与非法混版；两种启动超时和五项有界 RpcLimits 的领取前零进程效果；一次会话与代理审计 |
| `tests/test_offline_unbound_diagnostics.py` | 13 | 真实隔离 pytest 四阶段失败；含 secret 的参数不外泄；缺失/损坏/跨 run/哈希/路径/阶段拒绝；固定模块失败和正常路径兼容、嵌套身份隔离及非普通文件拒绝 |
| 合计 | 60 | 不进入旧 Pi 195、A1–A10 required 集合或固定回执分母 |

独立历史 fixture 为 `tests/fixtures/pi_rpc/legacy-format2-audit.json`，只由本轮测试消费。
原有 `test_pi_rpc_source.py` 23 节点和 `test_pi_rpc_source_backup.py` 21 节点仅对
新写格式号作对应更新；旧格式由独立字面量覆盖，节点不增减。
既有 `test_scope_shared_dag.py` 24 节点显式命名 #139 单一中央成员，保留
1175 旧基数、28 历史增量、41 refs 和原精确集合；
`test_scope_material_inventory.py` 4 节点只增加新 Contract 的精确路径。

## 开发期验证与最终判据

| 验证范围 | 结果 |
| --- | --- |
| 相关42模块组合（含全部60个新D1节点） | 518 passed，229.54秒；1条既有SQLAlchemy metadata循环外键警告 |
| 来源/审计/执行/Feed/doctor/历史冷导入组合 | 161 passed，108.60秒 |
| 新诊断及原离线入口/历史终端字节 | 33 passed，21.65秒 |
| `check-compatibility all` | 176 passed，pytest 272.11秒，入口272.74秒，退出0 |
| 全仓 Ruff check / format check / mypy | 全通过；格式748文件、mypy747文件 |
| 显式 main 基线候选 scope / collection | 退出0，无hash/baseline漂移；285模块/5281节点，289条原计数保持 |
| 全量独立 collection | 352模块/6385节点；未绑定67模块/1104节点 |

登记仅更新8条实际材料哈希，中央成员集合、组用途、固定测试字节/分母与41 refs保持。
敏感范围为入口说明fixture、分类控制及A8/A9/A10的展开登记摘要，共5路径/20项下游确认；
最终提交与工作树身份的确认单独保存在树外。
完整离线门禁待最终提交冻结后执行；完成要求为同次 `./scripts/check-offline`
退出 0，且 `verification-status` 为 `passed/verified/same`。
开发期测试及只读 collection 不代替正式门禁，历史 passed 不适用于新树。

## 历史证据与证明限制

[原 Pi 台账](issue-140-pi-delivery.md) 的 195 节点和按次开发结果、
[#142 台账](issue-142-pi-rpc-source.md) 的 44 节点及旧格式 2 陈述是历史覆盖事实；
其正文和既有 verification-runs JSON 保留原字节。当前公共规则从 Contract 查询，
本轮逐项审阅处置与过程仅见
[r1 报告](../../intent/review/issue-140-pi-execution-review-r1.md) 与
[r2 报告](../../intent/review/issue-140-pi-delivery-review-r2.md)。
ADR-0039 的正文是接受时上下文，状态行指向本摘要；当前现场责任不由其历史措辞推定。

没有运行 live、真实 Pi/Node/auth/模型或 `/srv/pi-cwd` 现场验收。
Cwd/Live 继续负责祖先资源、现场隔离、主机级出站、DERIVED、订阅刷新/通道、
模型权限/限额、采样能力、TLS/DNS 与隐含 retry/预热抑制；B 继续负责真实入口、
实验根、日志与用途资格。产品缺当前证据仍领取前阻断；`stage_a_verified=false`。
