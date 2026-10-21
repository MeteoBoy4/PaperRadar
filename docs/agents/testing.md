# 测试

- 修复 Bug 时，先写一个在修复前失败的回归测试。
- 常规测试完全离线：使用固定 fixture / mock，不访问实时网络、付费 API 或用户数据库。
- Live source 验收通过显式命令运行，且只在用户明确要求、配置和 credential 可用时运行。
- 新增或修改 migration 时，测试从上一 revision 升级到当前 revision；涉及快照或恢复的改动，测试恢复路径。
- 完整离线验证入口与证据格式见 `docs/verification/offline-evidence.md`。

## 开发环境

- 新 worktree 直接执行 `uv run --offline --locked …`，环境自动按锁文件同步，解释器由 `.python-version`（3.14）决定。
- 若 uv 报离线缓存缺包，须先取得用户联网授权，再用 `UV_PROJECT_ENVIRONMENT=$(mktemp -d)/venv uv sync --locked` 一次性补齐缓存，完成后删除这个临时环境；不复制 `.venv`。
- 临时根默认 `/tmp`，不能位于任何 Git 工作树内；worktree 与 `.venv` 放在磁盘上，不放在 `/tmp`。
- 长时间门禁前运行 `./scripts/dev-environment check`（可加 `--json`）。命令只读，直接使用已有 Python，不触发 uv 同步；解释器版本读取项目环境的 `pyvenv.cfg`（支持 `UV_PROJECT_ENVIRONMENT`），缺失时报未知。
- 容量须严格大于 5 GiB，inode 至少 50000；配额读取失败显示“配额未知”并返回非零。配额采用非零软/硬上限中的较小者，保守忽略宽限期。pytest 残留含正常保留会话，仅提示，不导致失败；清理命令只可在没有 pytest 运行时手动执行。
- 为保持不写文件，临时根按 `tempfile` 的候选顺序通过目录权限选择，再解析符号链接；不调用会创建探测文件的 `tempfile.gettempdir()`。只读权限检查不能验证实际写入能否成功。
