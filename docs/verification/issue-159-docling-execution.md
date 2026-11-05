# Docling 受限执行独立 D1 覆盖

依据 [#159](https://github.com/MeteoBoy4/PaperRadar/issues/159) 与父规格
[#155](https://github.com/MeteoBoy4/PaperRadar/issues/155)。本页登记独立离线工程覆盖，
`stage_a_verified=false`；不加入 A1–A10 分母、required 或历史回执。

## 公共边界与分母

| 模块 | 节点数 | 可观察行为 |
| --- | ---: | --- |
| `tests/test_docling_executor.py` | 22 | 真实 probe 与冻结部署核验、缺失/commit/哈希/链接拒绝先于锁且无领取、真实 BodyService/四角色/唯一成功/两次预算、外部进程结果、真实 worker 的 import/MemoryError 安全结算、整组超时回收与 wait4 峰值、seccomp 及后代网络/进程组禁止、普通线程保留、RLIMIT_AS 实际分配拒绝、并发独立准备和全部出口清理、关闭公式不消费其模型、坏协议 fail-closed |
| `tests/test_docling_mapping.py` | 5 | 真实 core 对象的 children 顺序/容器/父关系/标题 level、全部多页 charspan 与 codepoint、bottom-left bbox、orig/候选/unknown、缺页与未知层拒绝、越界源不修补且自动质量拒绝、普通表格无 orig/受限展示、已有嵌图去除、图片 caption 子树与 furniture |
| `tests/test_docling_manifest_compatibility.py` | 2 | 独立旧字段字面量重建原 manifest 字节，公共四角色读取不因新增默认 null 拒绝旧制品；可选审计不改变正文身份且内部身份不一致拒绝 |
| `tests/test_docling_cold_import.py` | 1 | 冷进程禁止 SDK/网络/执行，公共 parser 构造、Body 查询与 ReadContext 重建无 SDK |
| `tests/test_no_extra_runtime.py` | 1 | extra 测试进程选择真实无 extra、同 Python minor、同 ROOT 源码的恢复解释器 |
| `tests/test_docling_executor_recovery.py` | 2 | 成功/失败审计、预算、源字符的真实基础解释器异地恢复/再备份，屏蔽原根；失败 attempt 审计语义篡改拒绝 |
| 合计 | 33 | extra+dev 主验必须全部执行，零 skip/deselect |

支撑：`tests/docling_executor_support.py` 只在外部 worker 进程边界提供合成结果，
不替换数据库、锁、预算、制品、规范化或公共 probe。
`tests/no_extra_runtime.py` 为 Body/Read 冷恢复共用真实基础解释器端口，
原 `tests/body_recovery_worker.py` 的 SDK metadata 不存在断言保持。
`tests/test_body_recovery.py` 只换该端口，原 8 节点和已发布 #158 台账的历史结果不变。
`tests/docling_execution_recovery_case.py` 是显式双环境组合：成功/失败各一次真实公共服务
与外部 worker → 备份 → 原路径屏蔽 → 无 extra 冷进程恢复/再备份；核对预算、审计、源字符。

core 模块只有依赖确实缺失时的开发 guard；这个 skip 不算覆盖通过。
版本不符、资源设施失败不得 skip，extra+dev 的真实 probe 与 core 构造必须通过。
无 extra 只运行下列明确基础消费者，不把未运行的 SDK 能力记 passed。

## 精确准备与命令

在被测仓库 ROOT 中，先明确已有可用的离线 cache 与同 minor 解释器；不联网下载、
不复制 venv，不改变 Python minor。以下环境路径都在磁盘上的独立位置。

```bash
export UV_CACHE_DIR=/path/to/prepared-cache
export UV_PYTHON_DOWNLOADS=never
export PAPER_RADAR_EXTRA_ENV=/path/to/extra-dev-env
export PAPER_RADAR_BASE_ENV=/path/to/base-dev-env
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_EXTRA_ENV" uv sync --offline --locked --extra docling --group dev --python /path/to/selected-python
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_BASE_ENV" uv sync --offline --locked --group dev --no-extra docling --python /path/to/selected-python
export PAPERRADAR_NO_EXTRA_PYTHON="$PAPER_RADAR_BASE_ENV/bin/python"
```

公共 fixture 未设置端口时，若当前已为实际基础环境则复用当前解释器；否则在本 ROOT 的
`.scratch/test-environments/no-extra-cpython-<major.minor>` 离线同步 base+dev。
显式端口非法直接失败；不跳过或换 minor。fixture 查 SDK metadata/spec 均缺失、
基础服务依赖可 import，并使恢复消费者从本 ROOT 的 `ROOT:ROOT/src` 加载源码。

extra 主验：

```bash
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_EXTRA_ENV" uv run --offline --locked --extra docling pytest -q tests/test_docling_executor.py tests/test_docling_mapping.py tests/test_docling_manifest_compatibility.py tests/test_docling_cold_import.py tests/test_no_extra_runtime.py tests/test_docling_executor_recovery.py
```

真实无 extra 冷入口、帮助、查询、上下文与旧 manifest 消费：

```bash
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_BASE_ENV" uv run --offline --locked pytest -q tests/test_docling_cold_import.py tests/test_docling_runtime_process.py tests/test_docling_manifest_compatibility.py tests/test_fulltext_artifacts.py tests/test_fulltext_quality.py
```

双环境成功/失败新审计恢复（目录须尚不存在）：

```bash
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_EXTRA_ENV" uv run --offline --locked --extra docling python -m tests.docling_execution_recovery_case produce /tmp/paperradar-docling-recovery-case
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_BASE_ENV" uv run --offline --locked python -m tests.docling_execution_recovery_case verify /tmp/paperradar-docling-recovery-case
```

主验之外重跑实际消费者：Body 的事实/提取/并发/隐私/恢复、fulltext 四模块、运行配置/
StageInput、doctor/probe 和触发的 `./scripts/check-compatibility cli`。这些检查不生成
历史组的正式回执；完整门禁仅由用户显式要求时的唯一执行者运行。

## 结果与证据边界

开发预览先仅复制 #161 尚未提交的第二迁移，公共执行/映射/规范正文组合通过；
该预览不作为正式集成或恢复验收。正式结果以合入 #161 后重跑的父票收口记录为准。
预览曾因备份消费者 head 仍旧而受控拒绝，未改 head 或 scope 预期凑绿。

TDD 先观察公共 executor/mapping 入口缺失、空成功协议被误接受及无 extra fixture 缺失，
再补实现；测试通过公共服务与真实进程观察结果。真实 SDK 只以 core 对象构造做窄映射，
没有运行真实 PDF、加载模型、联网、Pi 或付费调用。
资源设施测试只证明本机子进程限制行为，不证明 Docling 的合适内存阈值。

## 用户本人执行的 smoke 命令

以下只供 #164 用户本人在明确实验根、合法 PDF 已附加且模型部署/配置冻结后执行。
工程代理没有执行。必须自行填写资源数值；地址空间上限不能套用 EXP-3 的 cgroup 峰值。
该命令不运行 Read，不提供正式质量许可。

```bash
export PAPER_RADAR_DATABASE=/path/to/database.sqlite3
export PAPER_RADAR_DATA_ROOT=/path/to/data
export PAPER_RADAR_MODEL_ROOT=/path/to/deployed-models
export PAPER_RADAR_PAPER_ID=<已登记paper_id>
export PAPER_RADAR_SNAPSHOT_ID=<与现场工具链一致的历史snapshot_id>
export PAPER_RADAR_TIMEOUT_SECONDS=<显式秒数>
export PAPER_RADAR_MEMORY_LIMIT_BYTES=<显式虚拟地址空间字节数>
UV_PROJECT_ENVIRONMENT="$PAPER_RADAR_EXTRA_ENV" uv run --offline --locked --extra docling python - <<'PY'
import os
from pathlib import Path
from paper_radar.body import BodyService
from paper_radar.docling_executor import DoclingParser, DoclingRun
service = BodyService(Path(os.environ['PAPER_RADAR_DATABASE']), Path(os.environ['PAPER_RADAR_DATA_ROOT']))
parser = DoclingParser(DoclingRun(
    model_root=Path(os.environ['PAPER_RADAR_MODEL_ROOT']),
    timeout_seconds=float(os.environ['PAPER_RADAR_TIMEOUT_SECONDS']),
    memory_limit_bytes=int(os.environ['PAPER_RADAR_MEMORY_LIMIT_BYTES']),
))
view = service.extract(os.environ['PAPER_RADAR_PAPER_ID'], snapshot_id=os.environ['PAPER_RADAR_SNAPSHOT_ID'], parser=parser)
print({'fingerprint': view.fingerprint, 'artifact_id': view.artifact_id,
       'quality': view.quality.basis, 'remaining_attempts': view.remaining_attempts})
for attempt in view.attempts:
    print({'ordinal': attempt.ordinal, 'failure': attempt.failure,
           'elapsed_seconds': attempt.elapsed_seconds,
           'peak_memory_bytes': attempt.peak_memory_bytes,
           'execution_audit': attempt.executor_audit.model_dump(mode='json') if attempt.executor_audit else None})
PY
```

首次真实 smoke 核对：所选工具链/模型能否加载、源 charspan/断词保真、正文顺序/标题、
公式父源块 unknown 类别和候选上限、无源表格的受限信息、实际耗时与 wait4 峰值、
无 extra 冷恢复。SDK orig 不等于 PDF 原始 glyph 字节；合成测试不证明真实分类覆盖。
F 承接四刊/中文/复杂版式、PDF 裁切展示、整组物理资源与代表性安全余量；
B 仍须逐文档人工核查、用途与真实 Read 准入，doctor.models/native_abi 保持 not_assessed。

## 登记与移交

新增代码、测试、台账为独立 D1。新增执行 Contract 的精确活文档分类、任何已绑定实际
consumer 源码漂移和共享 fixture，引入的 S3 候选交 #165 最终树逐项审阅；
不机械重绑、不制造确认，不改 A9 v1 的源码/15 测试/计数/格式或 A8 冻结向量。
第二迁移的审计列由 #161 唯一提供，#159 不创建第三迁移，也不改 body01 原字节。
