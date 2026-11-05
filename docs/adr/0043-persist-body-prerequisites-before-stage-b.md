# Body 持久前置事实，B 提供真实产品流程

状态：已接受；日期：2026-11-05；依据：[#155 裁决](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6631023698)、[#155 根用途裁决](https://github.com/MeteoBoy4/PaperRadar/issues/155#issuecomment-6632720328)、[#158 补充](https://github.com/MeteoBoy4/PaperRadar/issues/158#issuecomment-6634183486)；补充 [ADR-0036](0036-isolate-stage-b-read-experiment.md)。

Body 持久保存一次写入不可变的根用途、直接人工决定、实验样本、PDF 选择、提取预算与逐文档质量，B 在同一公共服务上提供建根、选样、决定、真实核查和报告命令。根用途以 SQLite 为唯一事实源并绑定根登记，不另写文件标记，使严格备份集合和路径迁移后的用途拒绝保持一致；代价是不得凭数据目录名推定用途，也不能用临时投影替代恢复闭包。

人工决定仅接受 direct_manual_decision，论文内序号由写入 API 分配，并消费共享 visibility。Read 的上游执行来源取决定事件自身引用的 Screening 成功，不因其变为历史而失效：任一 test 优先为 test，全部 pi_rpc 才为 production，无引用为 unknown。B 的决定命令须提供 Screening 引用；纯人工 accepted 的专用通道留给 B/C。这保留旧人工决定的效力，同时接受 Body 无法读取纯人工 accepted 的限制；Read 自身成功来源另行判断。

自动质量通过与独立人工版式通过共同产生实验逐文档依据；人工否决绑定正文三元组并对指纹永久，后续通过按矛盾拒绝。F 持有 formal_gate 与四刊代表性门槛，B 执行真实核查；Body 的记录与合成不能代替这些依据。提取预算在全库按 backend 与指纹共享，根级等待锁只串行本机同根转换，不扩大成跨机资源保证。
