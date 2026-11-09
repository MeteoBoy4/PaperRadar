# #176 owner业务预算采样：稳定空WAL与SHM只读兼容

本补充记录最终owner流程的I/O兼容修复，不回写先前审阅修复台账、历史回执或固定分母。
不改变保护准入账本的hot-journal／WAL／SHM拒绝规则，不修改业务预算或必要绑定。
实际EXP2及root未由本次修复读取或变更，旧69候选包已经标为勿运行；最终包须按新integration身份重建并审阅。

## 公开行为与红绿

现有owner业务预算采样拒绝任何侧文件，会阻断正常残留的0字节WAL＋32768字节SHM。
临时SQLite先提交合成七表，再仅在fixture启用WAL并SELECT即可构造相同形状，无须checkpoint。
首个公开 `budget_inventory` 回归按原实现以closure_business_sidecars_present失败；修后可读全部必要字段，
七组预算ID／指纹／代际／attempt／每日领取标识的原有行数与摘要算法保持，payload列由authorizer拒绝。

允许无侧文件，或regular／单链接／产品uid所有、size=0的WAL及可选同样可信SHM；只lstat，不读侧文件正文。
journal即使为0、非空WAL、无WAL的单独SHM、链接／类型／uid失信仍受控拒绝，不删除、清理、checkpoint或切换模式。
主库路径与固定O_NOFOLLOW只读fd相互核对；主库与各侧文件的dev/ino/mode/nlink/uid/gid/size及纳秒mtime/ctime
在打开、各次查询前和结束复核，增长、替换、触碰、侧文件出现／消失或open竞争均以受控changed拒绝。
atime可由自身只读访问改变，不作为内容变化依据。任务与其他写入暂停是前提，metadata检查不保证任意并发下的原子快照。

[SQLite WAL格式](https://www.sqlite.org/walformat.html)说明WAL承载未回填主库的提交，SHM为索引；
仅WAL确实无frames且稳定时，才从主库采样。
[SQLite immutable语义](https://www.sqlite.org/uri.html#uriimmutable)跳过锁及变化检测，因此它仅用于避免SQLite写侧文件，
不能代替暂停条件或显式稳定性验证，不作为并发安全证明。

## 独立覆盖

| 模块 | 人工节点数 | 责任 |
| --- | ---: | --- |
| `tests/test_owner_budget_readonly.py` | 17 | 真实空WAL＋SHM字节／metadata不变及不打开侧文件1；空WAL无SHM不创建1；非空／journal／symlink／hardlink／uid／孤立SHM7；读取期间增长／替换／mtime变动／journal出现／SHM消失／查询中变化／open竞争8 |

本模块为新增独立未绑定覆盖，不追溯扩大旧31模块478节点结论；新消费闭包可单列新增本模块与当前源字节。
既有 `test_owner_budget_check_selects_only_ids_generations_and_attempt_counts` 四节点不变，继续拒绝原非空WAL／SHM／journal，
保留payload拒读、行数、原文件字节和无侧文件创建断言；业务before/after全部预算身份比较仍由owner工作流执行。

## 验证与现场边界

初始0-byte WAL/32768-byte SHM回归先red；随后新模块与旧四节点定向通过。
仅运行受影响owner／预算／包／guard／文档子集与静态检查，不重复143／50或完整门禁，不发布旧组验收结论。
未发布v4的当前源码清单／摘要锚随最终脚本字节刷新，v1/v2/v3及其锚原字节保持。
本模块17节点collect相符；owner／预算／包／guard／文档定向组合**56passed／18.92s**，无skip／deselect。
相关五Python文件Ruff／format／mypy通过，git diff --check通过；新v4清单仍39源码，
SHA256为 `ff8a37321ea097d9d444d4840212f249431d36d2b364f275f7ca1253db7cefc1`。
本补充17与原31／478的当前人工并集可单列32模块495节点，不追溯扩旧结论或required。
实际owner新包和OS演练仍须主代理在最终integration重建后交所有者执行。
