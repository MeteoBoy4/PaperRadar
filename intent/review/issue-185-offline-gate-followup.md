# #185 完整离线门禁失败后续：独立 D1 测试输入修复

本票不新增 Alembic migration，不改生产行为。基线为
`1b4a4ee8e2dc82ae6ad57bdea12e34a247427cde`；用户提供的 1b4 完整门禁回执
暴露四个独立未绑定模块的旧 setup。该回执中的固定 5281 节点已全部通过，
本次不改变 fixed285/5281、scope 登记、既有 fixture、迁移或历史报告。

## 根因与输入身份

1. `test_report_replay_projection.py` 创建当前报告，当前 renderer 已为 2。
   原 `"renderer_version":1` → `9` 没有实际变更，先在 mutation 前置断言失败。
   改为独立字面量 `2` → `9`，继续要求实际变更且长度不变，并保留
   `registration_invalid` 受控拒绝断言。
2. `test_live_bundle.py` 的当前守卫负例只布置 v28 manifest，产品当前读取
   v29，因缺文件未进入守卫比较。输入改为明确的 v29 路径，仍将合成
   `root.py` 与登记 SHA 设成不匹配，保留 `source_guard_mismatch` 和输出不存在断言。
3. `test_live_epoch_upgrade.py` 同样只拷贝 v28。改为独立字面量 v29，并继续
   拷贝 manifest 的源成员、实际篡改 `live_bundle.py`，保留受控拒绝和写入前边界。
   两项均不从生产常量或被测输出推导预期版本。
4. `test_experiment_exposure_migrations.py` 原先在当前 head 生成 renderer2
   报告，再降到 b006；b009 正确以 `renderer_v2_history_present` 阻止丢失 v2 历史。
   现在复用 `legacy_root()` 恢复已冻结的纯合成 b008/v1 非空根。该 helper
   固定检查 `stage_b_report_v1.zip` 的 SHA-256
   `27e3f911f0092fc8afd223afd781c99376071864f19f4c39f97b224ece0c049d`；
   配套 manifest 明确来源为 `b008_body_selection`、renderer 1，原报告 SHA-256 为
   `4c0c27698af9ee63d1b1b6a22a87ca58ce7cea6d57e18000f26aa0a48265d8e6`。
   公共 `initialize()` 先正常升级该旧根，再以 `report verify` 取得既有报告回执；
   不生成新报告。随后沿原 Alembic 入口降到真实 b006，明确断言 revision 为
   `b006_reports` 且唯一报告仍为 `(1, published)`，再运行原四个 stop 参数。
   原升级失败原子性、重试、根身份、published 回执、append-only、备份与冷恢复
   断言全保留，并增加升级及恢复后原回执和 Markdown 字节不变断言。

旧 v1 报告与 v1–v28 守卫材料保留原字节。v1 非空升级、Schema 与 metadata
一致性、冷恢复精确字节以及 v2 拒降保护仍由既有 renderer migration 模块核验；
v28 历史保护和守卫模块继续独立核验旧 manifest。

## 诊断与验证

按 `diagnosing-bugs` 使用四个原失败节点作为反馈环，先复现再修复。
独立 worktree 为 `.scratch/worktrees/fix-185-gate-followup`，分支
`fix/185-gate-followup`。自有 `.venv` 使用 CPython 3.14.4；实际 `sys.prefix`
和 `paper_radar.__file__` 分别指向此 worktree 的 `.venv` 和 `src/paper_radar`。
默认缓存通过离线同步建立环境后，后续使用树外 `UV_CACHE_DIR` 和 `--no-sync`。

所有 Python 命令均由 `uv run --offline --locked` 执行。完整 stdout/stderr、
收集结果和保留证明位于树外 `/tmp/paperradar-185-offline-followup/`。
原四节点红灯为 `4 failed in 8.43s`；修复后同四节点为
`4 passed in 54.25s`。中间一次仅 exposure setup 失败：公共根查询正确拒绝旧
revision，因此改用已有 `initialize()` 升级后验证，不绕过 revision 守卫。

四个修改模块完整收集 60 节点：report replay 3、live bundle 11、epoch upgrade 42、
exposure migrations 4。相关模块完整收集 47 节点：renderer migrations 10、
report migrations 5、source history 1、admission source guard 30、migration expectations 1。
四模块完整执行 `60 passed in 514.38s`；相关五模块完整执行
`47 passed in 81.79s`。两次均退出 0，无 skip、deselect 或 incomplete，覆盖原先
另三个失败节点及 exposure 的全部四个参数。

Ruff format/check 四文件通过。定向 mypy 最初只传 tests 路径，因未将 `src`
纳入分析而把生产包当无 `py.typed` 的第三方，得到 236 个导入及派生错误；
这不是生产回归，未为此改代码。显式 `MYPYPATH=src` 的四文件定向检查通过；
项目默认全覆盖 mypy（不传文件路径）通过全部 1333 个源文件。

AST 对照确认四个原模块的全部原断言保留（12、37、48、10），exposure 额外增加
6 个断言；测试名称、装饰器和参数均未变化，无删除、skip 或 deselect。
`tests/fixtures`、`src/paper_radar/storage/migrations` 和 `docs/verification`
相对基线的 Git diff 为空。未新增节点、未变更 scope、未重绑历史材料。

## 边界

本次只改变四个独立 D1 测试的 setup 与本过程记录，不触及 CLI 注册、包导入链、
发布产物或验收回执接线，因此不触发额外入口兼容组合，也不机械重跑既有 176 节点。
未运行 `./scripts/check-offline`，开发回归不构成最终完整门禁结论。
未执行任何真实/live 命令，未创建、读取或修改真实实验根或真实 runtime 根，
未读取凭据；名字包含 live 的测试均使用 `/tmp` 合成根和既有替身。
真实 HTTP、Pi、Docling 和现场恢复行为未验证。
