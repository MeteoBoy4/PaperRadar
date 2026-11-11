# #184 最终源码测试 fixture：独立工程覆盖

本台账记录最终 current-source 测试接线维护，不发布 Live 资格或扩大任何历史组分母。
生产源码、旧 v1–v16 源码向量及 pins、receipt v1/v2 和旧 Schema 均不在本次修改范围。

## 输入与保护边界

- epoch fixture 直接使用当前完整源码，不再 clone／checkout 历史 Git 对象。两代包均经过真实源码守卫、完整 Python／项目源码冻结、离线 cc 和 compile-only AppArmor parser。
- 为获得不同 collector 和七计划 ID，首代解释器使用同一真实 ELF 追加非加载尾部数据的合法 OS 输入副本；次代使用原解释器。独立节点实际执行该副本验证可运行。两代保持原 site、model、supply、owner 全对象和窗口，placement 完整身份相同。
- `real_freeze=True` 显式恢复真实 freezer，避免前一次轻量 OS fixture 残留。其他宿主模型仅替代有限 OS 行为；真实源码、guard、kernel 策略检查、lifecycle 和 epoch 接口不被替换。
- 原 v1 epoch AST 预期使用独立固定声明 literal；篡改源码负例只复制实际 guard 成员，不复制整仓库、环境或历史归档。当前 guard 负例输入显式采用 v17，旧向量不换字节。
- resources／nft 多代续接沿用原 site，使测试命中原恢复行为。新工具集合保留旧五项并显式增加 `apparmor_parser`、`true`、`systemd-run`，仍为精确集合。
- AppArmor installer 测试使用实际编译 policy，移除后附合成 policy／重封印步骤。未知策略拒绝前，原部署与 policy journal 字节均须保持。

## 独立 D1 节点

`tests/test_final_placement_fixtures.py`：**12 项**，不加入旧 scope 固定分母。

| 节点 | 数量 | 验证边界 |
| --- | ---: | --- |
| 合法 OS freezer 输入实际可执行 | 1 | 同一 Python ELF 的非加载尾部差异仍可执行 |
| 轻量 fixture 后恢复完整真实 freezer | 1 | 原解释器字节、七个新增源成员、两个静态 native ELF、相同 placement 身份及不同 collector |
| 新工具路径／SHA 篡改拒绝 | 6 | 三工具各两种篡改，真实 host preflight 在任何命令执行前拒绝 |
| 无 placement feature 历史 metadata layout | 4 | 无 source identity 及 format 1／2／3，仅合成历史 metadata，不声称旧可执行源码 |

原 epoch 42 项、AppArmor lifecycle 44 项、seal CLI 10 项节点全部保留。原 canceled／stopped／intent／额度／回执／归档／七窗口／未知字段及失败断言不删除、不 skip、不 deselect。

## 开发验证与承接

- current-source 初步 epoch 组合：42 passed，147.92 秒；随后进一步加强为双代完整真实 freezer。
- 双代完整真实 freezer 最终组合：新增 D1 12 项、epoch 42 项、原 bundle lifecycle 18 项，合计 **72 passed，286.61 秒**；无 skip／deselect。
- 十模块消费者组合（bundle、lifecycle、host、resources、nft recovery、AppArmor、seal CLI、contract Schema、evidence contract、receipt）：162 passed，1 failed，204.79 秒。唯一失败是原 `test_filesystem_interruptions_resume_without_rewriting_known_history[history_published]`，生产 resources 分支在合法同字节 history 已存在时重复发布而触发 `FileExistsError`。原节点保持失败，不在测试中绕过；生产修复与新源码守卫由后续独立修复承接。
- 八个受影响测试／支撑模块 Ruff check、Ruff format check 通过；连同四个受测源码入口的 mypy 共 12 模块通过。`git diff --check` 通过。

最终集成树的全部相关组合与兼容检查由父任务在生产修复后统一运行；上述开发结果不替代该最终树结论。
未运行完整离线门禁、真实 profile load／remove、namespace／scope、网络、认证、模型、receive、激活或实际 root 现场操作。
