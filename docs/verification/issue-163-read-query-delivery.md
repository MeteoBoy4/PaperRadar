# Read 当前性与配置已旧查询独立覆盖

依据 [#163](https://github.com/MeteoBoy4/PaperRadar/issues/163) 及
[#155](https://github.com/MeteoBoy4/PaperRadar/issues/155) 评论 2/4/5/7。
主 seam 是已确认的 ReadQueries 公共只读服务，组合真实 BodyService、ReadTasks、
历史配置和 backup/restore；parser、HTTP、模型执行边界使用合成替身。
不以调用方传入的裸投影或数据库侧查询代替业务可观察结果。

## D1 模块与节点

| 模块 | 节点 | 覆盖 |
| --- | ---: | --- |
| tests/test_read_queries.py | 7 | 无分析与身份不可判区分、PDF换字节、多成功正文歧义及新领取拒绝/旧历史保持、安全DTO及丢弃整条不可回查、实验空结果普通拒绝、缺PDF、受限警告、当前版本不能借旧版本正文 |
| tests/test_read_query_config.py | 13 | 缺省/非法/缺失/未就绪unknown不进old、显式可核对快照且不读settings、Profile/Read模型/Prompt/adapter差异、其他Screening/纯版本变化不使Read旧、按提交序且A→B→A幂等不改最新、zh/en共存、新指纹失败不替换、损坏参照不自证 |
| tests/test_read_query_readonly.py | 2 | 全入口真实mode=ro连接/零写SQL/共享visibility空集合调用、未结算租约预算和DB字节不变；书目补全/metadata后变/旧人工依据/质量否决/样本/PDF及换回旧PDF不抹合法历史 |
| tests/test_read_query_recovery.py | 1 | 无SDK真实基础冷进程异地恢复，两轴/语言/降级输出与计数/old列表/证据/未结算预算一致，原根/网络/模型执行拒绝、恢复后全树字节不变 |
| 合计 | 23 | 独立未绑定 D1，stage_a_verified=false |

支撑：tests/read_queries_support.py、tests/read_queries_recovery_worker.py，复用
tests/no_extra_runtime.py 与 PAPERRADAR_NO_EXTRA_PYTHON；保留 metadata 缺少 SDK 的实际断言，
另外禁止 SDK/model 导入、网络和外部进程。守卫不冒充依赖未安装。

## 边界与承接

本文没有加入 A1–A10 旧成员、固定分母、required 或新的 Contract live 分类。
A9 v1 源码/15模块/560节点/格式、A8旧向量及已批准的A5窄变化均保持本票基线字节。
没有 migration、投影缓存表、产品 CLI、自动队列或新模型调用。
已有 ADR-0041/0042/0043/0044/0045 直接适用，没有新增领域决策。

配置变化只返回六类安全组件，Contract/chunking 的未来版本未在本票创建；
当前受支持版本的投影与就绪核验仍由既有配置服务负责。
同PDF多成功正文的显式选择由B/F承接，当前查询与新领取共同安全拒绝歧义，
旧claim refs和历史metadata引用的核验不要求当前资格仍成立。
低层ReadAnalysis原始候选仍只供持久回放；展示DTO只携带接受后的内容和安全计数/警告。

相关功能pytest、CLI导入兼容、静态和scope审计的实测记录见外部完成报告；
继承的15 hash_drift及86确认候选留给#165最终集成树S3，不机械重绑或生成确认。
未运行完整离线门禁、live、真实Pi/Docling、正式质量/校准、B产品闭环或NAS。
