# #177 正常认证刷新接缝：独立 D1 工程台账

本台账只覆盖所有者新批准的产品持密认证接缝与正常提前刷新定义（[裁决](https://github.com/MeteoBoy4/PaperRadar/issues/177#issuecomment-6784720735)、[ADR-0063](../adr/0063-observe-normal-oauth-refresh-in-product-process.md)）。不重写既有 #178–#183、gate2、scope 或现场证据，不扩历史分母。

| 公开接缝 | 本轮合成覆盖 | 限制 |
| --- | --- | --- |
| `prepare_launch`／严格认证元数据解析 | 额外字段、类型、来源、pid、时序拒绝；部分提交未知；旧wire不能省略版本升级；实际本地放置握手转交独立 metadata FD、同 pid 绑定与 token 不进入元数据 | Python 假 Pi 对端，非真实订阅 |
| 固定 1.4.0 公开 `ModelRuntime` + JS `resolveAuth` | fresh、正常阈值、Pi 阈值到期、锁内竞争跳过、refresh 失败、persist 失败、短有效期后置拒绝、toAuth 失败、取消后底层继续的9场景；非 OAuth 在 resolver 前拒绝 | 全部 CredentialStore／refresh／I/O 为合成；不推定供应商行为 |
| JS 实际固定 executable entry | 原具体默认文件 store 读取临时合成 OAuth 文件、原 toAuth、独立 stdout／metadata FD、额外 argv 拒绝 | 合成足够长的有效期确保零刷新／零网络；未读私人凭据 |
| `collect_models_once`／受保护正常评审 | 三批返回；A/B/C 成功与两个不同刷新提交；B 或 C 缺事件持久 unknown 停止；再次调用不花费、不补跑；旧 manifest v1 六格续跑保留 | 替换 OS/RPC 边界，非现场资格 |
| 独立部署 epoch 与目标披露 | 首次时点固定、重复初始化不续期、完成或未完成预占后来源丢失不补造；72h逾期不擅自变准入停止条件 | 实际部署／恢复时点由 Live 验收 |
| 新封印 builder／源码守卫 | launch v9、admission v13、独立 v13 向量／锚；冻结 JS、Python、metadata／normal review 与 source identity v3；旧 v1–v12 向量原字节及旧 receipt 格式保留 | 只离线合成包测试；最终真实候选由集成执行者冻结后另 build |

新增 Python D1 模块为 `tests/test_auth_refresh_metadata.py`（4项）、`tests/test_normal_auth_refresh.py`（6项）；Node harness 为 `tests/auth_refresh_harness.mjs`，显式固定 Node／package 路径运行，不查 PATH／个人安装，不是 pytest skip。既有启动、放置、collector、builder、部署生命周期、历史源码锚及相关兼容组合由本轮相关回归覆盖；最终准确命令、数量与退出状态保留在实施交接报告，不以本台账替代最终树门禁。

固定 API 依据为项目已供给 Pi 1.4.0 `docs/docs.json` 完整导航下的 SDK、credentials example、providers、CLI、security、custom-provider、environment 及其公开 `.d.ts`／实际实现。只有 `ModelRuntime` 根导出与其公开实例方法参与调用；静态摘要只读取固定源码，绝不计算 credential／token 派生摘要。泛型 store 注释不作为具体文件 backend 的异常传播证明。

未执行 live：新字节 sudo 审阅／部署、真实 OAuth refresh／供应商有效期、网络与 kernel 现场、三批闭环、receive／逐格激活／正式只读采样。供应商真实到期、隐藏请求、完整会话写史、认证全写史／writer 保持原 unknown／not_assessed。六格、40/40累计域、失败／stopped／恢复、三检查点与清理责任不减；完整离线门禁由唯一集成执行者在最终冻结树按授权运行。
