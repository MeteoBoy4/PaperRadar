# #150 外部审阅修复独立覆盖

本台账记录外部审阅后的新增 D1，不纳入 A1–A10 的 required、旧成员、分母或历史回执。
`stage_a_verified=false` 保持；处理依据逐项见
[r1 处理表](../../intent/review/issue-150-docling-extra-review-r1.md#本轮逐项核实与处置)及
[r2 处理表](../../intent/review/issue-150-docling-extra-review-r2.md#本轮逐项核实与处置)。

| 新增未绑定模块 | 节点数 | 公共边界与证明范围 |
| --- | ---: | --- |
| `tests/test_docling_review_regressions.py` | 15 | probe 与显式 smoke 的 4 个 ABI 拒绝、3 个普通 GIL 构建成功；冷进程哨兵拒绝 3 种无关 sidecar 写入并保留所选数据库 WAL 例外；帮助哨兵捕获 metadata/顶层 find_spec；settings/snapshot 两种 runtime CLI 只显示本范围结果。 |

ABI、无关 sidecar 与 CLI 输出先分别记录 4、3、2 个失败，再验证修复通过。
测试使用独立人工版本字面量和 stdlib/SDK 边界替换，不调用私有分类函数，也不从生产清单推导预期。
既有 smoke 10 节点、runtime 冷进程 26 节点的数量不变；更新其平台 fixture 和帮助/所选数据库哨兵输入。
其他既有 D1 的人工 cv2 库存改为锁定的 `4.14.0.94`，probe 仍只做 cv2 metadata/顶层发现，
不增加 extraction 语义版本。旧台账、fixture 和正式回执保留原字节。

本轮在 CPython 3.14.4 + extra + dev 环境运行上述模块、六个既有 Docling D1、doctor
冷进程和 extraction check/CLI/持久化/字段验证，共 **263 passed**；CLI 兼容组合
**59 passed**。触及的 8 个 Python 文件通过 Ruff、格式及严格 mypy 检查。
显式真实 SDK import smoke 退出 0，库存 85 包；模型加载与 PDF 解析为 `not_assessed`。
三 minor 的本轮 ABI 行为使用受控事实覆盖，未重新执行三解释器实装矩阵。

基线为本地 `integration/issue-150-docling-extra` 的
`bc8ab83f2a78510129d55a11b37cc8d6120103d0`。只读 scope 审计无 baseline/hash drift，
本轮未改旧绑定源码或敏感登记，不重绑、不扩张历史固定分母。
`--collect` 审计退出 0，保持 1214 成员、289 计数记录、285 个固定模块；无 issues。
这些开发检查不代表当前新树通过完整门禁；本轮未运行完整 `check-offline`，
历史通过结论仍仅适用于其原冻结身份。模型、PDF 转换、四刊/中文 fixture、质量、资源、
Read/reuse、Pi live、正式校准与 NAS 均未验证。
