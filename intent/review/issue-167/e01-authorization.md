# #167：E01单次执行批准

所有者在针对最终待审包的H1/H2/H3问题后明确回复「批准」。该批准绑定下列材料，不延伸到其它案例或新版本：

- run：4e01c7a3b962。
- review-seal SHA256：ddce0ec03ecbb819d124c94d92babf1d4d75420dcd97ff6972bb6bf9152e3646。
- 包：`.scratch/issue-167/h1-live-signal-e01-v1/`。
- 范围：该具名单元/独占表、最多auth CLI1（计划联网刷新及持久写）、合成value/low prompt/model1、Node2、仅目标controller的外部SIGINT1，以及包内DB/宿主/目录恢复；不补跑、不退款。

范围、输入声明、HTTP/DNS unknown、Pi用量未知成本、提前结束/迟到分类及恢复限制均沿[最终准备材料](../../../docs/verification/issue-167-e01-preparation.md)和封印owner-review。旧e93/d5的unknown不改，产品准入不由此批准。

收到批准后只读重核seal、manifest、40成员及driver同字节；results仅offline-validation.json，没有execution-started或owner-run。本记录只证明会话批准及交付时状态，不预占预算、不代替实际回执，也不是产品接收/激活。

按票内H1，root动作由所有者审阅执行。下一动作是所有者运行owner-review末尾四项确认命令；只在终端输入sudo密码。agent本轮没有启动向导、服务、认证、刷新、模型或信号，也不接收密码。

后继状态：所有者随后报告已运行，已只读复核[本轮结果](../../../docs/verification/issue-167-e01-result.md)为observed_expected_and_restored。该单次许可已消费，不可再次运行；后续K/T方向及新批次另行裁决、冻结和批准，原批准交付时的检查与记录不改写。
