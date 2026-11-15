# Stage B 两轴代码审查（r1）

- 固定点：`main`（`6f0c4e93d43b86cf25e87d90bf5130e7533d19d1`）
- 审查目标：`HEAD`（`3a25e6574d50348f8ea7f92cb8961f028e4fa024`）
- 比较命令：`git diff main...HEAD`
- 提交范围：`git log main..HEAD --oneline`，共 73 个提交
- Originating spec：GitHub issue #185 正文及全部后续评论；评论中的所有者裁决优先
- 方法：Standards 与 Spec 使用独立 fresh-context 子代理，只读分路径审查；未修改代码、未创建 commit、未运行测试或 live 命令

## Standards

### 硬性违规

- **README.md:7–48**：复制了大量 Contract 细则；尤其 **21–22** 的“`cgroup ≤8 GiB、无 swap`”属于具体前置条件。违反 `docs/agents/documentation.md`「README 规则」：“具体前置条件……由所属 Contract 维护……README 不另维护这些事实的副本”。应保留能力摘要并链接 `stage-b-workflow.md`。
- **未使用受控原因／状态类型**：违反 `docs/agents/python-conventions.md`“用明确的领域类型和受控 enum / reason 表达状态与原因”。以下新边界直接接受或声明任意 `str`，而非 `Literal`／`Enum`／封闭集合：  
  `experiment/acceptance.py:26–32`、`body_selection.py:16–23`、`egress.py:31–34`、`extraction.py:35–41`、`layout_errors.py:4–10`、`pdf.py:38–45`、`reading.py:39–46`、`reports.py:48–54`、`screening.py:35–40`；同类状态问题见 `experiment/model_mapping.py:53–56`（`state/reason: str`）及 `llm/rpc.py:420–424`。

### 判断性 smell

- **Duplicated Code** — `src/paper_radar/llm/rpc.py:427–539` 的 `probe_mapping` 大量复制 `run_call`（542–669）的描述校验、初始化、取消、异常映射与两轮清理，例如两者均重复：“`connection = _Connection(...)` / `_initialize(...)` / `_cleanup(...)`”。可抽取共享执行／清理骨架，保留探测与业务调用的不同中段。
- **Divergent Change** — `src/paper_radar/experiment/reports.py:76–1093` 的单个 `Reports` 同时承担暴露历史（79–106）、成员装配与排序、发布（662起）、文件重建／核验（980–1012）、历史及回放（1055–1093）。这些变化原因可分别拆到查询、发布和投影模块。

### 无发现项说明

其余未发现可由本 diff 明确定位的标准违约。仅做分路径只读静态审查；未修改文件，未运行测试、完整门禁或 live 命令。

## Spec

### 缺失或部分实现

- `src/paper_radar/experiment/extraction.py:82-146` 只核对当前 cgroup 成员关系及 `memory.max`/`memory.swap.max`，未验证它确为**用户 cgroup scope**；普通 cgroup 也会被接受并记录为 `scope_sha256`。Spec 第 25 条明确要求：“**命令必须运行在用户 cgroup scope 内**……否则拒绝且不占提取预算。”数值上限仍有效，但规定的执行放置未被强制。

### 范围蔓延

未发现。

### 实现错误

- `src/paper_radar/experiment/reports.py:570-572,598-604` 无序遍历全部 metadata 请求并按 paper 覆盖，未采用 `feed_metadata/service.py:448-485` 的“当前版本优先、再按 `observed_at`”权威选择。旧请求可能误报故障或掩盖当前故障。Spec US61 要求：“**空日报明确区分「无新结果」与「故障」**”；此处会使该区分及运行摘要失真。

---

汇总：Standards 共 4 项（2 项硬性违规、2 项判断性 smell），最重为多个新边界以任意 `str` 表达状态／原因；Spec 共 2 项（1 项部分实现、1 项实现错误），最重为提取路径未强制要求的用户 cgroup scope。
