# #208 审阅修复与 #207 串行集成

本台账追加独立开发覆盖，保留[首次交付台账](issue-208-local-checks.md)原字节；
不扩大历史分母、required 集合或正式回执证明范围。

## 审阅修复与 D1

Standards P3：CLI 参数错误现在区分未知选项/多余参数、非法 action 和
`install/uninstall --staged`，给出受控中文原因与 `--help` 下一步。

Spec P2：`checkout-index` 会执行本地 smudge，将坏 index 改成好内容而误通过。
改为通过 `ls-files --stage -z` 取得条目、`cat-file --batch` 批量读取原始 blob，
禁用 replace refs；不应用 smudge/换行/编码转换，不读取工作树补齐。
普通/可执行文件保留模式；支持仓库既有的内部符号链接，延迟到普通文件写完后创建，
逐条拒绝树外/成环链接；submodule、未合并条目及非 UTF-8 路径受控拒绝。
另通过红测确认 intent-to-add 的空 blob 可能误满足本次未提交的文档目标，
现在受控拒绝，提示完整暂存或撤销意图。临时 Git 测试均隔离 HOME、系统/全局配置和签名。

| 独立 D1 模块 | 初交节点 | 本次新增 | 当前节点 |
| --- | ---: | ---: | ---: |
| `tests/test_local_document_links.py` | 7 | 0 | 7 |
| `tests/test_check_local.py` | 6 | 12 | 18 |
| `tests/test_local_hooks.py` | 4 | 0 | 4 |

新增节点覆盖三类 CLI 参数、smudge 误放行、可执行模式、五类拒绝、intent-to-add 和内部符号链接。
本票相关子集包含当前 29 个 D1 节点、旧 links 4 项和 inventory 4 项；
旧 `tests/test_live_document_links.py` 文件字节和四项断言保持。

## 串行集成与精确重绑

修复提交为 `755322a`，随后合并 `integration/207-208` 的
`c1ad6018bef65ee03d08b94adac7039411ed5b3c`，合并提交 `608725f`。
共享 README 与测试导航自动合并后逐段检查，保留 #207 的五组合选择与 #208 的轻量入口。
最终审计的 base 为上述 c1ad601，target 为 `integration/207-208`；不复用旧树确认。

所有者审阅后授权的精确重绑只有：

| 材料 | 现有登记 | 旧 SHA-256 | 新 SHA-256 |
| --- | --- | --- | --- |
| `pyproject.toml` | 中央共享材料供完整 A2 source / A10 fixture 消费 | `c3bd0b4984c4b8480c826c8a1b537712cb81bf6013c71d389af24b734a417349` | `634b507d2112cda9d656df9f60cd5f30ea557c69ee577d1d4c770240c291693c` |
| `uv.lock` | A10 fixture 字面量 | `fcd6149e80b961d9bfa3c9b0015f3ddf2835c830f03b956506f300353c0f0905` | `b398adef6f5bcb674fc411fff0faf3efbde3e4e520223a4bdfd47890c153aa8c` |

理由仅为锁内 `markdown-it-py` 4.2.0 升为直接 dev 依赖；其他依赖版本、登记成员、
验收分母与用途保持。只改中央对应值和 A10 的 uv.lock 对应值，不做 scope 哈希级联。
inventory 只新增精确活 Contract `docs/contracts/check-local.md`，分类守卫只增加同一路径。
分类、依赖身份及 A10 登记的 22 条逐组敏感确认由所有者在最终 HEAD/target 身份上另行生成，
不自动接受候选，不把必要重绑当作确认。

## 合并树开发验证与计时

合并树相关测试为 56 passed / 7.23s：本票与旧链接/inventory 共 37 项，
另加统一兼容入口与 #207 消费者目录的 19 项。全仓 Ruff format/lint 通过
（1341 个 Python 文件），mypy 1340 文件通过；`uv lock --check --offline` 通过。
合并树 `./scripts/check-compatibility cli` 为 59 passed / pytest 127.92s，
入口含 uv 为 128.47s；后续符号链接导出修复未触及该组合选择或行为，未机械重跑长测。

| 合并树测量 | format | lint | docs | 入口总耗时（含 uv） |
| --- | --- | --- | --- | --- |
| 工作树 | 0.055s | 0.059s | 0.571s | 0.757s |
| 2137 个材料的完整临时 Git 仓库真实 hook | 0.054s | 0.164s | 0.578s | 1.162s |

hook 测量包含现有内部符号链接，先同步锁定环境，Git 提交墙钟为 1.245s；
临时仓库安装及提交均成功，随后清理，不设置耗时硬门槛。

精确重绑后，无 base 的结构/字节审计 `--collect` 退出 0，285 固定模块、5281 节点，
collection skip/deselect 均为 0。它仅验证当前登记与固定分母，不解除敏感确认。
显式 base/target 审计无 baseline issues 或 hash drift，因上述 22 条未确认候选返回 1，
并受控不执行其收集；最终身份确认由所有者完成。
开发原始日志均保存在树外 `/tmp/paperradar-207-208/`，不是正式验收文件。

## 证明限制

仅在临时仓库验证 hook，不向真实仓库安装；未运行完整离线门禁或任何 live，
未发布正式验收回执。带基线审计的敏感候选仍须按最终身份独立确认。
