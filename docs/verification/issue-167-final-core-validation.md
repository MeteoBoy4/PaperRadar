# #167 H4 终局：显式零 core 限额的合成正负对照

本轮依据所有者明确授权验证第三条路；不选全机分发器，亦不改回全局“不外流+可清理”路线。计数终局见[ADR-0048](../adr/0048-accept-bounded-request-observability.md)，core决定见[ADR-0049](../adr/0049-bound-core-persistence-with-explicit-zero-limit.md)。基线仍为 `c0bee235f4ebb0a88be4a60c392c96619ec61683`，保留前轮未提交工作。

## 结论

**两例实际结果支持绑定到当前Apport非打包分支的第三条路径，没有得到具体反证。** 同一合成ELF、同uid、空环境、同目录与handler，仅改变exec前设置的RLIMIT_CORE软硬限额；两例均自触发SIGSEGV（退出-11），没有Pi/Node、认证或模型请求。

| 案例 | exec后样本自行回读的soft/hard | /var/crash新增成员 / 新增事件 | /var/lib/apport/coredump新增成员 / 新增事件 | 结果 |
| --- | --- | --- | --- | --- |
| 零限额 | 0 / 0 | 0 / 0 | 0 / 0 | 观察到预期无新增，包含短暂创建后删除事件的检查 |
| 非零正对照 | 67108864 / 67108864（64MiB） | 0 / 0 | 1 / 1 | 唯一新rawcore按合成exe编码路径、uid、pid精确归属；未读取其内容 |

uid两例均1000；不公开或读取任何原有crash/core成员内容。样本退出后每例继续8秒目录观察，inotify覆盖完整，没有overflow、目录删除/迁移或额外成员；不是无限期“永不写入”证明，也不外推其他collector、配置、服务uid或打包路径。非零正例成立，使零限额结果不只是“collector根本没运行”的同零观察；固定源码分支与此次对照共同支持限额是这两例的决定差异。

## 方法与身份

- 合成原生C源码保存在[审查材料](../../intent/review/issue-167/core-limit-sample.c)，只打印自身pid/uid/core限额，等待单字节门闩后raise(SIGSEGV)；不读取文件、网络、认证或环境内容。C由本机cc编译到工作区 `/home/…/.scratch/issue-167/core-limit/`，模式0700、同uid、无symlink，被现有likely_packaged路径规则判False。
- Python显式授权入口 `scripts/issue167_core_limit.py --run-authorized-pair` 用同一ELF顺序运行两例；env为空，exec前setrlimit分别为(0,0)/(64MiB,64MiB)，RLIMIT_AS=32MiB限制无秘密正例体积。只有样本回读元数据完全匹配才释放崩溃门闩。
- 不设置dumpable=0，不改core_pattern、suid_dumpable、Apport/unpackaged或服务配置。现有handler路径、当前账户默认unpackaged=false与非打包分支依据沿用[只读报告](issue-167-node-auth-facts.md)。源码检查没有发现limit0早退被绕过的具体反证。
- 两目录仅取成员集合、inotify新增/迁移事件及本次新core的lstat；不打开core/report，不读凭据、进程environ、上传日志或旧制品。普通用户跨工具沙箱执行实际样本，uid1000，无sudo/root，不把沙箱namespace的handler早退误当正对照。
- 预检当前uid已有rawcore数0，小于Apport自动清理阈值5，避免非零例触发对旧core的删除。收据在首个崩溃前排他预占，已有收据拒绝重跑；它只是防误重复，不代表更换路径可自动获得授权。两例仅执行一次，不重试、不重跑EXP-2。

| 本次材料 | SHA-256 |
| --- | --- |
| C源码 | `cc7c64ce94a019d14ecb883ca1f319b3ebdc156ebadbc572c1dbca3d52ecf7e8` |
| 实际运行合成ELF | `a08cc0f8b016872f771d2ba83fd2eed0eb631ecba4f007d64f21b879e6a9aa8d` |
| 实际执行时runner字节 | `7574c3df67483a6452e4bb5a6311cfcb0ec950875dbb2a433af51db7e9b18db4` |
| 原始合成两例收据JSON | `722ce49bbbb4433bd190cd339e6870e5c3a83bd6de55fc4ce6ddf4f21c5be4a0` |

实际执行runner与原始收据保存在忽略目录 `.scratch/issue-167/core-limit/executed-runner.py`、`pair-receipt.json`。执行后独立审阅新增DELETE_SELF立即失效和正例瞬时report事件拒绝的回归/收紧，以及异常时保留已完成cases；当前两例均无目录删除、report事件均0，因此不改变结果。原执行字节/收据保留，不为这些收紧再制造崩溃。

## 残余与回收

正例产生的唯一无秘密rawcore为普通文件、uid1000、0400、454656 bytes；只检查元数据，未读/复制/归档其内容。父目录root所有0755，当前普通用户不能unlink。本轮不执行root操作，不按前缀/通配符删除任何文件；**此正例文件尚未删除**。精确成员与设备/inode/大小记录在 `.scratch/issue-167/core-limit/positive-member-metadata.json`，供所有者审阅的精确交互删除命令在同目录 `owner-cleanup-command.txt`；执行前应核对归属/元数据，不能删其他成员。测试生成这一无秘密制品不是未来真实任务可保留core的许可。

所有者明确接受Apport可能在root内存读取过环境而不落盘；本轮不把它说成从未读取秘密。未来依赖实际Apport版本/配置、路径/uid、有效限额与非打包分支，漂移长期doctor检查属于后续工程，不在本票实现。备份/上传的全局unknown不被伪装为已解决，也不再作为第三路的证明前提。

## 目标与已实现范围分开

规格和部署候选要求项目持密子进程exec前软硬RLIMIT_CORE=0、服务LimitCORE=0；本轮合成runner已显式设置进程限额、现有服务模板有LimitCORE=0。**本轮没有改生产auth/model启动器或安装服务，没有宣称产品已显式强制该限额或已取得Live准入。** 实际接线、现场配置与适用证据接收仍由后续明确工程和适用H1/H2承担；doctor长期检查明确移交而不在本票扩展实现。其余文件/网络/进程/认证/模型门禁仍分别满足，B未因此开始。

计数按终局只声明可证近似下界与unknown；token用量预算计量依Pi报告，缺失或零值仍未知，不取消attempt/每日配额。隐藏重试、预热、刷新限制进入后续doctor/日报口径，精确请求数交I无人值守/NAS重评。loader保留离线材料，不登记请求覆盖、不计入分母、不接产品、不改变启动身份、不为此重跑EXP-2；历史证据和unknown原字节保留。

## 开发验证

新增 `tests/test_issue167_core_limit.py` 为独立未绑定D1模块：15项通过，pytest不编译/执行C、不制造真实崩溃。覆盖事件截断/overflow/DELETE_SELF拒绝、瞬时成员元数据、精确归因、路径与收据拒绝、合成run_case流程。DELETE_SELF回归先红，修复后绿，独立复核确认对本次实际观察无影响。

命令仍采用 `uv run --offline --locked …`，缓存前缀 `UV_CACHE_DIR=/tmp/issue167-observation-uv`。定向Ruff check/format与 `MYPYPATH=src … mypy scripts/issue167_core_limit.py tests/test_issue167_core_limit.py`通过。固定范围审计、链接与diff结果在最终回帖记录。没有完整离线门禁、真实Pi/Node/模型验收或产品激活。
