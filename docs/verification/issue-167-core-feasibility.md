# #167 A4：pre-exec 禁 core 候选的可行性复核

2026-11-07，本次只对新建、无秘密的 Python 子进程读取/设置其自身 prctl 属性并普通 exec；没有执行 Node/Pi、认证或网络，没有制造崩溃、发送信号、读取已有 core、修改 core_pattern/宿主策略或其他程序。代码为 `scripts/issue167_core.py`，独立未绑定测试为 `tests/test_issue167_core.py`。旧证据原字节保持。

## 实际结论

**只在 exec 前设置 `PR_SET_DUMPABLE=0` 不能保护 exec 后的普通模型/认证进程。** 合成子进程执行固定 Python 小程序后，实际观察如下：

| 模式 | exec 前 | exec 后 | exec 后再次进程内设置 | 结论 |
| --- | --- | --- | --- | --- |
| 不额外设置 no_new_privs | 0 | 1 | 0 | pre-exec 保护丢失 |
| 显式设置 no_new_privs=1 | 0 | 1 | 0 | no_new_privs 不阻止此次重置 |

本环境两例实际读到的 no_new_privs 均为1（第一例继承已有约束，没有尝试清除）；不声称测试了 no_new_privs=0。探针只 exec 同一个 Python 解释器，不触碰固定 Pi 安装。子进程自身 RLIMIT_CORE 设为0作为附加防护，但不把它当 pipe handler 的阻断证据；整个实验没有 crash 或 core 事件。

本机 `execve(2)` 的“Effect on process attributes”说明普通 exec 把 dumpable 设为1，特殊身份/capability exec 有另行规则；`PR_SET_DUMPABLE(2const)`描述0/1设置及身份变更；`core(5)`明确 pipe 方式不执行 RLIMIT_CORE 限额。本次实测与这些本机手册相符。无需、更不能为复现上述属性重置而制造一次含秘密的崩溃。

因此[上一轮部署候选](../../intent/review/issue-167/deployment-plan.md)的 pre-exec prctl 必须作为**已被否定的充分条件**处理；`LimitCORE=0`、`CoredumpFilter=0`与其他namespace/文件白名单也不能自行补成“全过程无秘密core”。本报告不改写上一轮证据或把当前实现提升为准入通过。H1/H2 当前不能据旧候选启动认证或模型。

## H4 可裁决替代路径

| 选项 | 具体变化与成本 | 保留风险/准入影响 |
| --- | --- | --- |
| 保持固定供给并继续阻断 | 不改变供给或主机core；先完成其他离线项，core与认证调用等待可验证方案 | 成本是Live/B等待；不能把等待或有限探索接受改称core通过 |
| 新的受控启动器/运行时供给 | 在目标进程 exec 后且接收任何秘密前，于本进程内设置并验证dumpable=0；使用内存门闩之后才供给秘密，并约束后续exec/身份变更及后代；冻结新的供给/启动策略并重新验收 | 当前OPENAI_API_KEY在exec环境中供给，简单preload/JS import不能证明动态加载/初始化前没有泄漏窗口；固定Node/Pi是否有满足条件的早期本进程入口尚未证明。需新工程、供应链/兼容回归与H1/H4，不能静默patch固定安装。native嵌入或受控runtime也要证明不再exec、不会重新开dumpable |
| 项目定向的core处理路径 | 由所有者审阅现有collector是否能按可信项目service/cgroup身份在持久化/额外proc采集前拒绝本项目core；保持其他程序原有处理语义，提供卸载和恢复 | 本轮未核查/部署具体collector。不能仅在收到完整core后再过滤保存；处理器可能读取environ/maps等。若必须替换全机core_pattern/代理handler，属于新的明确H4取舍，当前“不长期改变其他程序core行为”约束仍在；不能自行把全机丢弃当实现细节 |

本轮不代替所有者选择上述方案，不降低core判据。项目collector选择、runtime/启动器改变的影响、秘密到达时点、后代与exec边界、规则恢复必须形成具体新绑定，并由H1/H4审阅。即便解决core，独立HTTP/刷新计数、实际隔离和供应商能力等其他前置仍分别成立；H2批准后才可H3执行，产品激活独立。

## 验证与证明范围

命令均为 `UV_CACHE_DIR=/tmp/issue167-core-uv uv run --offline --locked …`：

- `pytest -q tests/test_issue167_core.py`：9 passed，0.18s。2项真实无崩溃exec属性观察、6项畸形输出拒绝、1项未观察到重置仍不自证保护。
- `python scripts/issue167_core.py`：输出上表受控数值与 `pre_exec_protection_lost`，不输出进程环境、路径或秘密。
- 定向 `ruff check`、`ruff format --check`通过；`MYPYPATH=src … mypy scripts/issue167_core.py tests/test_issue167_core.py`：2 files通过。

固定探针只有自有prctl/exec/退出，不处理外部输入或等待外部对端，父进程不发送信号；它不是生产任务监护器。实测只否定pre-exec充分性，不证明真实Node/Pi执行、crash收集行为、实际core零写入、完整后代收束或任何上线许可。本轮未运行完整离线门禁。

本次只读本机压缩手册身份（不是新增产品依赖或冻结组材料）：

| 文件 | SHA-256 |
| --- | --- |
| `/usr/share/man/man2/execve.2.gz` | `03586c6523a6810bddeda7b60de7feb845cff745c20c0ca760f09779a33fdead` |
| `/usr/share/man/man2/PR_SET_DUMPABLE.2const.gz` | `c455f4118471404bb3dbaf76bcb6a1c0f9b8fdbbd99954a868efc0e2d562510e` |
| `/usr/share/man/man2/PR_GET_DUMPABLE.2const.gz` | `83372335faced58c9e073a49eba6397cfd3f72bfe3d9aa2db687ea9e9a092fe0` |
| `/usr/share/man/man5/core.5.gz` | `940afb6eddff0f80bea92b2468382eee55fd5da4f465f15932e49e97a5f1f7eb` |
