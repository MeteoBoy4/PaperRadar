# Live-04 例行受保护观察刷新：独立 D1 覆盖

本台账只登记离线工程行为，不进入历史固定分母，不生成产品证据或现场 passed。需求依据为
[#177 最终裁决 E-4/E-7/S-1/S-10/S-11](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6768256547)
及 [#181 候选发布澄清](https://github.com/MeteoBoy4/PaperRadar/issues/181#issuecomment-6768786581)。

## 独立范围

| 模块 | 节点数 | 公共接缝与覆盖 |
| --- | ---: | --- |
| `tests/test_observation_refresh.py` | 31 | root 固定刷新、候选发布/保留、实际 nft/cgroup/封印成员、60秒边界与重启、临时失败、规则/目标/来源失信、待撤销及冷进程、共享内核锁、low/high 逐格原证据、正式调用无副作用拒绝、doctor 只读原时点、轻量元数据不执行完整 β/Node、v6/v7 原字节 |

测试只使用临时 ledger/安装/业务库、普通本地 RPC 对端和 Linux I/O 替身，不读取实际凭据内容，
不运行 root 部署、认证、模型、网络或现场 nft 操作。新模块不扩大旧 D1/D7 或任何 A1–A10 分母。
`CurrentObservation` v1、回执 v1/v2、既有受保护表及业务 migration 均未改格式。

## 验证记录

- 新增行为先以缺模块、缺投影参数等受控 red 失败，随后逐段 green。
- 独立模块、当前源码守卫及旧只读 stale 受控原因维护的阶段性定向组合：39 passed。
- 最后补充同一快照与刷新状态的发布竞态、健康 doctor 时点/结果披露；一致性测试保留完整投影
  相等断言，在独立预期中明确加入原夹具观察，不忽略新增诊断字段。最终同树直接影响组合
  （独立模块、旧观察、放置、消费者一致性、当前源码守卫）：83 passed。
- 16 个直接相关模块首轮：328 passed，1 项旧测试的 stale 原因仍预期 ledger_untrusted；
  改为 observation_stale 后，包含该参数化用例的定向组合全部通过。安全拒绝、无 qualified、
  原事实及只读断言保留，没有把 unknown 或缺证据改为成功。
- 同一离线工程支撑的 Pi/Read/RPC/放置组合：140 passed。固定刷新系统调用边界仅在私有测试
  支撑替换；默认拒绝实际特权请求，显式工程正例继续穿过实际放置与 RPC 权威接收。已先验证
  工程成功用例因缺替身而 red，避免把提前拒绝误当成原有负例通过。
- 同一工程支撑的其余四个直接调用方：61 passed。
- `./scripts/check-compatibility all`：176 passed，退出 0；后续 CLI 组合复验59 passed。
  这些是开发期间的兼容组合，不是最终冻结树完整离线门禁。
- 触及的13个生产模块 mypy、触及代码/测试的 Ruff、格式与 `git diff --check` 通过。

源代码策略为 `pi-admission-v8`；启动 argv/env 未改变，launch 保持 v7。独立
[源码向量 v8](../../tests/fixtures/live-admission-source-guard-v8.json) SHA256 为
`ab3beeacbda934f3389639ce220cfd84bfcc6826bb9999eae2e1241a8877316c`。
旧 v1–v7 向量原字节保留。ADR-0061 为 Proposed，不替代现场验收或所有者授权。

## 尚未证明的 live 行为

固定 helper/wrapper/sudoers、封印成员与实际 target/nft/resolver 的安装由封印升级包负责；
真实 systemd manager/锚定、cgroup、nft 故障注入、只追加属性和 helper 失败持久性仍须在审阅
封印字节后由 Live 现场流程验证。未执行 receive、证据激活、正式任务派发或完整离线门禁。
