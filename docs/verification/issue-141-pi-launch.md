# Issue #141：Pi 受控启动与资源隔离

依据 [#141](https://github.com/MeteoBoy4/PaperRadar/issues/141) 与父票最终 C/D 确认。
实施基线 HEAD 与 integration 初始 tip 均为 `e0f8e39d1aff8b57eadfe60de44b8570423c1d40`，
工作分支 `feat/issue-141-pi-launch`，初始 dirty=false。
本台账只证明启动资源工程切片，不扩大 A4/A7/A8 的历史分母或任何 live 结论。

## 独立 D1 分母

测试 seam 是规格已确认的公共 `prepare_launch`/`SessionFactory`/`ByteSession` 与必要下层纯检查、真实 OS 权限拒绝。
合成固定供给中的 Node/Pi 入口实际上是复制的 Python 可执行文件与标准库对端；同一对端支持 host auth 和 RPC 两种形状。
Python 标准库运行路径仅由测试私有扩展到白名单，产品策略不开放 Python 运行树。
对端 env/argv 观察走测试 stdout，未增加产品转储或 token 注入接口。

| 未绑定模块 | 用例数 | 可观察范围 |
| --- | ---: | --- |
| `tests/test_pi_execution_resources.py` | 15 | 空 cwd/链接/污染、精确系统文本与路径形状、含 NUL 的单 argv UTF-8 字节上限、owner 0700 凭据元数据与业务根隔离、代理拒绝 |
| `tests/test_pi_execution_launch.py` | 18 | 真实 auth/RPC 双形状、完整 snapshot ID、固定 argv、精确 env、保护 fd、no_new_privs、独立资源与 settings、token/cmdline/DB/repr 隔离、auth 形状/失败/超时、代理、cwd/树变化、exec 失败、清理失败、两条进程边界接管失败的组回收、激活切换仍用在途入口 |
| `tests/test_pi_execution_isolation.py` | 3 | 本机最低能力、白名单读取与 DB/安装/cwd 拒绝、TCP 代理端口允许与无关端口/bind 拒绝、低 ABI 安全失败 |
| 合计 | 36 | 无 skip/deselect/incomplete 的最终子集 |

`tests/pi_execution_support.py` 是新增支撑，不计用例。
本机能力原型于 2026-11-01 观测 Linux x86_64、uid 1000、Landlock ABI 8；在真实 fork 子进程设置 no_new_privs 后，允许白名单读取，拒绝私有读取和只读树写入。
正式新增用例继续使用真实本机标准库子进程观测拒绝，能力不足时失败，不 skip。
沙箱组合用例额外拒绝业务 DB/blob、出版方哨兵、个人 Pi 哨兵和宿主 refresh 凭据目录；只尝试打开哨兵，不读取真实秘密。

## 验证

命令统一使用 `uv run --offline --locked`，uv 离线缓存锁和新工作树环境同步已按授权提升文件权限运行；没有联网补依赖。
TDD 首轮先观察缺包/API、argv/代理规则与完整 snapshot ID 的红灯，然后补实现；不以红灯或开发期 deselect 记通过。

最终新增子集：三个模块 **36 passed**。
相关回归追加既有 `test_pi_supply_protection.py`、`test_a8_rpc_pipes.py`、`test_a8_rpc_lifecycle.py`，历史 102 项保持通过。
CLI 兼容组合 `./scripts/check-compatibility cli`：实际选择 8 模块、59 节点，**59 passed**，退出 0（入口总耗时 62.28 秒）。
Ruff 检查/格式与 mypy 覆盖新增 7 个生产文件及 4 个测试/支撑文件。
最终合并树的实际命令/数量由任务报告附上；本台账不冒充完整离线门禁回执。

## 处置与漂移

新增 `pi_execution` 只负责固定安装使用保护、只读资源检查、宿主专用 auth、隔离会话与 attempt 回收。
不改 config、screening_tasks、物理表、migration、A8 内核、冻结测试/支撑或 required 计数。
独立契约与 ADR-0039 记录资源和主机级出站缺口；原 ADR-0037/0038 已占用，因此采用 0039，未覆盖历史 ADR。
README/GLOSSARY 只补受影响能力和词汇。新包/测试/ADR/台账没有逐子票机械加入历史 scope。
按稳定 main 基线的只读审计，在本票合并其他子票之前，`affected_groups=[]`、issues 为空；
新的 D1 成员和合并后源代码漂移交 S4 统一核对与必要登记，不能把旧哈希或其他工作树证据移用。

## 仍未验证的行为

没有运行真实 Pi、真实 auth 刷新、供应商调用或现场 `/srv/pi-cwd` 验收。
当前产品没有 Cwd/Live passed 来源；S3 必须先做证据门禁，真实执行保持领取前阻断。
本机 Landlock 结果不等于部署权限证据；真实 TLS/DNS 白名单充分性、订阅模型可用性、
OAuth 前缀启发式、min-expiry 行为、自动 retry/预热抑制、RPC 兼容与所有 DERIVED 仍归 Cwd/Live/EXP-2。
TCP 仅按端口约束，不能按主机限制；UDP/DNS 不受其 TCP 规则约束。
正常生产用途、采样/校准语义与任务成功接收不由本票授予。
未运行完整离线门禁，不声称阶段 A、Pi 模块整体或生产运行验收完成。
