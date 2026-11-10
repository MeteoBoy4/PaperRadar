# #182 固定模型采集闭环独立工程覆盖

依据：[#182](https://github.com/MeteoBoy4/PaperRadar/issues/182)、[#177 最终裁决](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)。这是独立 D1，不扩大历史分母，不继承 A1–A10 或 Live 现场结论，不新增 required 组。

| 独立测试模块 | 节点数 | 公共接缝与覆盖 |
| --- | ---: | --- |
| `tests/test_model_collection_dispatch.py` | 7 | 公共 prepare/run_call；exec-stop auth 预占、首 prompt 字节预占、精确 completed-case 查询、合成语义与真实 latest 安装分离、错模型／WS 安全拒绝、终态 metadata 与独立删除 |
| `tests/test_model_collection_materials.py` | 7 | 纯配置编译不连接／写业务库；实际公共 prepare→真实本地合成 RPC 进程→boundary/value/read × low/high 权威接收，Read 固定 ordinal=1，无合成 snapshot 注册或业务 task |
| `tests/test_model_collector.py` | 10 | 固定 root 入口四负对照→六格→受保护完成/inbox；精确续跑与原时点；首失败组停止／安全域首停；当前观察不能代替站点完成源；带 pending 的发布中断恢复、已发布来源丢失拒绝、零参数边界；payload 无部署后未来值；运行绑定来源不重建 |
| `tests/test_model_network_collection.py` | 2 | 真实规则结构与 drop/reject counter 精确增1；缺归属／无增量／多增量／handle变化／其他 counter 演进拒绝，errno/timeout不冒充通过 |
| 合计 | 26 | OS/RPC 边界替身与本地合成对端，均不证明现场权限或供应商行为 |

`tests/model_collection_support.py` 只提供独立 root 库存、当前观察、放置／counter 和 fork/RPC 边界替身。未替换正式 admission 或注入 test 许可。既有 `tests/pi_placement_support.py` 只补返回类型／显式错误导入，不改断言或行为。公共 A8 协议负例复用，原缺 usage/totalTokens=0 语义未改。

新策略为 `pi-admission-v9`／`pi-launch-1.4.0-v8`；D7 的 `live-admission-source-guard-v9.json` 单独绑定当前源码，新增八项显式来源（六个 collector/network 模块、dispatch 受控流与纯配置服务）。v1–v8 清单原字节保留，已有 D7 守卫的八个节点复用，不计入上表新分母。初始 `live-admission-v1` 35 项登记、receipt/plan v1/v2 wire 和旧冻结协议负例均保持。

开发期按 red→green 纵切完成预占、纯编译、安装上下文、权威接收、root 闭环、续跑、counter归属及发布中断边界。此前直接影响组合 459 passed；后续公共正式启动、Read/Screening 准入与 RPC 相关组合 164 passed。最终运行绑定变化后，本表26节点加 `test_observation_refresh.py` 共57 passed；最终 D7 守卫8 passed。触及源码和新增测试的 Ruff／严格 mypy 通过。开发期组合不代替最终冻结树完整离线门禁。

`./scripts/check-compatibility all` 实测 65 failed、111 passed，退出1；失败为尚未对白名单实际 source/support 字节重绑的 `scope_drift` 及失败终态传播。未降低旧标准、修改旧分母或冻结负例以绕过，交父票统一审阅精确重绑后复跑。只读 scope audit 记录当前变更供最终集成审阅；本票不机械修改共享登记。

实际 root 权限、私有 fork 降权、systemd scope/ptrace/userns/resolver、nft counter归属、真实认证／模型、终态实际文件行为及 owner receive／逐格激活仍未验证。封印包应先安装实际 target／counter规则、处理所有者已确认的旧 cache 迁移并严格 β，再由当前 root 观察与严格站点完成源生成确定性运行绑定；不得构建前自拍或排除未知成员。自然到期／真实 refresh 缺无秘密事件时仍未知，不因成功调用或 stat 演进判通过。后继封印安装、现场及最终门禁由 [Live](../roadmap.md#module-live) 承接。
