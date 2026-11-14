# #199 实验报告工程覆盖

本台账只记录离线合成工程验证，不授予真实材料、Pi、Docling、现场隔离、NAS 或生产消费资格。
规格依据 [#185](https://github.com/MeteoBoy4/PaperRadar/issues/185)、
[#199](https://github.com/MeteoBoy4/PaperRadar/issues/199)；现状规则见[报告 Contract](../contracts/reports.md)。

## 实现边界

新增线性 migration `b006_reports`，父为 `b005_layout_recordings`；建立最终 report run/entry，
固定 daily/paper、experiment、日期/时区、paper/version、primary/supporting、N1–N5、
栏位/顺序/首次发布键、投影 fingerprint、renderer 与发布结果。
准备事务冻结完整输入后同目录临时文件、成员/来源/evidence/路径核验、fsync、atomic replace、published；
历史重建只读 SQLite，使用显式 database/data_root/output_dir，标准恢复无需执行根布局。
报告不调用模型、不建任务/预算、不重验当前宿主/认证/安装或受保护 Live 链。

日报上限五项、成功分析三项，分析 FIFO，pending/全文受阻竞争非分析槽位；
单篇修订与 daily 首次发布键独立。同日日报固定后，晚到成功不改原字节。
Read 只消费权威 analysis_payload 与历史 attempt 依据，不从 safe trace 或当前 PDF 猜历史。
原题名、非决定支撑 Screening、授权者/代执行者、受限内容未核对与 discard 计数均在私有报告保留。
题名链接被字面显示；结构化内容不能逃逸代码围栏，错误/日志不携带这些私有正文。

Reports.validate_all 只经 experiment.validation 唯一接入备份；Reports.history 提供原始
paper/version、primary/supporting 及授权历史，供后续暴露清单消费。

## 独立 D1 收集与结果

九个模块均为新增、未绑定 D1，不改变旧 scope 的 required 集合、固定分母或历史证据：

| 模块 | 完整节点数 | 覆盖 |
| --- | ---: | --- |
| test_experiment_reports_cli.py | 11 | 固定空日报、成功分析/单篇、pending/缺 PDF、故障空日报、冷帮助、日期/TZ、私有内容与安全输出 |
| test_experiment_reports_capacity.py | 1 | 六成员真实合成 CLI 准备、五项/三分析、FIFO、独立单篇与原日报重建 |
| test_experiment_reports_recovery.py | 1 | replace 已完成、published 未提交→当前豁免关闭→backup/restore verify→冷进程固定字节 |
| test_experiment_reports_faults.py | 4 | SQL 边界、同日并发、坏字节/缺成员/不安全路径、备份 registration_invalid |
| test_experiment_reports_late_results.py | 2 | 空/失败日报发布后才成功，原 run 不变、paper 可发布且次日进入 daily |
| test_experiment_reports_migrations.py | 5 | 非空上一 revision 升级、四处 DDL/提交故障原子回滚、真实 restore verify |
| test_experiment_reports_logging.py | 2 | 执行入口 FileSink、只读动作不建日志、每次共享 visibility 与拒绝 |
| test_experiment_reports_publication.py | 2 | 临时文件 fsync/replace 故障、清理自身临时文件、不破坏已发布字节 |
| test_experiment_reports_sections.py | 1 | code_tool 受控价值类型进入可转化成果栏 |
| **合计** | **29** | **全部通过** |

实际完成组合：

- 25 passed /857.44s：前六模块完整 24 个新 D1，加独立
  `tests/test_config_service.py::test_upgrade_is_idempotent_and_schema_matches_metadata`。
  容量节点 542.37s；冷恢复 92.03s；late 失败/空分别 61.66s/37.46s。
  容量中的逐篇真实 CLI 准备反复校验上游历史；120s faulthandler 仅打印诊断，节点最终通过，无 skip/deselect。
- 4 passed /2.05s：日志与文件发布故障两个完整模块。
- 2 passed /36.37s：code_tool 新节点与既有 doctor 豁免披露回归；保留旧 not_assessed header，增加共享分项。
  这两个必要窄修复的最终验证单列，不借更早的同名组合结果替代。
- 独立冷恢复再次 1 passed /102.19s：renderer 固定字节后复核 import 拒绝、网络拒绝、原路径拒绝、
  标准 database.sqlite3/根级 blobs 重建、原成员/first-key/字节及恢复树库存不变。
- 91 passed /89.62s：migration_expectations、backup_service、backup_integrity、backup_failures、
  restore_service、restore_failures 六个完整公共模块。
- 独占 TMPDIR 预先创建后 `check-compatibility cli`：59 passed /84.19s，入口总 84.80s。
- 全部触及的 33 个 Python（含生产、全部新 test/support、迁移 head/scope 声明）默认 strict mypy、
  Ruff 与 format 均通过；实际提交范围 diff-check 另在交接登记。

上述最终覆盖去重为 181 个节点；单列冷恢复为重复复核，不扩新 D1 29 的分母。
完整收集节点、逐模块数量、33 Python 清单与原始日志保存在本次外部交接材料。

## TDD 与诊断分界

空日报 red 为缺 report 命令；成功分析 red 为空成员；pending red 缺非分析成员；
缺摘要 red 错称无新结果；题名链接 red 生成 file 链接；code_tool red 错入 cognitive。
分别经 CLI 行为绿测关闭，未修改旧冻结断言来通过。
较早两个容量运行中断/诊断与 renderer 修改中途的跨版本恢复哈希拒绝均不算最终通过；
最终新根容量与 renderer 稳定后的冷恢复已按上列实际节点完成。

## 固定范围与未验边界

人工推进唯一 head 常量、十个 scope、A3 格式、生产 backup revision、两份 Contract 与两个中央哈希。
既有 migration、刻意历史 revision、旧测试/fixture/历史证据保持原字节。
新 reports Contract 在 inventory 的精确路径分类为活文档；分类仍需全部受影响组 S3 确认。
旧 source/support 哈希不机械重绑；scope 审计的敏感确认和 43 边/15 路径漂移由集成收口负责。
请求 collect 被 audit_failed 阻止时，不宣称固定分母已重新收集。

未运行完整离线门禁；没有真实/live 命令，没有真实实验根、运行专用 checkout、私有材料或真实凭据读取。
所有数据来自 /tmp 合成 HTTP transport、Pi RPC、parser/cgroup 与时钟边界；
冷进程 Python 守卫不是操作系统隔离证明。真实数据/资源、脱网现场、暴露导出、NAS 与完整生产日报，
分别由 B 后续闸门及 C/F/G/H/I 责任承担。
