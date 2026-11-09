# G3 所有者审阅与当前观察新鲜度修复

本台账仅覆盖所有者完整审阅、手动短 ID 与执行前真实当前观察的衔接。
不扩大历史 required、回执或固定分母，不修改旧 scope／中央成员或哈希。
真实 G3 尚未通过；不以离线绿替代所有者实际部署、采集或证据激活。

## 公共 seams 与独立覆盖

| 模块 | 人工预期节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_live_evidence_review_freshness.py` | 17 | 实际 owner CLI、临时受信账本、假钟推进完整审阅超过60秒；同事实新观察成功；binding/coverage漂移、旧/未刷新/未来观察、部分撤销、恢复屏障、来源丢失、时钟回退、原能力到期、采集失败及错误短 ID 拒绝；固定零参数冻结 collector 的OS边界 |
| `tests/test_live_admission_source_guard.py` | 5 | 原四节点保持，追加 v2 清单原字节归档保护；当前 v3 显式33文件与策略摘要锚 |
| `tests/test_site_runtime_upgrade.py` | 27 | 原7项红模型扩展：旧SHA/manifest/完整成员/权限/硬链/入口/policy/cwd/中断态；新包身份及语法；一次sudo替身到新payload部署/合成采集接收，篡改与失败保留历史、不激活 |

测试只替换当前时钟、临时 OS 信任根、人工输入与固定 collector 的系统调用边界。
不执行真实 sudo、collect、receive、revoke、activate、认证、模型或网络。
既有 owner CLI 7 节点仍保留原意图：过期初始观察拒绝、完整摘要、正确/错误手动确认、
未刷新旧观察不能在阅读后使用、show 与两处冷帮助；仅补 collector OS 替身及假钟调用点。

## 根因与安全行为

最小回归首次红：`tests/test_live_evidence_review_freshness.py` 为1 failed in0.44s。
单一已接收必需站点主张、有效观察、正确短 ID，在完整摘要之后假钟推进61秒，
实际 owner CLI 精确返回 `observation_stale`。剩余触发因素均是公开链路必需项。

旧链路有三个叠加条件：确认后重读审阅前观察；lifecycle另将reviewed_at限制为60秒；
观察整对象相等又把真正刷新后的observed_at变化视作事实改变。
修复将完整人工审阅与执行前观察分开：正确短 ID 后调用固定root冻结collector，
读取本次刷新产生的真实观察，核完整binding/coverage不变及60秒时效，
再以真实当前时间在保护事务内重新生成完整审核摘要及eligible集合，一致才写入。
原receipt、登记、原verified_at、期限、分项原状态/原因与恢复屏障均保持，
改变时拒绝或要求重新审阅，不静默激活剩余子集，不延长能力期限或减少必需项。
错误确认不触发collector。采集失败、超时或缺失得到受控拒绝。

## 开发验证

当前相关组合90 passed in1.93s，退出0：新增17、D7五项、既有owner CLI/lifecycle/loader/
CurrentObservation与site collector。没有skip/deselect/incomplete。
修复源码及直接测试六文件strict mypy通过；七文件格式检查与git diff --check通过。
新增测试首个红之后绿，随后安全负例及原始公开路径均重复验证。
CLI兼容59 passed in119.86s，入口退出0、含uv总耗时120.49s。
只读scope审计退出1，baseline_issues为空，仅继承cli.py/contracts/schema.py/pi_supply/cli.py
三项baseline_drift/mechanical，本次没有current_change候选；未重绑旧材料，消费闭包交#176。
升级最终相关组合89 passed in26.65s，覆盖新升级当时26节点、旧部署/单入口/保护链、
collector、owner freshness与D7；随后追加构建CLI缺少配对摘要在读site前拒绝的冷进程回归。
最终独立升级模块27 passed in18.67s，三个变更文件Ruff、格式与strict mypy通过。
新增模块人工预期27节点，与参数化和实测输出核对，不从生产登记反填。
本轮升级只触及非特权构建CLI与生成脚本，既有product CLI导入/注册未改，
已通过CLI59不重复；构建冷help、缺项、空环境导入和脚本语法由相关测试直接覆盖。
完整离线门禁、真实root与G3均未执行。

## 策略与现场承接

受守卫lifecycle变化要求显式升级为`pi-admission-v3`。
新清单`tests/fixtures/live-admission-source-guard-v3.json`，格式仍1，33文件集合保持；
v1/v2原清单及摘要锚保持，只追加v3摘要锚，追加v2字节保护测试。
v3清单SHA256为`78c7e3f27768e138a9137395cefb71cb0058005020cf3a4d1ac4ad9fc5726fc6`。
旧策略证据不能借绑定漂移继承新资格。

现场已部署旧root runtime，不允许直接覆盖或声称旧回执已由新代码核验。
新的root字节须所有者重新审阅；正式推进须保留旧账本/回执/撤销/stopped/历史/预算，
按明确旧payload/manifest核验后安全归档升级，再新计划采集/接收与人工G3。
升级代码生成机制起初被自动批准审查拒绝，理由为高影响root升级机制缺明确授权。
所有者随后针对“仅编写并离线验证旧SHA/manifest核验、归档旧runtime、替换已核入口/sudoers，
完整保留账本历史预算，实际sudo/采集/激活仍本人审阅后执行”明确回复“授权”。
据此重新请求自动审批并获准，只实现代码与无root离线验证，没有执行现场操作。

原7项升级模型先因缺render_upgrade全部红，再绿；完整受控原因回归捕获shell管道子进程
丢失拒绝原因，已改为主shell循环。额外payload标记换行、特殊权限位与非空cwd分别先红后绿：
旧标记改为规范字节SHA，成员/入口/policy模式精确校验，cwd先决提前到归档前。
单入口模型先普通用户核SHA，再一次sudo替身复制并重核，归档原runtime，安装不同新payload，
调用合成collector/receive并输出新实际短ID。用户包篡改、复制前竞态篡改、旧源码变化在归档前拒绝；
采集失败不receive，旧账本/inbox/stopped/失败历史逐字节保留。成功后重复运行同包安全拒绝，
中断不自动恢复或清除归档。真实sudo/冻结保护/站点采集/接收/G3仍全部留给所有者。

升级详细公共规则仅见[live-evidence Contract](../contracts/live-evidence.md#β-站点采集与封印部署)。
新包必须从最终合并后的主工作树非特权重建，旧G2包原字节保持；新的root字节仍需所有者重审。
