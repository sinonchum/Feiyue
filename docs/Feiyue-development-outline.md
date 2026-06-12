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
- **Phase 3：候选生成与反馈分析**
  - LLM provider adapter、候选计划/补丁生成、失败归因。
- **Phase 4：评测基准与策略版本**
  - 固定 eval set、策略对比、指标记录、回滚规则。
- **Phase 5：技能/经验沉淀**
  - 从成功和失败轨迹生成 skill candidates、failure playbooks。
- **Phase 6：安全治理**
  - 权限模型、secret scan、危险命令审批、预算控制。
- **Phase 7：Dashboard 与人工审核**
  - 任务状态、候选对比、指标趋势、技能审核 UI。
- **Phase 8：高级能力**
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

---

## 6. Phase 3：候选生成与反馈分析

### 目标

引入 LLM，但只让它生成候选和分析反馈，不直接决定成功。

### 功能

1. Provider adapter。
2. Structured candidate generation。
3. Patch generation 或 plan generation。
4. Feedback Analyzer。
5. Iteration loop：失败 → 分析 → 生成修复候选 → 再验证。

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
- 依赖 API key，但 unit tests 必须 mock。
- 依赖 prompt versioning。

### 是否可并行

- 可并行：provider adapter 和 feedback taxonomy。
- 可并行：prompt templates 和 unit tests。
- 必须串行：真实 iteration loop 要等 Phase 2 稳定。

### 常见问题与解决思路

1. **LLM 输出非 JSON**
   - 解决：structured output + schema validation + retry with repair prompt。
2. **Patch 不能应用**
   - 解决：先允许 plan-only；patch apply 失败归类并重试；后期引入 file-aware edit tool。
3. **模型误读错误日志**
   - 解决：Feedback Analyzer 必须引用具体日志片段；不能只给结论。
4. **API 成本不可控**
   - 解决：每个 task budget；限制 iteration count 和 candidate count。
5. **Provider 差异**
   - 解决：adapter 层只暴露统一 request/response；保存 provider/model/version。

### 验收标准

- Mock provider tests 覆盖 payload、parse、error handling。
- 一个 toy failure 能生成修复候选并通过 verifier。
- LLM 失败不会破坏 trace 或 sandbox。

---

## 7. Phase 4：评测基准与策略版本

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

---

## 8. Phase 5：技能与经验沉淀

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

---

## 9. Phase 6：安全治理

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

---

## 10. Phase 7：API 与 Dashboard

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

---

## 11. Phase 8：高级自我提升能力

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

### M3：LLM candidate + feedback

- Provider adapter。
- Candidate generator。
- Feedback analyzer。
- Retry loop。

### M4：Eval + strategy

- Eval fixtures。
- Metrics。
- Strategy version。
- Comparison report。

### M5：Skill candidate + safety

- Skill candidate generator。
- Failure playbook。
- Permission policy。
- Secret scan。

### M6：API/Dashboard

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
