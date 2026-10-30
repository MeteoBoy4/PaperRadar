# Pi 固定供给 Contract 迁出历史

## 来源与证明限制

下列原文存在于基线 `2ad8f354e8d2497719b22eb1a543223d4c8d98aa` 的
`docs/contracts/pi-supply.md`；这里只冻结既有材料与验收叙述，不记录本轮验收，
不推定其最初撰写日期。原文中的“本次”、产物数量与验收结论均属于原叙述的历史范围，
不是当前运行结论；“六份主要文件／第七份”不描述后来扩展的完整离线入口。

Pi 1.3.0 fixture 派生锁向量只约束该固定材料的派生结果，不证明真实安装、RPC 或模型兼容。
历史范围与逐条依据继续由[离线证据](offline-evidence.md)、[A4 归属表](a4-requirements.md)
维护；现状公共边界见[Pi 固定供给 Contract](../contracts/pi-supply.md)。
不从本页推断当前工程通过、Pi 1.4.0 生产就绪、现场隔离、正式校准或 live 通过。

## Pi 1.3.0 fixture 派生锁原文

真实 Pi 1.3.0 fixture 的派生锁 SHA-256 固定为
`a342ed1baea205543bdcaf82ec4aed2bfc771a5c2c47b2bacb8238d06513e7c6`。

## A4 离线验收边界

唯一 `./scripts/check-offline` 追加必需 `.a4.json`，与基础证据、A1、A2-01、完整 A2、A3
组成六份主要文件，pytest 回执另存第七份。A4 独立绑定本次三份必需前置、执行回执、
固定材料/源码/测试、真实迁移与生产格式、环境及代码身份。十项生命周期 capabilities
全部通过才完整通过，不从机制 spike 或退出零推断覆盖。live_install/RPC/完整阶段 A、
真实来源/NAS/自动精读恒未验收；真实 install_check 仍只能查询用户库本次 prepare 记录。
细则见 [离线证据](offline-evidence.md)；
正文、各轮裁决和补充的责任见 [逐条归属](a4-requirements.md)。
