# #167 续办：可行性反证、持久预算与安装锁传递

本轮承接[前轮AFK台账](issue-167-afk.md)，基线仍为 `c0bee235f4ebb0a88be4a60c392c96619ec61683`；开始时保留前轮所有未提交修改。GitHub重读仅有前轮回帖，无新增H1/H2授权；原生blockedBy为已关闭#140（1/1），subIssues为0/0。由主代理及两个fresh subagent执行本轮离线工作；不以“继续推进”推定已批准改变启动/供给、宿主配置、认证/模型请求或激活。

## 本轮新事实与产物

| 项 | 实际结果 | 限制/下一责任 |
| --- | --- | --- |
| A4 core | [无崩溃实测](issue-167-core-feasibility.md)证明pre-exec dumpable=0经普通exec变为1；no_new_privs不防重置 | 旧候选充分性被否定，活部署计划已修正。不得用LimitCORE/CoredumpFilter补猜通过；H4选择替代 |
| A4 本机collector | [Apport只读核查](issue-167-apport-review.md)：现handler在ignore判定之前add_proc_info，非package等分支亦可能走其他core路径 | 当前ignore列表不能证明秘密全生命周期安全；没有运行handler/制造崩溃/读crash文件，H4决定新方向 |
| A3 现成事件源 | [首批client补查](issue-167-client-observation.md)：默认fetch路径、SDK retry/logger、响应回调和宿主refresh分别核对 | onResponse漏响应前失败；debug含详情且不覆盖refresh；没有可直接安全启用的完整计数输出。最小loader仍需H4，真实次数unknown |
| A6 持久预算 | [预算原型](issue-167-budget.md)：预占上限/稳定case ID、重启或换run不返还、未知/超限/清理缺失持久blocked | 合成数据库/计数声明，未接H2、真实观察或产品。无抗恶意删除/快照回滚证明，不创建真实现场余额 |
| A4 原锁OFD | [匿名IPC原型](issue-167-fd-handoff.md)：SCM_RIGHTS共享偏移、接收后代持锁、重open不等价、ACK失败/缺失清理 | 仅固定合成进程，fork路径通过；exec后socket包装曾被沙箱EPERM拒绝，失败保留。未证明systemd/跨uid/token桥/任意后代回收 |
| A4/A6 方案审阅 | [具体剩余选择](../../intent/review/issue-167/remaining-decisions.md)：跨unit锁、同uid内存、manager属性泄密、core、计数与部署身份的阻断矩阵 | T1/T2/观测与core需新取舍；已有Q1–Q10不重复询问，不把选择材料称部署通过 |

已修正活部署候选，不更改前轮verification证据原字节；公共Contract、规格、现有产品行为与固定历史登记不变。Live仍待探索，B仍等待完整Live。

## 开发验证

命令统一 `UV_CACHE_DIR=/tmp/issue167-observation-uv uv run --offline --locked …`。

- `pytest -q tests/test_issue167_materials.py tests/test_issue167_lifecycle.py tests/test_issue167_observation.py tests/test_issue167_budget.py tests/test_issue167_core.py tests/test_issue167_fd_handoff.py`：76 passed，模块分别2/29/21/10/9/5项。新模块独立未绑定，不进入旧分母/组回执。
- `ruff check`、`ruff format --check`：12个Python文件通过；`MYPYPATH=src … mypy scripts/issue167_*.py tests/test_issue167_*.py`：12 source files通过。
- 预算独立审阅发现非法计划seal异常会回滚阻断，新增回归先失败，再修复为持久blocked；恢复计划或重开数据库仍拒绝。该原型的受信输入边界与持久化限制保留。
- 显式base/target的只读固定范围审计（含collect）退出0，issues/affected_groups为空；未重绑旧哈希、未改required、skip/deselect均0。完整离线门禁未获明确指令，未运行。
- 新增文档本地链接与 `git diff --check` 通过。没有公共CLI/包导入链/验收组接线变化，不触发兼容组合。

## HITL 具体边界

本轮没有运行Node/Pi、认证CLI或外部网络，没有读取认证/token派生值/现有core，没有提权或改宿主策略；core探针也未制造崩溃。匿名Unix IPC仅为合成进程本地fd传递。

core的最小新取舍是：项目定向前置分发器（会触及core_pattern分发链，必须评估非项目透明转发和新增失败面）或新运行时/秘密延迟到达机制，亦可继续阻断。请求观测的最小新取舍是安装树外独立观察代码与新启动策略身份，或继续原方式unknown。均已提交H4选择，**未获具体裁决前不实现/注入相应新策略**。

H1仍需最终路径化配置/代码与恢复审阅且root由所有者执行；H2仍需适用隔离通过后的逐批材料/端点/认证/预算批准；H3才执行获授权现场；H5审阅与产品显式激活分开。票保持open，不以移交代替完成。
