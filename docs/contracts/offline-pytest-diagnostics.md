# 离线 pytest 未绑定失败辅助诊断

## 用途与范围

完整离线入口通过 `scripts.a2_test_receipt` 收集 pytest 回执。
未绑定模块不进入正式回执的固定成员；辅助诊断为其失败提供安全模块定位。
`read_failure_diagnostics` 是离线控制方的只读消费接口；它不参与验收或状态查询判据。
该辅助模块只在 tests 检查实际失败时加载；历史状态读取不加载辅助诊断或当前生产组登记。

## 规则

- 诊断文件从本次 `PAPER_RADAR_TEST_RECEIPT` 路径派生：
  `<run_id>.pytest.json` 对应 `<run_id>.pytest.failures.json`。没有独立诊断环境变量；
  嵌套离线检查清除继承的回执/run_id，然后仅为自己的 tests 检查绑定新身份。
- pytest 仅在未绑定模块实际失败时写入辅助文件。允许阶段为
  `setup | call | teardown | collection`，同模块同阶段去重、按模块和阶段排序。
  模块必须是当前根 `tests/` 下实际存在的普通非链接文件，精确匹配
  `tests/test_[a-zA-Z0-9_]+.py`，并且不在正式回执模块集合中。
- 独立格式 1 恰有 `format_version`、`run_id`、`receipt_sha256`、`failures`。
  每条 failure 恰有 `module` 与 `phase`；回执更新后同步刷新其 SHA-256。
  不保存 nodeid、函数名、参数、异常、skip 原因、原始输出、绝对路径或输入内容。
- 消费方通过不跟随链接的非阻塞描述符读取，拒绝非普通文件或超过 1 MiB 的回执或诊断、额外/缺失字段、非法类型、
  非当前 run_id、回执字节哈希不匹配、非法模块/阶段、重复或乱序条目。
  条目数量最多为当前允许模块数的四倍。坏或缺诊断返回空定位。
- tests 检查实际失败时，控制方仅对有效定位输出
  `[离线检查] 未绑定失败：tests/test_example.py (call)`。
  正常或仅固定模块失败不生成辅助文件，正式回执格式及正常十四份 JSON 保持。

## 错误与拒绝

pytest 实际退出码和既有检查/组/终态判据保持唯一权威。
辅助写入失败、文件缺失或校验失败不能升级结果、隐藏非零退出或伪造通过。
入口仍抑制子进程 stdout/stderr；没有原始错误回显或保存入口。

## 不提供／不证明

辅助文件不是正式证据、不进入 terminal 哈希绑定、required 集合或历史固定分母；
不提供函数/参数级定位，也不证明某个安全模块名下的具体失败原因。
维护者可按模块单独重跑获取本地诊断，分享前核对敏感输入。

## 相关

依据：[#140](https://github.com/MeteoBoy4/PaperRadar/issues/140) 后续外部审阅修复与未绑定失败定位要求。

- [离线证据入口](../verification/offline-evidence.md)、[正式状态查询](verification-status.md)。
- [开发组合检查](check-compatibility.md)、[本次独立覆盖](../verification/issue-140-external-review-followup.md)。
