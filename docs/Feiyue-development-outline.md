# Feiyue 开发大纲：AI 自我提升系统实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
>
> **Goal:** 建立一个以外部验证器为核心的 AI 自我提升闭环：任务输入、候选生成、沙箱执行、验证反馈、策略优化、技能沉淀、评测对比、审计回放。
>
> **Architecture:** 先实现本地可运行的单机 MVP：FastAPI + Python orchestrator + Git worktree sandbox + pytest-style verifier + JSONL traces。待闭环跑通后，再扩展 Dashboard、队列、数据库、向量检索、远程沙箱和训练数据导出。
>
> **Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, PostgreSQL/SQLite, Git worktree, pytest, JSONL trace, Next.js/TypeScript later, Docker later.

---

## 1. 总体开发策略

### 1.1 阶段划分

- **Phase 0：项目基线与文档**
  - 建立仓库结构、PRD、开发大纲、术语表、架构图。
- **Phase 1：核心数据结构与任务入口**
  - Task、Candidate、ExecutionRun、VerificationResult、StrategyVersion 的 schema。
- **Phase 2：本地执行闭环 MVP**
  - Git worktree sandbox、命令执行、pytest verifier、trace 保存。
- **Phase 3：抗失忆会话运行时**
  - session journal、recovery manifest、operation records、known mistakes、fallback clean rebuild、断电/断网恢复。
- **Phase 4：候选生成与反馈分析**
  - LLM provider adapter、候选计划/补丁生成、失败归因。
- **Phase 5：评测基准与策略版本**
  - 固定 eval set、策略对比、指标记录、回滚规则、repeated mistake 指标。
- **Phase 6：技能/经验沉淀**
  - 从成功和失败轨迹生成 skill candidates、failure playbooks。
- **Phase 7：安全治理**
  - 权限模型、secret scan、危险命令审批、预算控制、unknown side effect 阻断。
- **Phase 8：Dashboard 与人工审核**
  - 任务状态、候选对比、指标趋势、技能审核 UI、恢复状态展示。
- **Phase 9：高级能力**
  - Tree search、bandit 策略优化、向量检索、Docker/remote sandbox、训练数据导出。

### 1.2 MVP 优先级

必须先跑通：

1. 固定任务输入。
2. 生成候选或读取人工候选。
3. 隔离执行。
4. 外部验证。
5. 记录 trace。
6. 比较结果。
7. 形成经验候选。

不要一开始就做：

- 大而全 Dashboard。
- 分布式任务队列。
- 真实模型训练。
- 多租户权限系统。
- 复杂向量检索。
- Kubernetes / Temporal。

---

## 2. 推荐仓库结构

```text
Feiyue/
  README.md
  docs/
    Feiyue-PRD.md
    Feiyue-development-outline.md
    AI递归自我提升现状讨论 2026-06-12.md
    architecture.md
    terminology.md
  apps/
    api/                         # FastAPI backend
    dashboard/                   # Next.js dashboard, later
  packages/
    feiyue-core/                 # Core Python package
      feiyue_core/
        schemas/
        orchestrator/
        sandbox/
        verifiers/
        feedback/
        strategy/
        audit/
        runtime/
        recovery/
        safety/
      tests/
  evals/
    fixtures/
    tasks/
    runners/
  traces/                        # local-only, gitignored later
  local-notes/                   # local-only
```

### 依赖关系

- `feiyue-core` 是所有模块基础。
- `apps/api` 依赖 `feiyue-core`。
- `apps/dashboard` 依赖 `apps/api`。
- `evals` 依赖 `feiyue-core` 的 orchestrator/verifier。
- `traces` 和 `local-notes` 不应提交。

---

## 3. Phase 0：项目基线与文档

### 功能

- 明确系统定义、非目标、技术路线、风险边界。
- 建立基础目录。
- 建立 `.gitignore`，避免提交 traces、env、local notes。
- 创建架构文档和术语表。

### 技术栈

- Markdown。
- Git/GitHub。

### 是否可并行

- 可并行：PRD、术语表、架构图可以并行写。
- 必须串行：`.gitignore` 必须先于任何 broad `git add .`。

### 大概率问题

1. **文档边界过泛**：容易写成 AGI 口号。
   - 解决：所有表述锚定“外部验证器 + 局部能力提升”。
2. **过早承诺训练**：容易把“策略优化”误写成“模型自训练”。
   - 解决：训练数据导出放后期，默认不训练。
3. **隐私文件误提交**：traces 可能包含私有代码和工具输出。
   - 解决：`traces/`、`local-notes/`、`.env` 从第一天 gitignore。

### 验收标准

- PRD 和开发大纲存在。
- README 链接到核心文档。
- `.gitignore` 覆盖 traces/local-notes/env/cache。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- 文档验收：检查 PRD、开发大纲、README 的链接均可解析，章节包含目标、非目标、测试/验收、风险。
- Git 验收：运行 `git status --short`，确认没有误提交 traces、env、cache、local-notes。
- Ignore 验收：对 `traces/`、`local-notes/`、`.env` 样例运行 `git check-ignore -v`，确认命中规则。
- 合格标准：文档存在且互链正确；隐私/本地文件目录被 ignore；仓库状态干净。

---

## 4. Phase 1：核心 Schema 与项目骨架

### 目标

建立稳定的数据契约，避免后续模块互相猜字段。

### 功能

- 定义 TaskSpec。
- 定义 Candidate。
- 定义 ExecutionRun。
- 定义 VerificationResult。
- 定义 StrategyVersion。
- 定义 SkillCandidate。
- 定义 TraceEvent。

### 技术栈

- Python 3.11+。
- Pydantic v2。
- pytest。
- ruff / mypy 可选。

### 主要文件

- `packages/feiyue-core/pyproject.toml`
- `packages/feiyue-core/feiyue_core/schemas/task.py`
- `packages/feiyue-core/feiyue_core/schemas/candidate.py`
- `packages/feiyue-core/feiyue_core/schemas/execution.py`
- `packages/feiyue-core/feiyue_core/schemas/verification.py`
- `packages/feiyue-core/feiyue_core/schemas/strategy.py`
- `packages/feiyue-core/feiyue_core/schemas/trace.py`
- `packages/feiyue-core/tests/test_schemas.py`

### 依赖

- 无外部系统依赖。
- 只依赖 Python package setup。

### 是否可并行

- 可并行：各 schema 文件可并行设计。
- 必须串行：`pyproject.toml` 和包初始化必须先做。
- 建议串行：TaskSpec 先定，因为其他 schema 都引用 task_id。

### 常见问题与解决思路

1. **Schema 过早复杂化**
   - 问题：一开始加太多字段导致实现负担。
   - 解决：MVP 字段只保留 id、status、type、refs、metadata、timestamps。
2. **字段命名不稳定**
   - 问题：后续 trace/eval/API 命名不一致。
   - 解决：所有 schema 加 serialization tests。
3. **状态机混乱**
   - 问题：Task/Candidate/Run 都有 status，容易重复。
   - 解决：定义清晰状态：Task 是业务状态，Candidate 是生成状态，ExecutionRun 是执行状态。

### 验收标准

- `pytest packages/feiyue-core/tests/test_schemas.py -v` 通过。
- schema 可 JSON serialize / deserialize。
- 无外部 API 调用。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Unit tests：每个 schema 至少覆盖默认值、必填字段、enum 值、JSON round-trip。
- Contract tests：保存关键 schema 的稳定字段断言，防止后续模块悄悄改名。
- Negative tests：缺失必填字段、非法 status/type/risk level 必须 validation fail。
- 命令：`pytest packages/feiyue-core/tests/test_schemas.py -v`。
- 合格标准：测试全部通过；schema 输出不包含 secret/raw payload；没有 provider/network 调用。

---

## 5. Phase 2：本地执行闭环 MVP

### 目标

先不依赖 LLM，使用人工候选或固定 patch，跑通“候选 → 沙箱 → 验证 → trace”。

### 功能

1. 创建 sandbox。
2. 应用候选 patch。
3. 执行命令。
4. 捕获 stdout/stderr/exit code/duration。
5. 运行 verifier。
6. 写入 trace JSONL。
7. 输出结构化结果。

### 技术栈

- Python subprocess。
- Git worktree。
- pathlib/tempfile。
- pytest verifier。
- JSONL trace writer。

### 主要文件

- `feiyue_core/sandbox/worktree.py`
- `feiyue_core/sandbox/command_runner.py`
- `feiyue_core/verifiers/base.py`
- `feiyue_core/verifiers/pytest_verifier.py`
- `feiyue_core/audit/trace_writer.py`
- `feiyue_core/orchestrator/local_loop.py`
- `tests/test_worktree_sandbox.py`
- `tests/test_pytest_verifier.py`
- `tests/test_local_loop.py`

### 依赖

- 依赖 Phase 1 schema。
- 依赖本地 Git。
- 依赖目标任务仓库有测试命令。

### 是否可并行

- 可并行：command_runner、trace_writer、pytest_verifier 可并行。
- 必须串行：worktree sandbox 先于 local_loop。
- 必须串行：schema 先于所有执行模块。

### 常见问题与解决思路

1. **Git worktree 污染主仓库**
   - 解决：所有执行在临时 worktree；结束后清理；失败也保留可选 debug path。
2. **命令超时卡死**
   - 解决：subprocess timeout；stdout/stderr 上限；超时归类为 `timeout`。
3. **不同项目测试命令不同**
   - 解决：TaskSpec 中明确 verifier command；不要猜。
4. **stdout 太大**
   - 解决：保存完整日志到 artifact，trace 中只存摘要和路径/hash。
5. **macOS/Linux 命令差异**
   - 解决：避免依赖 GNU-only 工具；核心逻辑用 Python。

### 验收标准

- 用一个 toy repo 跑通失败测试 → 应用修复 → 测试通过。
- trace 中包含 task_id、candidate_id、command、exit_code、verifier result。
- 主仓库 git status 不被污染。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Unit tests：command runner 覆盖成功、失败、timeout、stdout/stderr 截断；trace writer 覆盖 JSONL 追加和可读回放。
- Integration tests：toy repo 中制造 failing test，candidate 写入修复文件后在 worktree 运行 verifier。
- Isolation tests：执行前后对源仓库运行 `git status --short`，必须保持干净。
- 命令：`pytest packages/feiyue-core/tests/test_worktree_sandbox.py packages/feiyue-core/tests/test_pytest_verifier.py packages/feiyue-core/tests/test_local_loop.py -v`。
- 合格标准：toy repo 通过；trace 证据完整；任何失败都有 exit code/failure category；主仓库无污染。

---

## 6. Phase 3：抗失忆会话运行时

### 目标

解决中途切模型、provider fallback、断电、断网、进程重启导致的“失忆”和重复踩坑问题。模型上下文和 provider cache 视为 disposable，本地持久 journal/manifest/artifacts 才是事实来源。

### 功能

1. Session journal：append-only JSONL，记录用户消息、模型调用、工具操作、错误、恢复事件。
2. Recovery manifest：5–12 KB 的低内存恢复清单，保存 confirmed facts、known mistakes、do-not-repeat、pending operations、changed files、next safe action。
3. Operation records：所有写文件、命令、Git/GitHub/API side effect 执行前先登记。
4. Known mistakes ledger：记录已验证失败的做法和用户纠正，fallback/resume 时强制注入。
5. Clean fallback rebuild：主模型失败后，fallback 从持久状态重建上下文，不继承半坏 messages。
6. Reconciliation：恢复时调和 file/Git/GitHub pending/unknown side effect。
7. Recovery prompt contract：恢复后先分类 confirmed/unknown/unsafe/next safe action，再继续执行。
8. Auxiliary isolation：标题生成、压缩、vision、embedding 等辅助失败不能污染主任务。

### 技术栈

- Pydantic recovery schemas。
- JSONL journal writer。
- Local artifact store：command logs、tool results、diffs、model errors。
- Optional SQLite index：metadata + offsets only。
- Git/filesystem/GitHub probes。

### 主要文件

- `feiyue_core/runtime/state_machine.py`
- `feiyue_core/runtime/session_journal.py`
- `feiyue_core/recovery/manifest.py`
- `feiyue_core/recovery/operation_record.py`
- `feiyue_core/recovery/known_mistakes.py`
- `feiyue_core/recovery/reconciler.py`
- `feiyue_core/recovery/prompt_builder.py`
- `tests/test_recovery_manifest.py`
- `tests/test_operation_records.py`
- `tests/test_fallback_rebuild.py`
- `tests/test_pending_operation_reconciliation.py`

### 依赖

- 依赖 Phase 1 schema。
- 依赖 Phase 2 command runner / sandbox 提供 side effect 执行入口。
- 依赖 Git 命令和文件 hash 检查。
- 不依赖 LLM provider；fallback 测试应可用 fake provider 完成。

### 是否可并行

- 可并行：session_journal、manifest schema、operation_record schema、known_mistakes schema。
- 可并行：file reconciler 和 git reconciler。
- 必须串行：operation records 要先于 side-effect tool wrapper。
- 必须串行：clean fallback rebuild 要等 manifest + journal reader 稳定。

### 常见问题与解决思路

1. **恢复时重复执行 GitHub push / send message**
   - 解决：external side effect 状态 unknown 时，先查 remote HEAD/API/idempotency key；无法确认时请求人工确认。
2. **fallback 模型忽略之前的错误**
   - 解决：known_mistakes/do_not_repeat 作为硬约束进入 recovery prompt；runtime 检查下一步计划是否违反。
3. **manifest 被模型幻觉污染**
   - 解决：模型只能 propose manifest update，runtime 只能基于 durable evidence commit。
4. **journal 太大**
   - 解决：journal 存摘要和 artifact refs；大输出进入 artifacts。
5. **断电时 operation 停在 started**
   - 解决：resume 后按 operation type 调和：file 查 sha256，git 查 status/log/remote，command 查 log/exit marker。
6. **辅助任务失败触发主 fallback**
   - 解决：auxiliary lane 完全隔离，只写 auxiliary event。

### 验收标准

- 模拟主模型失败后，fallback prompt 包含 confirmed facts 和 do-not-repeat。
- 模拟断电后，resume 能调和 file write started 状态，不重复写。
- 模拟 git push unknown 后，resume 先查询 remote HEAD，不重复 push。
- repeated_mistake_count 在 eval metrics 中可记录。
- auxiliary failure 不改变 main manifest。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Unit tests：RecoveryManifest、OperationRecord、KnownMistake、RecoveryPromptBuilder 做 JSON round-trip 和 section snapshot。
- Journal tests：append-only JSONL 顺序读取、忽略空行、manifest 原子写入。
- Reconciliation tests：pending/unknown → needs_inspection；do_not_repeat → unsafe_to_repeat；file hash/git ref/artifact 检查能确认或阻断重试。
- Resume tests：confirmed operation 从 pending 清除并写回 manifest；unsafe/unknown 写入 open_questions。
- End-to-end tests：模拟中断留下 pending operation，再运行 ResumeFlow，确认 next_safe_action 不会重复危险操作。
- 命令：`pytest packages/feiyue-core/tests/test_recovery_contracts.py packages/feiyue-core/tests/test_journal.py packages/feiyue-core/tests/test_reconciler.py packages/feiyue-core/tests/test_resume_flow.py -v`。
- 合格标准：fallback prompt 足够新模型无上下文恢复；未知 side effect 不自动重试；确认完成的 side effect 有证据并持久化。

详见：[`docs/resilient-session-runtime.md`](resilient-session-runtime.md)。

---

## 7. Phase 4：候选生成与反馈分析

### 目标

引入 LLM，但只让它生成候选和分析反馈，不直接决定成功；同时所有 provider failure 必须走 Resilient Session Runtime。

### 功能

1. Provider adapter。
2. Structured candidate generation。
3. Patch generation 或 plan generation。
4. Feedback Analyzer。
5. Iteration loop：失败 → 分析 → 生成修复候选 → 再验证。
6. Provider failure handling：主模型失败时写 model_error event，fallback clean rebuild。

### 技术栈

- OpenAI-compatible chat completions。
- Pydantic structured output。
- Prompt templates in YAML/Markdown。
- Optional: json repair。

### 主要文件

- `feiyue_core/providers/base.py`
- `feiyue_core/providers/openai_compatible.py`
- `feiyue_core/generation/candidate_generator.py`
- `feiyue_core/generation/prompts/*.md`
- `feiyue_core/feedback/error_taxonomy.py`
- `feiyue_core/feedback/analyzer.py`
- `tests/test_provider_payloads.py`
- `tests/test_feedback_taxonomy.py`

### 依赖

- 依赖 Phase 2 local_loop。
- 依赖 Phase 3 recovery runtime。
- 依赖 API key，但 unit tests 必须 mock。
- 依赖 prompt versioning。

### 是否可并行

- 可并行：provider adapter 和 feedback taxonomy。
- 可并行：prompt templates 和 unit tests。
- 必须串行：真实 iteration loop 要等 Phase 2 稳定。
- 必须串行：真实 provider fallback 要等 Phase 3 recovery runtime。

### 常见问题与解决思路

1. **LLM 输出非 JSON**
   - 解决：structured output + schema validation + retry with repair prompt。
2. **Patch 不能应用**
   - 解决：先允许 plan-only；patch apply 失败归类并重试；后期引入 file-aware edit tool。
3. **模型误读错误日志**
   - 解决：Feedback Analyzer 必须引用具体日志片段；不能只给结论。
4. **API 成本不可控**
   - 解决：每个 task budget；限制 iteration count 和 candidate count。
5. **Provider 差异 / 主模型不可用**
   - 解决：adapter 层保存 provider/model/version/error；失败后通过 recovery runtime rebuild，不直接复用 dirty messages。

### 验收标准

- Mock provider tests 覆盖 payload、parse、error handling。
- 一个 toy failure 能生成修复候选并通过 verifier。
- LLM 失败不会破坏 trace、manifest 或 sandbox。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Unit tests：provider payload、auth header redaction、response parse、retryable/non-retryable error 分类。
- Contract tests：candidate JSON 必须能 validate 成 Candidate；feedback analyzer 必须引用具体 verifier evidence。
- Fake-provider integration：用 deterministic fake provider 生成修复候选，跑通 local_loop，不依赖真实 API key。
- Failure tests：provider timeout/429/invalid JSON 必须写 model_error event，并触发 recovery runtime clean rebuild。
- 命令：`pytest packages/feiyue-core/tests/test_provider_payloads.py packages/feiyue-core/tests/test_feedback_taxonomy.py -v`，再跑 toy loop 集成测试。
- 合格标准：无真实 credential 也能测试；provider failure 不污染 manifest；候选生成结果可验证、可回放。

---

## 8. Phase 5：评测基准与策略版本

### 目标

判断系统是不是真的变好，而不是感觉变好。

### 功能

1. 固定 eval task set。
2. StrategyVersion 管理。
3. Eval runner。
4. Metrics aggregation。
5. Strategy comparison report。
6. Regression gate。

### 技术栈

- pytest-style eval runner。
- JSONL fixtures。
- SQLite/PostgreSQL metrics。
- Markdown/JSON report。

### 主要文件

- `evals/tasks/*.jsonl`
- `evals/runners/run_eval.py`
- `feiyue_core/evaluation/runner.py`
- `feiyue_core/evaluation/metrics.py`
- `feiyue_core/strategy/versioning.py`
- `tests/test_eval_runner.py`

### 依赖

- 依赖 Phase 2/3。
- 依赖固定任务集。
- 依赖可复现 sandbox。

### 是否可并行

- 可并行：fixtures 设计、metrics 实现、report 实现。
- 必须串行：runner 依赖 local_loop。

### 常见问题与解决思路

1. **评测集太小导致误判**
   - 解决：MVP 至少 10 个任务；按类别分层。
2. **任务泄漏**
   - 解决：训练/策略优化任务与 final eval 任务分开。
3. **指标单一**
   - 解决：成功率、成本、耗时、迭代次数、人工介入都记录。
4. **不可复现**
   - 解决：固定 strategy hash、prompt version、模型名、temperature。

### 验收标准

- 同一策略可重复运行 eval。
- 两个策略版本能输出对比报告。
- 指标下降时标记 regression。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Fixture tests：固定 eval task JSONL schema、任务类别、预期 verifier 配置。
- Runner tests：同一 strategy version 重跑结果结构稳定，记录 task_id、strategy_hash、metrics。
- Metrics tests：成功率、平均迭代次数、成本、耗时、repeated_mistake_count、regression flag 计算正确。
- Report tests：Markdown/JSON 对比报告包含 baseline、candidate、delta、pass/fail gate。
- 命令：`pytest packages/feiyue-core/tests/test_eval_runner.py packages/feiyue-core/tests/test_metrics.py -v`。
- 合格标准：策略比较可复现；指标下降会阻断发布；报告能定位失败任务和证据。

---

## 9. Phase 6：技能与经验沉淀

### 目标

把成功/失败轨迹变成可复用资产，而不是只存在日志里。

### 功能

1. SkillCandidate generator。
2. Failure playbook generator。
3. Prompt template update proposal。
4. Human review queue。
5. Search/retrieval for previous lessons。

### 技术栈

- Markdown。
- Pydantic metadata。
- SQLite/PostgreSQL。
- Optional embeddings：pgvector/LanceDB。

### 主要文件

- `feiyue_core/skills/candidate_builder.py`
- `feiyue_core/skills/review_queue.py`
- `feiyue_core/memory/retriever.py`
- `skills-candidates/` 或 DB-backed storage。

### 依赖

- 依赖 trace/audit。
- 依赖 feedback analyzer。
- 依赖安全治理，避免泄露私有上下文。

### 是否可并行

- 可并行：candidate builder 和 review queue。
- 必须串行：必须等 trace schema 稳定。

### 常见问题与解决思路

1. **技能污染**
   - 解决：默认生成候选，不自动发布。
2. **过拟合单一项目**
   - 解决：Skill 必须写适用条件和不适用条件。
3. **泄露私有代码/路径/密钥**
   - 解决：生成前做 redaction；人工审核。
4. **技能过多不可用**
   - 解决：按任务类型和错误类型索引；定期合并。

### 验收标准

- 成功任务能生成一份 skill candidate。
- 失败任务能生成一份 failure playbook。
- Skill candidate 包含来源 trace_id 和验证证据。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Unit tests：skill candidate builder 从 trace 中提取 title、applicability、steps、verification evidence。
- Failure-playbook tests：失败轨迹能生成 do_not_repeat、root cause、safe next action。
- Redaction tests：私有路径、token-like 字符串、raw secret 不进入 skill content。
- Review tests：未审核 candidate 不能进入正式技能库；approve/reject 状态可追踪。
- 命令：`pytest packages/feiyue-core/tests/test_skill_candidate.py packages/feiyue-core/tests/test_failure_playbook.py -v`。
- 合格标准：技能是候选而非自动发布；每条经验都有 trace/evidence；敏感信息被 mask。

---

## 10. Phase 7：安全治理

### 目标

在系统获得写文件、执行命令、联网、推送权限前建立边界。

### 功能

1. Permission model。
2. Risk classifier。
3. Dangerous command detector。
4. Secret scanner。
5. Budget limiter。
6. Human approval hook。

### 技术栈

- YAML policy。
- Python policy evaluator。
- Regex + entropy secret scan。
- Audit log。

### 主要文件

- `feiyue_core/safety/policy.py`
- `feiyue_core/safety/permissions.py`
- `feiyue_core/safety/secret_scan.py`
- `feiyue_core/safety/budget.py`
- `tests/test_safety_policy.py`

### 依赖

- 依赖 command_runner。
- 依赖 TaskSpec permissions。

### 是否可并行

- 可并行：secret_scan、budget、policy schema。
- 必须串行：command_runner 集成要等 policy API 稳定。

### 常见问题与解决思路

1. **误拦截常见命令**
   - 解决：policy 支持 allowlist，并记录解释。
2. **漏掉危险命令**
   - 解决：危险模式持续补充；高风险默认人工批准。
3. **扫描输出泄露 secret**
   - 解决：扫描报告只显示 masked value 和文件位置。
4. **权限太细导致难用**
   - 解决：MVP 权限先分 read/write/execute/network/git_push/delete。

### 验收标准

- 未授权写文件被拒绝。
- `.env`、token-like 字符串能被识别并 mask。
- git push/delete/rm -rf 等高风险操作需要 approval。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Permission tests：read/write/execute/network/git_push/delete 每类权限都有 allow/deny case。
- Dangerous-command tests：`rm -rf`、force push、credential dump、delete workspace 等必须默认阻断或审批。
- Secret-scan tests：API key/token/password fixtures 必须 mask；报告不能回显原文。
- Recovery-safety tests：pending/unknown side effect 未调和前，重复 push/send/delete 被拒绝。
- 命令：`pytest packages/feiyue-core/tests/test_safety_policy.py packages/feiyue-core/tests/test_secret_scan.py -v`。
- 合格标准：低风险操作不过度阻塞；高风险操作无审批不执行；审计日志只含脱敏内容。

---

## 11. Phase 8：API 与 Dashboard

### 目标

让用户能提交任务、查看过程、比较候选、审批技能和策略。

### 功能

#### API

- `POST /tasks`
- `GET /tasks/{id}`
- `POST /tasks/{id}/run`
- `GET /tasks/{id}/candidates`
- `GET /traces/{id}`
- `GET /evals/{run_id}`
- `POST /skills/{id}/approve`

#### Dashboard

- 任务列表。
- 任务详情。
- 候选对比。
- 验证器结果。
- 失败分类。
- 策略指标。
- 技能候选审核。

### 技术栈

- Backend：FastAPI。
- Frontend：Next.js + TypeScript。
- Styling：flat institutional style，避免花哨视觉。
- Charts：Recharts/ECharts。

### 依赖

- API 依赖 core。
- Dashboard 依赖 API。
- 审批功能依赖 safety/skills。

### 是否可并行

- 可并行：API mock 和 frontend prototype。
- 必须串行：真实 Dashboard 数据依赖 API schema 稳定。

### 常见问题与解决思路

1. **UI 先行导致数据契约反复变**
   - 解决：先 OpenAPI schema，再 UI。
2. **trace 太大不适合直接渲染**
   - 解决：API 返回摘要，完整 artifact 按需加载。
3. **实时状态复杂**
   - 解决：MVP 用 polling；后期再 WebSocket。

### 验收标准

- 用户能通过 API 创建任务并启动 run。
- Dashboard 能查看至少一个完整任务闭环。
- 技能候选可 approve/reject。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- API tests：`POST /tasks`、`GET /tasks/{id}`、`POST /tasks/{id}/run`、trace/eval/skill endpoints 覆盖 happy path 和权限失败。
- Contract tests：OpenAPI schema 与 frontend client 类型一致。
- Dashboard smoke：任务列表、任务详情、候选对比、验证结果、技能审核页面能渲染 fixture 数据。
- UX/manual acceptance：用一条完整 toy task 从创建到审核跑完，人工 checklist 记录可理解性和证据可追溯性。
- 命令：后端 `pytest apps/api/tests -v`；前端 `npm test` / `npm run build` / browser smoke。
- 合格标准：用户能看到完整证据链；approve/reject 有审计记录；UI 不暴露 raw secret/log dump。

---

## 12. Phase 9：高级自我提升能力

### 目标

在基础闭环稳定后，引入更强的搜索、优化和训练数据能力。

### 功能

1. Tree search / best-of-N。
2. Multi-agent debate / reviewer。
3. Bandit strategy selection。
4. Vector memory retrieval。
5. Training data export。
6. Docker/remote sandbox。
7. Formal verifier integration。

### 技术栈

- Search：custom tree search。
- Optimization：multi-armed bandit / Bayesian optimization。
- Vector：pgvector / LanceDB。
- Sandbox：Docker / Modal / Firecracker。
- Formal：Lean/Coq adapters。

### 依赖

- 必须依赖稳定 eval harness。
- 必须依赖 safety governor。
- 训练数据导出依赖隐私/许可流程。

### 是否可并行

- 可并行：vector memory、Docker sandbox、tree search prototype。
- 必须串行：自动策略更新必须在 eval harness 稳定后。
- 必须串行：训练数据导出必须在 privacy policy 和 redaction 稳定后。

### 常见问题与解决思路

1. **搜索成本爆炸**
   - 解决：预算、早停、分层验证。
2. **多 agent 互相强化幻觉**
   - 解决：外部验证器优先；agent debate 不作为最终证据。
3. **向量检索召回错误经验**
   - 解决：retrieval result 只作为提示，不自动执行。
4. **训练数据污染**
   - 解决：只导出验证通过且许可明确的轨迹。

### 验收标准

- best-of-N 在固定 eval 上显著提升成功率或降低迭代次数。
- 自动策略选择有回滚机制。
- 导出数据包包含 license/privacy metadata。

### 测试与验收方式

- **Functional Acceptance：功能性测试验收**：验证该 Phase 的用户可见行为、核心流程或恢复/安全行为真的成立。
- **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：验证代码结构、测试覆盖、lint/type/import、secret scan、文档同步和 git 工作区干净。

- Search tests：best-of-N/tree search 在 tiny deterministic fixtures 上选择 verifier 分数最高候选。
- Bandit tests：策略选择使用固定 seed，指标下降触发 rollback。
- Retrieval tests：向量记忆只作为提示，不直接触发 side effect；错误召回不会越权执行。
- Export tests：训练数据导出包含 license/privacy metadata、redaction receipt、trace refs，不包含未授权私有内容。
- Formal/sandbox tests：Docker/remote/formal verifier adapter 先用 optional dependency unavailable path 测试，再 gate 真实集成。
- 合格标准：高级能力必须在固定 eval 上证明收益；回滚可用；导出数据可审计且许可明确。

---

## 12. 并行开发矩阵

## 12.1 可以并行的工作流

- 文档/术语/架构图。
- Schema 文件内部拆分。
- Command runner 与 trace writer。
- Verifier adapters 与 toy fixtures。
- Provider adapter 与 feedback taxonomy。
- API mock 与 Dashboard prototype。
- Secret scanner 与 budget limiter。

## 12.2 必须串行的链路

1. `.gitignore` → broad staging/commit。
2. Package skeleton → schema → orchestrator。
3. TaskSpec → Candidate/ExecutionRun/VerificationResult。
4. Sandbox → command runner integration → local loop。
5. Local loop → eval runner。
6. Trace schema → skill candidate generator。
7. Safety policy API → command execution gate。
8. Eval harness → automatic strategy update。
9. Privacy/redaction → training data export。

---

## 13. 关键技术决策

### 13.1 为什么先代码任务？

代码任务有编译器、测试、lint、build，是最强的外部 Ground Truth。相比文档任务，代码任务更容易判定成功/失败，更适合作为自我提升闭环的 MVP。

### 13.2 为什么先 Git worktree 而不是 Docker？

Git worktree 轻量、实现快、足够验证闭环。Docker 更安全但工程成本更高，应在系统有真实执行需求后加入。

### 13.3 为什么先规则策略而不是强化学习？

MVP 的目标是验证闭环，不是训练最优策略。规则 ranking 更透明、更可控。等 eval 数据足够后再引入 bandit/Bayesian optimization。

### 13.4 为什么 LLM judge 不能作为主验证器？

LLM judge 容易偏差、奖励作弊和幻觉。Feiyue 的核心原则是：LLM 可以解释和建议，但成功必须由外部验证器或人工审核确认。

---

## 14. 测试策略

### Phase Acceptance Gates

每个 Phase 必须在进入下一 Phase 前完成以下 gate：

1. **测试计划存在**：该 Phase 的“测试与验收方式”已写明测试类型、命令、人工 checklist 和合格标准。
2. **功能性验收存在并通过**：证明需求行为成立，例如 API/CLI 输出、业务流程、恢复路径、权限行为、UI 可见结果。
3. **代码完整干净度验收存在并通过**：证明实现质量合格，例如测试覆盖、lint/typecheck、架构边界、无死代码/重复代码、无 secret、无临时文件、工作区干净。
4. **RED/GREEN 证据**：新增代码遵循 TDD；关键行为至少有一次先失败再通过的测试记录。
5. **相关测试通过**：运行该 Phase 指定测试命令，并记录 exit code 与摘要。
6. **全量回归通过**：核心包至少运行一次 `pytest -q`；文档-only 变更至少运行链接/路径/状态检查。
7. **验收证据归档**：trace/audit 或文档中记录命令、结果、artifact/hash/manual reviewer。
8. **安全检查通过**：不提交 secret、trace、local notes；高风险 side effect 有 approval 或被阻断。

### Two-track Acceptance Model

所有 Phase 和所有任务的验收都分成两条独立 gate：

#### Functional Acceptance：功能性测试验收

- 验证“用户要的功能/行为是否真的成立”。
- 典型证据：unit/integration/e2e 测试、API/CLI smoke、toy repo loop、fake provider flow、recovery simulation、人工 checklist。
- 合格标准：核心业务路径可复现；失败有明确分类；输出能追溯到 verifier evidence 或人工 reviewer。

#### Code Quality & Cleanliness Acceptance：代码完整干净度测试验收

- 验证“实现是否完整、干净、可维护、可合并”。
- 典型证据：lint、typecheck、compile/import check、dead code 检查、重复逻辑检查、架构边界检查、secret scan、git status clean。
- 合格标准：无新增 lint/type/import 错误；无临时调试代码；无未使用文件；无 secret/raw sensitive dump；没有污染工作区；文档与测试同步更新。

功能性验收通过但代码不干净，不允许合并；代码干净但功能未证明，也不允许合并。


### Unit Tests

- Schema serialization。
- Provider payload。
- Command runner timeout。
- Verifier parsing。
- Safety policy。
- Feedback taxonomy。

### Integration Tests

- Toy repo full loop。
- Failed candidate → feedback → retry。
- Eval runner with fixed fixtures。
- Trace replay。

### Smoke Tests

- API create task。
- Run local task。
- View trace。
- Generate skill candidate。

### Regression Tests

- 固定 eval set。
- Strategy version comparison。
- Safety deny cases。

---

## 15. 里程碑计划

### M0：文档和骨架

- PRD。
- 开发大纲。
- README 更新。
- 初始目录结构。

### M1：Schema + trace

- Pydantic schemas。
- JSONL trace writer。
- 基础 tests。

### M2：Sandbox + verifier

- Worktree sandbox。
- Command runner。
- pytest verifier。
- Toy repo loop。

### M3：Resilient runtime

- Session journal。
- Recovery manifest。
- Operation records。
- Known mistakes ledger。
- File/Git reconciliation。
- Clean fallback rebuild tests。

### M4：LLM candidate + feedback

- Provider adapter。
- Candidate generator。
- Feedback analyzer。
- Retry loop。

### M5：Eval + strategy

- Eval fixtures。
- Metrics。
- Strategy version。
- Comparison report。

### M6：Skill candidate + safety

- Skill candidate generator。
- Failure playbook。
- Permission policy。
- Secret scan。

### M7：API/Dashboard

- FastAPI endpoints。
- Minimal dashboard。
- Review workflow。

---

## 16. 第一个可执行 MVP 用例

### 用例：Toy Python 项目自动修复测试失败

1. 创建一个 toy repo，包含一个 failing test。
2. Feiyue 创建 TaskSpec：修复测试失败。
3. Candidate Generator 生成修复 patch。
4. Sandbox 创建 worktree。
5. 应用 patch。
6. Verifier 运行 pytest。
7. 如果失败，Feedback Analyzer 归因并生成下一轮候选。
8. 如果成功，记录 trace、diff、metrics。
9. 生成 SkillCandidate：如何处理类似断言失败。
10. Eval runner 将此任务纳入固定评测集。

### 为什么选它

- 验证信号明确。
- 成本低。
- 可完全本地运行。
- 可以覆盖核心闭环。

---

## 17. 开发中最可能遇到的问题清单

### 17.1 Patch 生成和应用不稳定

- **现象**：LLM 输出 patch 格式错误或上下文不匹配。
- **解决**：先让 LLM 输出 file edit plan；由内部 patcher 执行；patch apply 失败进入反馈 loop。

### 17.2 测试环境不可复现

- **现象**：本地能过，sandbox 失败。
- **解决**：记录 Python version、依赖安装命令、env；toy repo 固定依赖。

### 17.3 Trace 过大

- **现象**：stdout/stderr 和 diff 导致 DB 膨胀。
- **解决**：trace 存摘要，完整日志对象化存储并 hash。

### 17.4 策略优化没有统计意义

- **现象**：少数任务上提升但泛化差。
- **解决**：固定 eval + holdout eval；只在多任务稳定提升后发布策略。

### 17.5 安全策略影响开发速度

- **现象**：太多 approval 阻塞。
- **解决**：开发模式和生产模式分离；低风险 toy repo allowlist。

### 17.6 用户任务规格不明确

- **现象**：Agent 猜测目标，导致无意义迭代。
- **解决**：Task Spec Builder 在缺少验证器时必须要求澄清或创建人工 checklist。

### 17.7 LLM provider 不稳定

- **现象**：超时、429、格式漂移。
- **解决**：provider adapter retries；mock tests；真实 smoke tests credential-gated。

### 17.8 经验库质量下降

- **现象**：积累大量低质量技能，检索干扰。
- **解决**：候选审核、适用条件、定期合并和删除。

---

## 18. 实施原则

1. 每个模块先写 schema 和 unit test。
2. 每个闭环先用 toy repo 验证。
3. 每个策略更新必须有 eval 对比。
4. 每个 side effect 必须进入 trace。
5. 每个自动沉淀的技能必须人工审核。
6. 每个安全豁免必须记录理由。
7. 先局部真实，再扩展通用。

---

## 19. 下一步建议

建议下一步不是直接写完整平台，而是执行以下最小任务：

1. 创建 Python package skeleton。
2. 写核心 schemas。
3. 写 toy repo fixture。
4. 写 worktree sandbox。
5. 写 pytest verifier。
6. 跑通不依赖 LLM 的人工候选闭环。
7. 再接入 LLM candidate generator。

这样可以最快验证 Feiyue 的核心假设：**外部验证器驱动的 Agent loop 是否能稳定积累可复用能力。**
