# Live 统一审阅修复覆盖

本台账独立登记 #177 统一 Standards/Spec 审阅的四项修复，不改写 #178–#184 的历史交付台账、失败记录、回执或固定分母。实施起点为本地 `integration/issue-177-live` 的 `2ed0d86ecff7345eff118f98a3b505e485fa488e`，没有执行现场操作。

## 修复与公共接缝

| 审阅项 | 修复行为 | 独立验证接缝 |
| --- | --- | --- |
| Spec P1：临时 metadata 错误误撤销 | 普通 I/O 与完整 stat 采样不稳定只拒当次，保留上一快照及时间、原证据与业务预算；确认的非法成员/链接/权限与实际绑定漂移仍持久收紧。诊断保留当前调用的纯身份，避免用 low 站点上下文误撤销 high 模型证据 | 正式 Screening/Read `run_attempt`、共享诊断/guard、`refresh_once`、`collect_models_once` |
| Spec P1：材料快照误成为执行身份 | 例行 `metadata_only` 接受同供给/安装的最新有效材料快照；首次 β、collector 的 `require_snapshot=True` 与构建器最新 activation 三元组继续严格核验 | `activate_supply` → `observe_site`、正式绑定请求/guard、collector 入口 |
| Spec P2：负对照完成后发布中断 | 负对照复用既有先写 publication intent、完成落账、发布 inbox、清 intent 顺序；重开只恢复已完成原字节，不重复网络、不刷新原时间；已逻辑发布来源丢失继续拒绝 | `collect_models_once` 中断/重开与 `ProtectedCollection` 公开历史/预算读取 |
| Standards P2：安全负例只断言异常类型 | runtime/nft/unit 逐参数固定原因；缺文件固定 `ENOENT` 和具体 filename；库存 extra 明确使用 0644，确保触达库存分支；保留健康 tracer、未知文件与宿主调用断言 | 原 `test_live_bundle_lifecycle.py` / `test_live_bundle_host.py` 公共安装与核验入口 |

例行 metadata 子进程只传受控 `observation_unavailable` / `binding_observation_unavailable`，不传异常正文或秘密。首次 β 的严格失败语义、v1 baseline 算法字节、v1/v2 wire、有效 v2 不变量摘要均保持。没有修改表或 migration。

## 新增 D1 模块

| 独立未绑定模块 | 完整节点数 | 范围 |
| --- | ---: | --- |
| `tests/test_live_review_metadata.py` | 20 | 两正式消费者 open/lstat 临时故障与诊断；并发采样；同安装材料演进；真实执行选择/策略/模型漂移；非法 cache/链接/成员/根及子目录权限；root 临时/安全恢复；low/high 上下文和混合真实策略漂移 |
| `tests/test_live_review_collector_metadata.py` | 1 | collector 严格封印上下文，临时观察拒绝不预占、不生成失败轮，后续正常续跑 |
| `tests/test_live_review_publication.py` | 2 | 四负对照发布中断恢复与真正丢失已发布来源拒绝，原时间/字节/预算保留 |
| `tests/test_live_review_policy.py` | 2 | 独立 v11 摘要锚/实际源码与原 v10 字节 |
| 合计 | 25 | 不进入任何旧验收组回执或固定分母 |

新测试以合成凭据、安装、账本与 OS/RPC 替代边界运行；不读取真实凭据或用户 cache。不将树外一次性 probe 脚本搬入测试。

## 既有测试维护

`test_auth_cache_stat_v2.py` 的并发采样负例固定为 `observation_unavailable`，仍拒绝采样，不减少成员/字段检查。`test_live_admission_source_guard.py` 切到 v11 并追加 v10 归档参数，v1–v10 JSON 及原摘要锚不变；`test_live_bundle.py` 的错误源码向量负例同步指向 v11。

全仓 mypy 预检的 53 项原失败按实际 fixture 类型、不同消费者分支变量和标准库回调接口修正，涉及 `test_auth_helper_resources.py`、`test_pi_placement.py`、`test_observation_refresh.py`。没有新增粗放 `Any` / `type: ignore`、修改生产启动行为或删减负例。`test_pi_execution_launch.py` 只修原 Ruff 格式失败。

旧 freshness 组合暴露四个仍期待 `collect`/120s 的过期用例：现固定实际零参数 `sudo -n -- live-evidence-refresh`/30s，并让成功 OS fixture 真实发布受保护新快照；失败仍固定临时拒绝。原四个参数及分母保留。该维护不声称生产临时 helper 成功或独立刷新事件已被现场证明。

## 策略与固定范围

本轮受保护行为使用 `pi-admission-v11`；启动策略仍为 `pi-launch-1.4.0-v8`，没有实际 launch 行为改变。v11 新增独立源码向量及摘要锚；v1–v10 的 JSON、既有原锚、历史回执和归档不重绑。
新向量 SHA-256 为 `b3209a6f797248e9db7d2a4469e62bb31b5aa6d1cfeb82ff320ee6a866987da7`。

只读 scope 审计保持 `exit_code=0`、零 issues、289 条固定计数登记。本轮修改路径均不属于旧 scope 的材料清单，因此直接/下游旧组为空，无旧组哈希重绑；相关普通源码旧/新 SHA 另交最终集成审阅。本台账及四个新模块属于独立 D1。

## 开发验证与边界

验证结果由本轮实测登记；开发组合不代替最终冻结树的完整离线门禁。没有运行 `scripts/check-offline`。

| 开发验证 | 结果 |
| --- | --- |
| 首次 22 模块受影响组合 | 339 passed / 6 failed；清理回调和 placement 分支类型维护暴露 2 项 fixture 问题，旧 freshness 入口/时长 fixture 暴露 4 项；均保留参数并修正 |
| 上述 3 个失败模块修后 | 53 passed |
| 扩展 25 模块组合（含 doctor、loader、准入兼容） | 375 passed；随后仅追加权限 errno 分类纵切 |
| 最后权限分类及 scanner、正式两消费者、root 刷新、策略锚、文档链接组合 | 197 passed；含本轮全部 25 项 D1 |
| placement 标准库 `onexc` 回调维护补验 | 1 passed |
| `check-compatibility all` | 176 passed，退出 0；入口总耗时 331.80s |
| 全仓 `mypy` | 1124 source files 无错误 |
| 全仓 `ruff check` / `ruff format --check` | 全部通过，1579 files already formatted |
| scope 审计 `--collect` | 退出 0，零 issues，289 条固定登记；285 个去重模块收集 reason=ok，skip/deselect 均 0；不执行这些测试 |

前述临时 EIO、并发 stat、负对照发布中断、low/high 诊断及子目录实际权限异常均有修前 red 复现；没有以异常类型、仅文件保留或无宿主调用冒充拒绝分支的证明。交付前合并最新本地 integration，结果 `Already up to date`。

没有运行 root/live、真实网络、auth、模型、receive/activation、现场恢复或私有 build。自然到期/真实刷新仍为 unknown，用户两项 async 裁决仍待回复；本轮没有新增持密认证入口或改变验收含义。
