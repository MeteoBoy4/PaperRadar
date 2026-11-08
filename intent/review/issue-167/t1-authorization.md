# #167：T1单次H1/H2/H3执行批准

所有者针对最终待审包的单次H1/H2/H3问题明确回复“批准”。该批准绑定以下材料，不延伸至其它案例、重验、新版本或产品激活：

- run：`8b31f0a9d672`。
- 包：`.scratch/issue-167/h1-live-timeout-t1-v1/`。
- review-seal SHA256：`b47a6945ed485280180c633b292a66b217bebcd7904ba772b0b7e9db9374673d`。
- manifest SHA256：`dc4ef368e719c9ceda7940301ba550681c391c6182a05f54f552e081cba3e8e4`。
- driver SHA256：`71d6ce56eb1f832df134678ef3fa8340098e8cc3512c6881eecad33d20b4ba5c`。

批准范围沿[最终准备材料](../../../docs/verification/issue-167-t1-preparation.md)及封印owner-review：本次具名单元、唯一项目表、root-owned两树、永久单次记录与固定无凭据IPC预检；最多auth CLI1、合成value/low prompt/model1、Node2（auth/model）、应用重试0、外部信号0。首个有效text marker后一次事务双向DROP，默认公共300秒不重置，不resume、不补跑、不加任务、不退款。缺参照、半切换、观察/后验失败、late packet或恢复失败仍unknown保留，交所有者仅恢复。

批准同时覆盖问句所列H2条件：所有者确认冻结pool仍有效、专用认证输入维持review所列结构，认可条件逻辑刷新0或1及可能联网/持久更新，并接受Pi内部DNS/QNAME/fallback、redirect和隐藏HTTP次数unknown。agent未访问认证目录或读取新expires，不把批准当新的内容核查；不继承E01旧过期或必刷新声明。无新增预热探针，旧profile的candidate_probe不执行；上游映射/出口身份和IPv6边界保持。

收到批准后，agent只读重核封印、40成员及driver均同字节，bash-n通过；results仅offline-validation.json，尚无execution-started或owner-run。本记录证明会话批准和交付时状态，不预占余额、不代替执行回执；冻结材料中的静态not_granted字段不是许可来源。

按原票H1“root动作由所有者审阅执行”，下一步由所有者运行owner-review中的四项确认入口，只在sudo TTY输入密码。agent没有运行向导、sudo、服务、规则、认证、刷新、Pi/Node、模型或故障注入。实际结果待执行后只读复核；旧unknown、消耗、K2有限范围、H5草稿及普通产品缺证据阻断保持。

后继状态：所有者随后报告已运行，[本次结果](../../../docs/verification/issue-167-t1-result.md)经主代理和fresh独立只读核验为not_triggered_and_restored：实际双向DROP成立，public在约84.21秒stop_reason返回，300秒未触发；恢复完整。该单次授权已消费，不补跑、不退款，不延伸为新调用许可。
