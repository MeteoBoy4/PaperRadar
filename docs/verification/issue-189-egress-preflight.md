# B 外发授权与静态预检独立工程覆盖

本台账只记录 #189 的离线工程边界，不构成真实模型、来源、Docling 或现场隔离验收。
工作基线为 `1d23cfb`；不新增 Alembic migration，复用既有 config_versions 追加链。

## D1 接缝与计数

独立模块 `tests/test_stage_b_egress_preflight.py` 共 **35 例**，不修改历史冻结测试／fixture：

| 范围 | 数量 | 公共观察 |
| --- | ---: | --- |
| 所有者授权启用／撤销与范围拒绝 | 2 | 真实 CLI 登记、查询、缺失、换阶段、换模型与复制根拒绝 |
| 授权链损坏 | 6 | hash、format、version、previous、kind、reason 故障注入后，CLI 查询／核对／追加均封闭拒绝 |
| 调用范围故障注入 | 4 | Connection 短事务内复核阶段、provider、缺类别、额外类别；不写业务事实 |
| 冷进程帮助 | 4 | 授权写／查／核对与 preflight 中文帮助，socket/SQLite 拒绝守卫，无目录写入 |
| 静态预检完整汇总 | 2 | 缺供给等全部项同时披露；完整替身下必要项通过、豁免未验状态保留 |
| 静态缺项 | 14 | cwd、凭据缺失／权限、隔离、豁免损坏、外发缺失、内存、cgroup、peak、磁盘、部署、attempt／凭据／安装根 |
| Read 自身选择 | 1 | Screening 通过不能使 Read 独有的不支持 provider 通过 |
| 恢复副本与并发 | 2 | 移动后历史链可查而执行拒绝；并发所有者动作形成连续版本链 |

接缝遵守 #185 已确认的 CLI 主、服务只用于故障／并发原则。授权与豁免均由真实 CLI
记录；供给用既有合成 Download/Run 生产形状材料，主机事实指向临时 meminfo/cgroup。
预检期间守卫 Popen/socket 与 auth.json 内容读取；元数据只使用测试假目录。
文件库存与逻辑数据库前后相同；日志只由授权写入口生成且不含理由、根路径或载荷。

## Red → green

1. 首个所有者登记测试先在 `egress-status` 未注册处失败；实现版本化授权链与 CLI 后通过。
2. 范围复核测试先在 `egress-check` 未注册处失败；实现只读认证／领取前核对后通过。
3. 汇总测试先在 `preflight` 未注册处失败；接线两槽独立检查与资源事实后通过。

## 验证与边界

开发验证使用 `uv run --offline --locked`，未运行完整离线门禁。
独立 D1、doctor pi-exec、owner-waiver、日志 vocabulary 与实验 Feed 的相关组合，以及
`./scripts/check-compatibility cli` 作为本票消费者兼容验证。本次相关组合 **168 passed**（53.69s），CLI 兼容组合 **59 passed**（78.91s），
Ruff/格式/mypy 与 diff 检查通过；本台账不把某次历史结果提升为新提交的正式门禁。

现有严格豁免恢复测试在默认沙箱内的合成 placement 握手被阻断；同一单项在获准的
沙箱外离线环境通过。这不构成真实 placement 现场结论。

主机可用内存下限仍待所有者裁决。生产缺省以 `host_memory_policy_unset/not_assessed`
阻断；测试注入下限只覆盖分支，不形成产品政策。非必要 memory.peak 不可读仍为 unknown，
不使其它静态检查伪失败或将 worker ru_maxrss 混为同一口径。

只读 scope 审计以 `1d23cfb`/`integration/185-stage-b` 为显式基线，退出 1；
唯一已登记变化为基线已有 `src/paper_radar/cli.py` 的 source/support 漂移，未机械重绑。
新增 D1 模块独立登记于本台账，未进入历史 required 分母。

合入 #188 的 `41ea0e7` 后，在合并提交 `99294d8` 的代码树上复验：
相关组合 **186 passed**（89.17s），CLI 兼容 **59 passed**（78.03s），
定向 Ruff/格式与 mypy 通过。共享 CLI 保留 candidates 与授权/预检全部命令；
README 和工作流 Contract 按双方最终语义合并。
合并后 scope 审计以 `41ea0e7` 为 base，退出 1，另保留 #188 已有
`src/paper_radar/storage/artifact_contract.py` source/support 漂移（A3/A7/A9/A10）；
连同 CLI 基线漂移交 B 集成收口，不重绑历史材料。

下游 #190 接 B 聚合验证时调用 `egress_authorization` 的纯链检查，不能按恢复路径重新
解释历史；#192/#198 在认证前与领取短事务内调用 `require_egress_authorization`，两阶段
之间重新读取。#191 承接无 prompt 映射探测；#196 承接实际提取时 cgroup ≤8 GiB/swap=0
与双口径峰值记录。全部真实调用、认证刷新、合法材料、模型／Docling、现场隔离未验。
