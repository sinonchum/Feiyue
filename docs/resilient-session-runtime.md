# Feiyue 功能设计：抗失忆会话运行时与模型切换恢复

> **背景问题**：在 Hermes 使用过程中，主模型 Gemini 3.5 Flash 曾经频繁不可用，系统 fallback 到 DeepSeek V4 Pro 后，会像“失忆”一样重复之前已经犯过的错误，导致用户必须人工干预提醒。Feiyue 必须把这种问题作为一等公民处理：模型上下文、provider cache、网络连接和设备供电都不可信；本地持久状态才是事实来源。

---

## 1. 功能目标

### 1.1 目标

1. **中途切模型不失忆**：主模型失败、fallback 模型接手时，必须从持久状态重建上下文，而不是继承半坏的内存消息列表。
2. **断电/断网可恢复**：进程崩溃、网络断开、设备睡眠后，能从 session journal、manifest、artifact 和文件系统状态恢复。
3. **避免重复踩坑**：恢复后的模型必须先读取“已犯错误/禁止重复/当前已验证事实”，再继续执行。
4. **避免发疯执行**：恢复状态不明确时，不允许继续危险 side effect；必须进入 reconciliation（调和）流程。
5. **低内存友好**：不依赖常驻本地 LLM、向量数据库、全会话回放或多 subagent 常驻。
6. **可审计**：所有模型切换、失败、恢复、side effect 状态都必须落盘。

### 1.2 非目标

- 不保证 provider 不失败；只保证失败后恢复路径可靠。
- 不依赖把完整历史塞回 prompt。
- 不把“模型自我总结”当作事实来源。
- 不允许 fallback 模型无验证地重复外部 side effect，例如重复 push、重复付款、重复发送消息。

---

## 2. 核心原则

### 2.1 Durable Local State Is the Source of Truth

模型上下文和 provider-side cache 都是一次性缓存。事实只能来自：

1. append-only session journal。
2. latest recovery manifest。
3. durable summary。
4. artifacts：命令日志、工具结果、diff、模型错误。
5. 文件系统、Git 状态、命令验证结果。
6. 最新用户消息。

### 2.2 Fallback 必须 clean rebuild

错误做法：

```text
Gemini failed -> 把当前内存 messages 直接丢给 DeepSeek -> 继续执行
```

正确做法：

```text
Gemini failed
  -> persist model_error event
  -> close failed model call
  -> read latest_manifest + journal tail + durable summary
  -> reconcile pending operations
  -> build recovery prompt
  -> call DeepSeek fallback
```

### 2.3 恢复前先分类，不先行动

fallback/resume 后的第一步不是继续做任务，而是生成恢复判定：

1. confirmed facts：已确认事实。
2. known mistakes：本轮已经犯过、禁止重复的错误。
3. unknowns：未知状态。
4. unsafe assumptions：不允许假设的内容。
5. next safe action：下一步安全动作。

### 2.4 Side effect 必须有 operation record

任何写文件、运行命令、GitHub API、发送消息、删除/移动文件、推送代码，都必须先写 operation record，再执行。

---

## 3. 用户故事

### User Story 1：主模型不可用时自动 fallback 但不重复犯错

- **作为用户**，我希望主模型不可用时，fallback 模型能知道前面已经尝试过什么、失败原因是什么、哪些坑不能再踩。
- **验收标准**：fallback 后第一条内部动作必须读取 recovery manifest；输出中能引用 manifest 里的已验证事实和禁止重复事项。

### User Story 2：断电/断网后恢复开发任务

- **作为用户**，我希望电脑睡眠、断网或 Hermes 重启后，任务能从最后安全点恢复。
- **验收标准**：恢复后能显示最后确认的 task state、pending operation、已改文件、已验证命令。

### User Story 3：未知 side effect 不自动重放

- **作为用户**，我不希望系统在不知道上一次 push/send/delete 是否成功时自动再执行一次。
- **验收标准**：外部 side effect 状态 unknown 时，系统必须先查询 Git/GitHub/文件系统/平台状态，或者请求人工确认。

### User Story 4：避免“重新踩坑”

- **作为用户**，我希望系统能记住当前任务中已经失败的做法，例如“不要再直接改这个文件结构”“不要再次运行错误命令”。
- **验收标准**：manifest 中有 `known_mistakes` / `do_not_repeat` 字段，并在恢复 prompt 中强制注入。

---

## 4. 功能模块

## 4.1 Session Journal：追加式会话日志

### 功能

- 每个用户消息、模型响应、工具调用、工具结果、错误、恢复动作都写入 append-only JSONL。
- 事件不可原地覆盖，只能追加 correction event。
- 支持按 offset/timestamp 读取，避免全量加载。

### 技术栈

- JSONL 文件。
- 可选 SQLite index，只保存 metadata 和 offset。
- Python dataclass/Pydantic event schema。

### 事件类型

- `user_message_persisted`
- `context_built`
- `model_call_started`
- `model_error`
- `model_call_finished`
- `tool_operation_started`
- `tool_operation_finished`
- `tool_operation_unknown`
- `filesystem_snapshot`
- `git_snapshot`
- `manifest_updated`
- `recovery_started`
- `recovery_completed`

### 大概率问题

- **日志过大**：完整 tool output 很长。
  - 解决：journal 只存摘要和 artifact ref，大输出写 artifact。
- **写日志本身失败**：磁盘权限或空间问题。
  - 解决：日志写失败时禁止 side effect，进入 `RECOVERY_REQUIRED`。

---

## 4.2 Recovery Manifest：低内存恢复清单

### 功能

- 保存当前任务恢复所需的最小事实集合。
- 目标大小：5–12 KB；上限约 100 KB。
- 每次重要事件后更新。
- fallback/resume 时优先读取。

### 建议字段

```json
{
  "session_id": "...",
  "task_id": "...",
  "updated_at": "...",
  "current_goal": "...",
  "active_project": "/path/to/project",
  "confirmed_facts": [],
  "known_mistakes": [],
  "do_not_repeat": [],
  "completed_steps": [],
  "pending_operations": [],
  "changed_files": [],
  "verified_outputs": [],
  "open_questions": [],
  "next_safe_action": "...",
  "last_model": {
    "provider": "...",
    "model": "...",
    "failure_reason": "..."
  }
}
```

### 大概率问题

- **模型写入幻觉事实**。
  - 解决：manifest 只能由 runtime 根据持久证据更新；模型只能 propose，不能直接 commit。
- **manifest 太长**。
  - 解决：只保留恢复需要的事实，完整日志进 artifacts。

---

## 4.3 Known Mistakes / Do-Not-Repeat Ledger：错误防复发账本

### 功能

专门记录本轮任务中已经确认失败或用户纠正过的做法：

- 错误命令。
- 错误文件路径。
- 错误假设。
- 错误技术路线。
- 用户明确禁止的操作。
- 已经验证无效的修复。

### 示例

```json
{
  "mistake_id": "m_004",
  "summary": "Do not rerun git push before checking remote HEAD; previous push may have succeeded.",
  "evidence_ref": "artifacts/command-logs/op_012.log",
  "scope": "current_task",
  "severity": "high",
  "created_at": "..."
}
```

### 恢复规则

- fallback prompt 必须包含 top-N relevant mistakes。
- 如果下一步计划违反 `do_not_repeat`，runtime 要求模型重写计划。
- 用户纠正优先级高于模型总结。

---

## 4.4 Operation Records：side effect 操作记录

### 功能

所有 side effect 操作执行前必须创建 operation record。

### 字段

```json
{
  "operation_id": "op_s123_t17_003",
  "tool": "write_file",
  "args_hash": "sha256...",
  "status": "started|finished|failed|unknown|reconciled",
  "risk_level": "low|medium|high",
  "preconditions": {
    "path": "docs/Feiyue-PRD.md",
    "sha256_before": "..."
  },
  "postconditions": {
    "sha256_after": "...",
    "git_status_after": "..."
  },
  "artifact_refs": []
}
```

### 恢复规则

- read-only tools：可安全重跑。
- file write：必须检查 path + sha256 before/after。
- shell command：必须检查 exit code/log 是否完整。
- Git/GitHub push：必须查询 remote HEAD，不自动重复 push。
- external messages/API：必须查询幂等 key 或请求人工确认。

---

## 4.5 Recovery Prompt Builder：恢复提示构造器

### 功能

为 fallback/resume 模型构造稳定恢复上下文。

### 输入

- latest manifest。
- journal tail window。
- durable summary。
- pending operations。
- latest git/filesystem snapshot。
- latest user message。

### 输出结构

```text
You are resuming a task after provider/model interruption.
Only trust durable state below.
Do not rely on prior model cache.

Confirmed facts:
...
Known mistakes / do not repeat:
...
Pending operations:
...
Unknowns:
...
Latest user instruction:
...

First classify state, then propose next safe action.
```

### 大概率问题

- **恢复 prompt 太长**。
  - 解决：manifest + journal tail + artifact summaries，不塞完整历史。
- **fallback 模型忽略限制**。
  - 解决：runtime 验证模型下一步计划是否违反 pending/known_mistakes。

---

## 4.6 Turn State Machine：显式回合状态机

### 状态

```text
IDLE
USER_MESSAGE_PERSISTED
CONTEXT_BUILT
MAIN_MODEL_RUNNING
ASSISTANT_RESPONSE_PERSISTED
TOOL_CALLS_PENDING
TOOLS_RUNNING
TOOL_RESULTS_PERSISTED
TURN_SUMMARY_UPDATED
AUXILIARY_DEGRADED
MODEL_INTERRUPTED
UNKNOWN_SIDE_EFFECT
RECOVERY_REQUIRED
SUSPENDED_OFFLINE
```

### 规则

- 用户消息未持久化，不允许进入 model call。
- tool operation 未持久化，不允许执行工具。
- side effect unknown，不允许继续高风险操作。
- fallback 必须从 `MODEL_INTERRUPTED` 进入 `RECOVERY_REQUIRED`，完成调和后才能回到正常状态。

---

## 4.7 Auxiliary Isolation：辅助任务隔离

### 功能

标题生成、压缩、session search、vision、embedding、analytics 不能影响主任务状态。

### 规则

1. auxiliary 失败不能触发主模型 fallback。
2. auxiliary 失败不能让主会话 persistence 失败。
3. auxiliary 只能写 auxiliary event/artifact。
4. 主任务必须容忍 auxiliary 缺失。

### 示例

`Auxiliary title generation failed: HTTP 401` 只记录为 `auxiliary_degraded`，不能重置会话、不能污染 manifest。

---

## 5. 恢复流程

## 5.1 主模型失败 -> fallback

```text
1. Detect primary provider failure.
2. Persist model_error event.
3. Mark current model call closed/interrupted.
4. Persist recovery_started event.
5. Read latest_manifest.json.
6. Read journal tail by offset.
7. Reconcile pending operations.
8. Build recovery prompt.
9. Call fallback model.
10. Fallback model classifies confirmed/unknown/unsafe/next action.
11. Runtime validates next action.
12. Continue or ask user.
```

## 5.2 断电/重启 -> resume

```text
1. Load session_id.
2. Read latest_manifest.json.
3. Inspect last journal event.
4. If last state was TOOLS_RUNNING or MODEL_RUNNING, mark interrupted.
5. Reconcile filesystem/git/remote state.
6. Build recovery prompt.
7. Require model to classify state before action.
```

## 5.3 unknown side effect -> reconciliation

```text
1. Identify operation type.
2. Query durable evidence.
   - file: stat + sha256
   - git: status/log/remote HEAD
   - GitHub: API object state
   - message/API: idempotency key or platform lookup
3. Mark operation finished/failed/unknown.
4. If still unknown and high risk, ask user.
```

---

## 6. 与 Feiyue 现有模块的关系

### Audit / Replay Store

抗失忆运行时是 Audit / Replay Store 的增强版，要求 trace 不只是“事后审计”，还要支持恢复。

### Strategy Optimizer

模型切换导致的失败必须进入策略指标：

- fallback count。
- recovery success rate。
- repeated mistake count。
- unknown side effect count。
- user intervention count。

### Memory / Skill Library

本轮任务的 mistake ledger 不等于长期记忆。只有稳定、可复用、经验证的经验才进入 skill candidate。

### Safety Governor

恢复状态不明确时，Safety Governor 必须阻止危险操作。

---

## 7. MVP 范围

### MVP 必做

1. JSONL session journal。
2. latest recovery manifest。
3. operation records for side effects。
4. known mistakes / do-not-repeat ledger。
5. fallback clean context rebuild。
6. pending operation reconciliation for files and Git。
7. recovery prompt contract。
8. tests for simulated provider failure and process restart。

### MVP 不做

- 不做向量记忆。
- 不做分布式恢复。
- 不做完整浏览器 session replay。
- 不做自动长期技能发布。
- 不做所有外部平台幂等处理，只先支持 file/Git/GitHub。

---

## 8. 测试与验收

### Test 1：fallback 不重复错误

1. 主模型生成错误计划并失败。
2. runtime 写入 known_mistake。
3. 模拟主模型 503。
4. fallback 模型接手。
5. 验证 recovery prompt 包含 known_mistake。
6. 验证下一步计划不重复错误。

### Test 2：file write interrupted

1. operation record 标记 write started。
2. 写文件后模拟进程崩溃。
3. resume 后检查 sha256。
4. 标记 operation reconciled。
5. 不重复写入。

### Test 3：git push unknown

1. operation record 标记 push started。
2. push 后模拟网络断开，未收到 exit code。
3. resume 后查询 remote HEAD。
4. 如果 remote 已更新，标记 finished。
5. 不再次 push。

### Test 4：auxiliary failure 不影响主任务

1. 模拟 title generation 401。
2. 主任务继续运行。
3. manifest 不被 auxiliary 错误覆盖。

### Test 5：断电恢复先分类再行动

1. session 停在 `TOOLS_RUNNING`。
2. resume。
3. fallback prompt 要求分类 confirmed/unknown/unsafe。
4. 未调和 pending operation 前不执行新 side effect。

---

## 9. 关键数据结构草案

### RecoveryManifest

```python
class RecoveryManifest(BaseModel):
    session_id: str
    task_id: str | None = None
    updated_at: datetime
    current_goal: str
    active_project: str | None = None
    confirmed_facts: list[str] = []
    known_mistakes: list[str] = []
    do_not_repeat: list[str] = []
    completed_steps: list[str] = []
    pending_operations: list[str] = []
    changed_files: list[str] = []
    verified_outputs: list[str] = []
    open_questions: list[str] = []
    next_safe_action: str | None = None
```

### OperationRecord

```python
class OperationRecord(BaseModel):
    operation_id: str
    tool: str
    args_hash: str
    status: Literal["started", "finished", "failed", "unknown", "reconciled"]
    risk_level: Literal["low", "medium", "high"]
    preconditions: dict[str, Any]
    postconditions: dict[str, Any] = {}
    artifact_refs: list[str] = []
```

### KnownMistake

```python
class KnownMistake(BaseModel):
    mistake_id: str
    summary: str
    evidence_ref: str
    scope: Literal["turn", "task", "project"]
    severity: Literal["low", "medium", "high"]
    created_at: datetime
```

---

## 10. 实现优先级

1. Define schemas：RecoveryManifest、OperationRecord、KnownMistake、SessionEvent。
2. Build JSONL journal writer。
3. Build manifest updater。
4. Wrap side-effect tools with operation records。
5. Build file/Git reconciliation。
6. Build recovery prompt builder。
7. Simulate provider failure and fallback clean rebuild。
8. Add eval metric：repeated_mistake_count。
9. Add CLI/API command：`feiyue recover <session_id>`。

---

## 11. 一句话设计结论

Feiyue 不能把“连续性”寄托在某个模型的上下文窗口或 provider cache 上。真正可靠的抗失忆能力来自：**每一步先落盘、每个副作用先登记、每次恢复先调和、每次模型切换都从持久事实重建上下文，并把已犯错误作为硬约束注入下一轮。**
