# B 无 prompt 模型映射探测独立工程覆盖

工作基线：`a09f7e8dec50da50be24e31675703a3a2ade2563`。本次仅实现 #191，
不新增 Alembic migration 或表；不运行完整离线门禁，不运行任何真实/live 行为，
不访问真实实验根或读取凭据。以下均为合成固定供给、合成认证/RPC 对端与 `/tmp` 材料的工程结果。

## D1 接缝与计数

| 独立模块 | 数量 | 公共观察 |
| --- | ---: | --- |
| `tests/test_stage_b_model_mapping.py` | 11 | CLI 中文冷帮助；两槽独立模型/档位成功且数据库逻辑事实不变；模型拒绝/缺档位；外发范围、严格证据、不可豁免隔离、错误安装根在认证前拒绝；临时根清理与删除故障；中断退出 130、安全文件日志 |
| `tests/test_model_mapping_rpc.py` | 10 | 公共 RPC 合成故障：超时、清理失败、模型拒绝、不匹配、缺档位、脏状态；畸形槽/版本/档位/provider 在会话创建前拒绝 |

总计 **21 例**，独立未绑定 D1，不改历史测试、fixture 或既有 required 分母。
`DELIVERED_EXECUTION_ENTRIES` 在本票 CLI 模块登记 `probe-models` 并核对真实文件日志汇。
接缝沿 #185 已确认规则：CLI 为主；公共 RPC 的合成字节对端用于故障注入。
所有者豁免及外发授权均经真实 CLI 记录，不 mock 内部门禁放行。
合成 helper 直接产生合成短期 token/元数据，不读取 auth 内容；真实固定供给保护、
Landlock、零 core、no_new_privs、管道与资源清理由产品路径执行。

CLI 对端断言精确模型、两槽各自档位、控制命令序列直到 `get_state`、没有 prompt/message，
并核对进程限制、隔离数据库读取拒绝、独立 agent 目录和无 session 旗标。
数据库前后逻辑库存相等；删除故障不返回 mapping_settable；临时目录最终均清除。
默认日志/错误不含模型名称、所有者原文理由、合成凭据或外部异常原文。

## Red → green

1. `probe-models --help` 首先因未注册命令退出 2；补中文副作用/退出码说明后通过。
2. 畸形槽/版本/档位先返回 transport_error（3 failed、1 passed）；补启动前精确类型
   校验后统一返回 invalid_description，且不创建会话。

认证 helper 是否运行/刷新、超时、整组回收和独占临时根规则先写入执行 Contract；
探测不借空 prompt 调用 `run_call`，不构造 StageInput、任务或业务 attempt。

## 本次验证

统一使用 `uv run --offline --locked`；缓存只用已有离线材料，无联网补包。

- 新增 D1、A8 protocol/lifecycle/preflight、Pi launch/service、owner-waiver、Read RPC、
  B 静态预检及 D7 冻结源码守卫组合：**311 passed、2 failed**（117.26s）。
  两个失败均是下述已知冻结源码字节漂移，不是功能拒绝/生成失败；不称该组合通过。
- `./scripts/check-compatibility cli`：**59 passed**（73.79s），退出 0。
  首次 TMPDIR 指向尚不存在的目录，pytest 回退默认临时位置并发出旧合成目录清理警告；
  没有手动删除历史目录。后续命令使用已存在的本票临时目录。
- 定向 Ruff、format --check、git diff --check 通过。
- 默认 follow-imports 的 `mypy --strict` 显式包含 6 个改动源文件与 4 个新增测试/支撑文件，
  共 **10 文件通过**；没有 ignore 或降低 strict。

相关 pytest 的精确模块为：
`test_model_mapping_rpc.py`、`test_stage_b_model_mapping.py`、`test_a8_rpc_protocol.py`、
`test_a8_rpc_lifecycle.py`、`test_a8_rpc_preflight.py`、`test_pi_execution_launch.py`、
`test_pi_execution_service.py`、`test_owner_live_waiver.py`、`test_read_execution_rpc.py`、
`test_live_admission_source_guard.py`、`test_stage_b_egress_preflight.py`。
测试使用 `--basetemp=/tmp/paperradar-191-pytest`。

## 漂移与下游责任

只读 scope 审计以本地 `integration/185-stage-b` 的上述基线为 base/target，退出 1：
本票 current_change 为 `src/paper_radar/llm/models.py`、`src/paper_radar/llm/rpc.py`
（A8/A9/A10）；基线已有 `backup/service.py`、`cli.py`、`storage/artifact_contract.py`、
`storage/schema.py` 的 source/support 漂移分别保留。未机械重绑。

D7 v25 冻结源码守卫另绑定本票改动的 `pi_execution/admission.py`、
`pi_execution/launcher.py`、`llm/models.py`、`llm/rpc.py`。失败节点为：

- `test_live_admission_source_guard.py::test_admission_sources_match_reviewed_policy_manifest`
- `test_live_admission_source_guard.py::test_source_edit_with_same_policy_fails_guard`

两者都先遇到 `pi_execution/admission.py` 的旧字节不符；旧清单、策略键、历史向量不改。
该守卫是开发期冻结保护，不参与产品运行时准入；#206 在最终代码树统一审阅并推进新策略/
新向量。B 所有者豁免路径不构建 LiveBundle，也不恢复可选证据链。

下游真实执行仅在另获授权后消费 `experiment probe-models`。结果只表示此次映射/状态可设置，
不证明认证实际刷新、订阅可生成、档位影响推理、采样/外部参数有效、生产 Pi/TLS/DNS、
现场隔离或任何 Read/Screening 业务成功，不保存为 verified/准入证据。
模型/档位不可用交所有者按 §7.8 裁决；完整 B 纵向链、来源与逐文档质量仍由各后续票负责。
