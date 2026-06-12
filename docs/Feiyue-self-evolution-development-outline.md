# Feiyue 自我进化系统开发大纲

> **版本**：v0.1
> **日期**：2026-06-12
> **Canonical reference**：[`Feiyue-master-blueprint.md`](Feiyue-master-blueprint.md) 与 [`Feiyue-system-doctrine.md`](Feiyue-system-doctrine.md)
> **For Hermes**：后续 Feiyue 开发、计划、任务拆分和验收默认以本文与 System Doctrine 为准；除非用户明确说明，不得把 Feiyue 简化成普通弱模型 wrapper、普通 fallback runtime、普通 prompt optimizer 或普通 code repair bot。

---

## 0. 总目标

Feiyue 要构建的是一个**系统层自我进化框架**：

1. 默认使用 student models（例如 mimo-v2.5-pro、deepseek-v4-pro）生成和修订候选方案。
2. 使用外部 verifier 和人工验收作为 Ground Truth。
3. 在 student 失败、风险升高、不确定性过高或策略回归时，稀疏调用 teacher models（例如 GPT-5.5、Opus、Fable）作为 teacher / reviewer / labeler / strategy critic。
4. 将 teacher guidance、失败归因、成功修订和工具使用模式蒸馏为可复用系统资产。
5. 通过 eval harness 证明 weak-only、weak+Feiyue、weak+sparse-teacher、strong-full-run 之间的质量、成本和稳定性差异。
6. 通过 resilient runtime 确保断电、断网、模型 fallback、provider 切换后，系统仍能恢复进化状态并保持输出质量。

Feiyue 的进化发生在系统资产层：

- prompt templates
- planner policies
- tool-use policies
- model routing policies
- failure playbooks
- skill candidates
- strategy versions
- eval cases
- teacher guidance distillation artifacts
- recovery manifests

不默认在线修改基础模型权重；训练数据导出属于后期可选能力，且必须有许可、脱敏和审核。

---

## 1. 总体架构

### 1.1 Core Loop

主闭环：

1. Task Intake
2. Task Spec Builder
3. Model Role Router
4. Student Candidate Generation
5. Execution Sandbox
6. Verifier Layer
7. Feedback Analyzer
8. Candidate Revision Loop
9. Teacher Intervention Policy
10. Teacher Guidance Distillation
11. Strategy Optimizer
12. Evaluation Harness
13. Memory / Skill Library
14. Audit / Replay Store
15. Resilient Session Runtime
16. Safety Governor
17. API / Dashboard

### 1.2 Model Roles

Feiyue 必须显式区分模型角色：

- **Student**：默认执行者，生成 candidate、根据 feedback 修订 candidate。
- **Teacher**：稀疏介入，给出结构化指导，不默认替代完整执行链路。
- **Reviewer**：审查 candidate 风险、遗漏、约束违反。
- **Labeler**：为失败轨迹、teacher guidance、skill candidate 打标签。
- **Judge Auxiliary**：只能辅助解释，不可单独决定成功。
- **Fallback**：provider failure 后接管，但必须从 durable state clean rebuild。

### 1.3 关键原则

- Verifier / human acceptance 优先于 LLM 自评。
- Teacher 默认稀疏介入，而不是默认 executor。
- Student 的失败必须能转化为 feedback、revision 和 reusable lesson。
- 每个策略变化必须有 eval 证据。
- 每个 side effect 必须可追踪、可恢复、可调和。
- 每个 skill / playbook 默认进入候选区，不自动污染正式技能库。

---

## 2. Phase 0：Doctrine、PRD、基线文档

### 目标

建立 Feiyue 的 canonical 定义，防止后续开发跑偏。

### 功能实现

- System Doctrine：定义自我进化、弱模型质量放大、teacher 稀疏介入、跨模型质量保持。
- PRD：产品目标、非目标、核心模块、成功指标、风险。
- Development outline：阶段计划、依赖关系、并行/串行边界、测试验收。
- README：链接所有 canonical 文档。
- `.gitignore`：忽略 traces、local notes、env、cache。

### 技术栈

- Markdown
- Git / GitHub
- 本地文档校验脚本

### 依赖

- 无代码依赖。
- 依赖用户确认系统定位。

### 并行 / 串行

可并行：

- PRD、术语表、架构图、风险清单。

必须串行：

- `.gitignore` 必须早于 broad staging。
- System Doctrine 必须早于后续计划和 Phase 4+ 架构。

### Functional Acceptance

- Doctrine 明确写入：Feiyue 是系统层自我进化系统，不是普通弱模型 wrapper。
- PRD 和 outline 都引用 Doctrine。
- README 把 Doctrine 放在 Documents 首位。
- 后续路线明确包含 student/teacher roles、distillation、eval comparison。

### Code Quality & Cleanliness Acceptance

- 文档链接可解析。
- `git diff --check` 通过。
- 无 secret-like pattern。
- GitHub 远端内容 hash 与本地一致。
- 工作区 clean。

### 当前状态

已完成。

---

## 3. Phase 1：Core Schemas 与 Trace Contract

### 目标

建立后续模块共享的数据契约，避免 provider、sandbox、eval、dashboard 各自猜字段。

### 功能实现

- `TaskSpec`
- `Candidate`
- `ExecutionRun`
- `VerificationResult`
- `StrategyVersion`
- `SkillCandidate`
- `TraceEvent`
- 基础 enum：task type、candidate status、execution status、verifier type、risk level。
- JSON serialization / deserialization。
- Trace event contract。

### 技术栈

- Python 3.11+
- Pydantic v2
- pytest
- JSON / JSONL

### 主要文件

- `packages/feiyue-core/feiyue_core/schemas/*.py`
- `packages/feiyue-core/feiyue_core/audit/trace_writer.py`
- `packages/feiyue-core/tests/test_schemas.py`
- `packages/feiyue-core/tests/test_trace_writer.py`

### 依赖

- 依赖 Phase 0 文档定义。
- 不依赖 provider、LLM、GitHub、数据库。

### 并行 / 串行

可并行：

- 各 schema 文件可并行设计。
- trace writer 可与 schema tests 并行。

必须串行：

- package skeleton 先于 schema。
- `TaskSpec` 先于 `Candidate` / `ExecutionRun`。
- `TraceEvent` 先于 audit/replay/skill extraction。

### Functional Acceptance

- 每个 schema 能创建实例。
- 每个 schema 能 JSON round-trip。
- 非法 enum / 缺失必填字段会 validation fail。
- Trace event 可 append 到 JSONL 并读取。

### Code Quality & Cleanliness Acceptance

- 无循环 import。
- 无 provider/network 调用。
- `python -m compileall -q feiyue_core` 通过。
- `python -m pytest tests/test_schemas.py tests/test_trace_writer.py -q` 通过。
- 工作区 clean。

### 当前状态

已完成。

---

## 4. Phase 2：本地执行闭环 MVP

### 目标

不依赖 LLM，先证明 candidate 可以在隔离环境中执行、验证、记录证据。

### 功能实现

- Git worktree sandbox。
- Command runner。
- pytest verifier。
- LocalLoop：candidate file_writes → sandbox → verifier → result。
- stdout/stderr/exit_code/duration capture。
- source repo clean guarantee。
- toy repo fixture。

### 技术栈

- Python subprocess
- Git worktree
- pytest
- pathlib / tempfile
- JSONL trace

### 主要文件

- `feiyue_core/sandbox/worktree.py`
- `feiyue_core/sandbox/command_runner.py`
- `feiyue_core/verifiers/pytest_verifier.py`
- `feiyue_core/orchestrator/local_loop.py`
- `tests/test_worktree_sandbox.py`
- `tests/test_pytest_verifier.py`
- `tests/test_local_loop.py`

### 依赖

- 依赖 Phase 1 schemas。
- 依赖本地 Git。
- 依赖测试命令可运行。

### 并行 / 串行

可并行：

- command runner
- trace writer
- pytest verifier

必须串行：

- worktree sandbox 先于 LocalLoop。
- verifier schema 先于 LocalLoop result。

### Functional Acceptance

- toy repo failing test 可被 candidate 修复。
- LocalLoop 能返回 `VerificationResult`。
- source repo 执行前后 `git status --short` 为空。
- trace 包含 task_id、candidate_id、command、exit_code、passed。

### Code Quality & Cleanliness Acceptance

- timeout、command failure、pytest failure 都有测试。
- 不把超长 raw log 写入默认 trace。
- `python -m pytest tests/test_worktree_sandbox.py tests/test_pytest_verifier.py tests/test_local_loop.py -q` 通过。
- `git diff --check` 通过。
- 工作区 clean。

### 当前状态

已完成。

---

## 5. Phase 3：Resilient Session Runtime

### 目标

保护 Feiyue 的进化状态，确保模型 fallback、断电、断网、provider failure、进程重启后不失忆、不重复危险 side effect、不丢失质量约束。

### 功能实现

- Session journal。
- Recovery manifest。
- Operation records。
- Operation recorder。
- Known mistakes / do-not-repeat。
- Reconciler。
- ResumeFlow。
- Recovery prompt builder。
- SideEffectInspector：file hash、artifact exists、git ref、git remote ref、GitHub ref。
- RecoverySafetyGate：pending / unknown high-risk side effect 阻断。
- LocalLoop interruption simulation。
- CLI demo。

### 技术栈

- Pydantic
- JSONL
- filesystem hash
- Git CLI
- GitHub CLI (`gh`)
- pytest

### 主要文件

- `feiyue_core/runtime/journal.py`
- `feiyue_core/runtime/operation_recorder.py`
- `feiyue_core/runtime/reconciler.py`
- `feiyue_core/runtime/resume_flow.py`
- `feiyue_core/runtime/side_effect_inspector.py`
- `feiyue_core/runtime/recovery_safety_gate.py`
- `feiyue_core/runtime/interruption_simulation.py`
- `feiyue_core/recovery/*.py`
- `tests/test_journal.py`
- `tests/test_operation_recorder.py`
- `tests/test_reconciler.py`
- `tests/test_resume_flow.py`
- `tests/test_recovery_safety_gate.py`

### 依赖

- 依赖 Phase 1 schemas。
- 依赖 Phase 2 LocalLoop / side-effect boundaries。
- GitHub ref reconciliation 依赖 `gh`，测试必须 monkeypatch/fake。

### 并行 / 串行

可并行：

- journal schema
- manifest schema
- side-effect inspectors
- safety gate unit tests

必须串行：

- OperationRecorder 先于 Reconciler。
- Reconciler 先于 ResumeFlow。
- SideEffectInspector 先于 inspector-backed reconciliation。
- LocalLoop 先于 crash simulation。

### Functional Acceptance

- register 后 crash，manifest 保留 pending operation。
- resume 后能区分 confirmed / unsafe / needs_inspection。
- file/Git/GitHub side effect unknown 时先查询真实状态，不重复执行。
- high-risk pending operation 被阻断。
- LocalLoop crash 后 source repo 仍 clean。
- fallback prompt 包含 confirmed facts、do-not-repeat、next safe action。

### Code Quality & Cleanliness Acceptance

- journal append-only。
- manifest 字段稳定。
- no secret/raw dump。
- `python -m pytest tests/test_journal.py tests/test_operation_recorder.py tests/test_reconciler.py tests/test_resume_flow.py tests/test_recovery_safety_gate.py -q` 通过。
- full `python -m pytest -q` 通过。
- 工作区 clean。

### 当前状态

主干已完成。

---

## 6. Phase 4：Role-aware Student/Teacher Candidate + Feedback

### 目标

进入 Feiyue 主线：让 student model 默认生成与修订 candidate，在 verifier 和 feedback 的约束下迭代；当 policy 触发时，teacher model 稀疏介入并输出可蒸馏 guidance。

### 功能实现

1. Role-aware provider contract。
2. FakeStudentProvider / FakeTeacherProvider。
3. Provider error taxonomy。
4. ModelProfile。
5. ModelRoleRouter。
6. TeacherInterventionPolicy。
7. Structured Candidate Output。
8. Prompt Template Versioning。
9. Feedback Taxonomy。
10. Student Candidate Generation。
11. Student Revision Loop。
12. Sparse Teacher Guidance。
13. Teacher Guidance Distillation。
14. Provider failure → recovery runtime。
15. Toy iteration loop：student fail → verifier → feedback → revision → pass。

### 技术栈

- Python 3.11+
- Pydantic v2
- OpenAI-compatible provider interface
- Fake deterministic providers for unit/integration tests
- Markdown/YAML prompt templates
- pytest
- JSONL trace

### 主要文件

- `feiyue_core/providers/base.py`
- `feiyue_core/providers/roles.py`
- `feiyue_core/providers/fake.py`
- `feiyue_core/providers/errors.py`
- `feiyue_core/providers/openai_compatible.py`
- `feiyue_core/routing/model_role_router.py`
- `feiyue_core/routing/teacher_policy.py`
- `feiyue_core/generation/structured_output.py`
- `feiyue_core/generation/prompt_loader.py`
- `feiyue_core/generation/prompts/*.md`
- `feiyue_core/candidates/generator.py`
- `feiyue_core/candidates/revision.py`
- `feiyue_core/feedback/error_taxonomy.py`
- `feiyue_core/feedback/analyzer.py`
- `feiyue_core/distillation/teacher_guidance.py`
- `feiyue_core/orchestrator/iteration_loop.py`
- `tests/test_provider_payloads.py`
- `tests/test_model_role_router.py`
- `tests/test_teacher_intervention_policy.py`
- `tests/test_structured_candidate_output.py`
- `tests/test_feedback_taxonomy.py`
- `tests/test_iteration_loop.py`

### 依赖

- 依赖 Phase 2 LocalLoop。
- 依赖 Phase 3 recovery runtime。
- 依赖 Phase 1 schemas。
- OpenAI-compatible provider 依赖 API key，但所有 unit/integration tests 必须使用 fake provider。
- Teacher distillation 依赖 feedback taxonomy 和 trace evidence。

### 并行 / 串行

可并行：

- provider roles / model profile
- fake providers
- teacher policy tests
- feedback taxonomy
- prompt templates
- structured output schema

必须串行：

- ModelRoleRouter 要等 role/model profile schema 稳定。
- Candidate service 要等 provider contract + structured output 稳定。
- IterationLoop 要等 LocalLoop + FeedbackAnalyzer + CandidateRevisionLoop 稳定。
- Teacher distillation 要等 teacher guidance schema + trace evidence 稳定。
- Real provider adapter 要等 fake provider contract 稳定。

### Functional Acceptance

- 默认 candidate generation 使用 student provider。
- teacher 不默认执行；达到 policy 条件才介入。
- budget 不允许时 teacher 调用被拒绝并记录原因。
- fake student 能生成 deterministic candidate。
- invalid provider JSON 被分类为 provider/parse failure。
- failed candidate 能产生 evidence-backed feedback。
- student revision 能生成 revised candidate。
- toy repo 能从失败 candidate 迭代到 passing candidate。
- teacher guidance 不直接决定成功；成功仍必须来自 verifier / human acceptance。
- teacher guidance distillation artifact 包含 trace_id、teacher role、trigger reason、applicability、verification evidence。
- provider timeout / 429 / auth_error / invalid_json 写入 model_error event，并能进入 recovery runtime。

### Code Quality & Cleanliness Acceptance

- 无真实 credential 依赖。
- auth headers 和 API keys 不进入 repr/log/model_dump。
- provider、routing、generation、feedback、distillation 分层清晰。
- 所有 provider tests 使用 fake provider 或 monkeypatch。
- retry / iteration 有上限，避免无限 loop。
- `python -m pytest tests/test_provider_payloads.py tests/test_model_role_router.py tests/test_teacher_intervention_policy.py tests/test_structured_candidate_output.py tests/test_feedback_taxonomy.py tests/test_iteration_loop.py -q` 通过。
- full `python -m pytest -q` 通过。
- changed files secret scan 通过。
- 工作区 clean。

### 当前状态

已完成 deterministic candidate generation、feedback analysis、candidate revision loop。尚未完成 role-aware provider、teacher policy、distillation、iteration loop。

---

## 7. Phase 5：Evaluation Harness 与 Strategy Evolution

### 目标

用固定评测证明 Feiyue 是否真的让 student models 变得更接近 teacher model 输出质量，并且判断系统策略是否真的进化。

### 功能实现

- Eval task fixtures。
- Eval runner。
- StrategyVersion 管理。
- Metrics aggregation。
- Strategy comparison report。
- Regression gate。
- Model amplification report：weak-only、weak+Feiyue scaffold、weak+sparse-teacher、strong-full-run。
- Teacher metrics：teacher_call_rate、teacher_token_ratio、teacher_trigger_reason。
- Student metrics：weak_autonomy_rate、recovery_from_weak_failure、revision_count。
- Quality metrics：quality_gap_to_teacher、cost_normalized_quality、distillation_gain。

### 技术栈

- Python pytest-style eval runner
- JSONL fixtures
- Pydantic metrics schema
- Markdown / JSON reports
- SQLite/PostgreSQL later
- GitHub Actions later

### 主要文件

- `evals/tasks/*.jsonl`
- `evals/fixtures/*`
- `feiyue_core/evaluation/runner.py`
- `feiyue_core/evaluation/metrics.py`
- `feiyue_core/evaluation/report.py`
- `feiyue_core/strategy/versioning.py`
- `tests/test_eval_runner.py`
- `tests/test_metrics.py`
- `tests/test_model_amplification_metrics.py`
- `tests/test_strategy_report.py`

### 依赖

- 依赖 Phase 2 LocalLoop。
- 依赖 Phase 4 candidate/feedback/teacher loop。
- 依赖 strategy versions。
- 依赖 fixed eval fixtures。

### 并行 / 串行

可并行：

- fixtures
- metrics helpers
- report renderer
- strategy version schema

必须串行：

- eval runner 依赖 LocalLoop。
- model amplification report 依赖 metrics。
- strategy optimizer 依赖 eval runner。
- automatic strategy updates 必须等 regression gate 稳定。

### Functional Acceptance

- 同一 strategy version 可重复跑同一 eval set。
- 能输出 weak-only / weak+Feiyue / weak+sparse-teacher / strong-full-run 对比。
- 指标下降会触发 regression flag。
- report 能定位失败任务、失败类别、trace/evidence。
- teacher call rate 和 teacher token ratio 可统计。
- quality gap to teacher 可计算。

### Code Quality & Cleanliness Acceptance

- eval fixtures schema 有测试。
- metrics deterministic。
- report fields stable。
- 不把 raw private data 写入 report。
- `python -m pytest tests/test_eval_runner.py tests/test_metrics.py tests/test_model_amplification_metrics.py tests/test_strategy_report.py -q` 通过。
- full `python -m pytest -q` 通过。
- 工作区 clean。

---

## 8. Phase 6：Distillation、Skill Candidates 与 Failure Playbooks

### 目标

把成功/失败轨迹和 teacher guidance 转化为可复用资产，让系统进化能跨任务、跨模型保留。

### 功能实现

- Teacher guidance distillation。
- SkillCandidate generator。
- Failure playbook generator。
- Prompt template update proposal。
- Tool-use recipe proposal。
- Eval case proposal。
- Human review queue。
- Redaction before export。
- Retrieval metadata。

### 技术栈

- Markdown
- Pydantic metadata
- YAML frontmatter
- SQLite/PostgreSQL later
- Optional embeddings later
- pytest

### 主要文件

- `feiyue_core/distillation/teacher_guidance.py`
- `feiyue_core/skills/candidate_builder.py`
- `feiyue_core/skills/failure_playbook.py`
- `feiyue_core/skills/review_queue.py`
- `feiyue_core/memory/retriever.py`
- `tests/test_teacher_guidance_distillation.py`
- `tests/test_skill_candidate.py`
- `tests/test_failure_playbook.py`
- `tests/test_review_queue.py`
- `tests/test_redaction.py`

### 依赖

- 依赖 Phase 4 teacher guidance schema。
- 依赖 Phase 5 eval evidence。
- 依赖 audit/trace。
- 依赖 redaction/safety。

### 并行 / 串行

可并行：

- skill candidate builder
- failure playbook builder
- review queue schema
- redaction tests

必须串行：

- distillation 要等 teacher guidance 和 feedback taxonomy 稳定。
- formal skill publishing 要等 human review workflow。
- retrieval 要等 metadata 稳定。

### Functional Acceptance

- 成功轨迹能生成 skill candidate。
- 失败轨迹能生成 failure playbook。
- teacher guidance 能生成 checklist / prompt patch / tool-use recipe candidate。
- 每个 candidate 包含 source_trace_id、applicability、verification evidence、review status。
- 未审核 candidate 不能进入正式技能库。
- redaction 能 mask 私有路径、token-like 字符串、raw secret。

### Code Quality & Cleanliness Acceptance

- 生成内容不包含 raw secret。
- Markdown 格式稳定。
- review state transition 测试覆盖。
- no auto-publish side effect。
- `python -m pytest tests/test_teacher_guidance_distillation.py tests/test_skill_candidate.py tests/test_failure_playbook.py tests/test_review_queue.py tests/test_redaction.py -q` 通过。
- 工作区 clean。

---

## 9. Phase 7：Safety Governor 与 Budget Control

### 目标

确保系统获得写文件、执行命令、联网、Git push、teacher 调用、训练数据导出等能力前，有明确权限、预算和审批边界。

### 功能实现

- Permission model。
- Risk classifier。
- Dangerous command detector。
- Secret scanner。
- Budget limiter。
- Teacher budget policy。
- Human approval hook。
- Recovery-safety integration。
- Training-data export permission gate。

### 技术栈

- YAML policy
- Python policy evaluator
- regex + entropy secret scan
- pytest
- audit log

### 主要文件

- `feiyue_core/safety/policy.py`
- `feiyue_core/safety/permissions.py`
- `feiyue_core/safety/secret_scan.py`
- `feiyue_core/safety/budget.py`
- `feiyue_core/safety/approval.py`
- `tests/test_safety_policy.py`
- `tests/test_secret_scan.py`
- `tests/test_budget.py`
- `tests/test_teacher_budget_policy.py`

### 依赖

- 依赖 TaskSpec permissions。
- 依赖 CommandRunner。
- 依赖 OperationRecorder / RecoverySafetyGate。
- 依赖 provider role metadata。

### 并行 / 串行

可并行：

- secret scanner
- budget limiter
- policy schema
- dangerous command detector

必须串行：

- CommandRunner integration 要等 policy API 稳定。
- Teacher budget policy 要等 role-aware provider metadata。
- Training data export gate 要等 redaction stable。

### Functional Acceptance

- 未授权写文件被拒绝。
- 未授权 execute/network/git_push/delete 被拒绝。
- high-risk command 需要 approval。
- pending unknown side effect 未调和前不能重复 push/send/delete。
- teacher budget 超限时拒绝 teacher escalation。
- secret scanner mask 值，不回显原文。

### Code Quality & Cleanliness Acceptance

- policy deny/allow cases 覆盖所有 permission types。
- dangerous command fixtures 覆盖 rm -rf、force push、credential dump、workspace delete。
- scanner 输出只包含 masked value。
- 无绕过 policy 的 execution path。
- `python -m pytest tests/test_safety_policy.py tests/test_secret_scan.py tests/test_budget.py tests/test_teacher_budget_policy.py -q` 通过。
- 工作区 clean。

---

## 10. Phase 8：API 与 Dashboard

### 目标

让用户可以提交任务、查看候选与验证证据、比较模型/策略、审批 teacher guidance distillation 和 skill candidates。

### 功能实现

API：

- `POST /tasks`
- `GET /tasks/{id}`
- `POST /tasks/{id}/run`
- `GET /tasks/{id}/candidates`
- `GET /traces/{id}`
- `GET /evals/{run_id}`
- `GET /models/roles`
- `GET /teacher-interventions`
- `POST /skills/{id}/approve`
- `POST /strategies/{id}/approve`

Dashboard：

- task list
- task detail
- candidate comparison
- verifier results
- feedback categories
- teacher intervention log
- model amplification metrics
- strategy comparison
- skill / playbook review queue
- recovery state view

### 技术栈

- FastAPI
- Pydantic
- SQLite/PostgreSQL
- Next.js + TypeScript
- React
- Recharts/ECharts
- flat institutional UI style

### 依赖

- API 依赖 core schemas、orchestrator、eval、skills、safety。
- Dashboard 依赖 API schema。
- approval UI 依赖 review queue。
- metrics UI 依赖 Phase 5。

### 并行 / 串行

可并行：

- API mock
- frontend fixture prototype
- OpenAPI contract tests

必须串行：

- real dashboard data 依赖 API schema 稳定。
- approve/reject 依赖 review queue。
- run endpoint 依赖 safety policy。

### Functional Acceptance

- 用户能通过 API 创建 task。
- 用户能启动 toy run。
- 用户能查看 candidate、verification、feedback、teacher intervention、trace evidence。
- 用户能比较 weak-only / weak+Feiyue / weak+sparse-teacher。
- 用户能 approve/reject skill candidate。

### Code Quality & Cleanliness Acceptance

- API tests 覆盖 happy path 和 permission failure。
- OpenAPI schema 与 frontend client 类型一致。
- frontend build 通过。
- browser smoke 通过。
- UI 不暴露 raw secret 或超长 raw log。
- 后端：`python -m pytest apps/api/tests -q`。
- 前端：`npm test`、`npm run build`、browser smoke。
- 工作区 clean。

---

## 11. Phase 9：Advanced Self-Evolution Capabilities

### 目标

在基础闭环、eval、安全和审核稳定后，引入更强搜索、策略优化、记忆检索和训练数据能力。

### 功能实现

- best-of-N。
- tree search。
- multi-agent review / debate。
- bandit strategy selection。
- Bayesian optimization later。
- vector memory retrieval。
- Docker / remote sandbox。
- formal verifier adapter。
- training data export。
- holdout eval。

### 技术栈

- Python search orchestration
- optional Docker / Modal / Firecracker
- pgvector / LanceDB later
- JSONL training data packages
- optional formal verifier adapters
- pytest

### 主要文件

- `feiyue_core/search/tree_search.py`
- `feiyue_core/search/best_of_n.py`
- `feiyue_core/strategy/bandit.py`
- `feiyue_core/memory/vector_retriever.py`
- `feiyue_core/export/training_data.py`
- `feiyue_core/sandbox/docker_sandbox.py`
- `tests/test_best_of_n.py`
- `tests/test_bandit_strategy.py`
- `tests/test_training_data_export.py`
- `tests/test_vector_retrieval_policy.py`

### 依赖

- 依赖 stable eval harness。
- 依赖 safety governor。
- 依赖 redaction。
- 依赖 review/approval workflow。
- 训练数据导出依赖用户许可。

### 并行 / 串行

可并行：

- best-of-N prototype
- vector retrieval unavailable path
- Docker unavailable path
- training export schema

必须串行：

- automatic strategy update 必须等 eval regression gate 稳定。
- training data export 必须等 privacy/redaction/review 稳定。
- bandit optimization 要等 eval 数据足够。
- vector retrieval 不能在 safety policy 前触发 side effect。

### Functional Acceptance

- best-of-N 在 tiny deterministic eval 上选择 verifier 分数最高 candidate。
- bandit fixed seed 下选择稳定。
- 指标下降触发 rollback。
- retrieval 只作为 prompt context，不自动触发 side effect。
- training data export 包含 license/privacy metadata、redaction receipt、trace refs。
- Docker/formal optional dependency unavailable path 有清晰安装提示。

### Code Quality & Cleanliness Acceptance

- optional dependencies lazy import。
- no unauthorized private data export。
- export package 可 hash / replay。
- tests 覆盖 unavailable path。
- full pytest 通过。
- 工作区 clean。

---

## 12. 并行开发矩阵

### 12.1 可并行工作流

- 文档、术语、架构图。
- schema 拆分。
- trace writer 与 command runner。
- pytest verifier 与 toy fixtures。
- role-aware provider contract 与 feedback taxonomy。
- fake providers 与 prompt templates。
- teacher policy 与 model profile schema。
- eval fixtures 与 metrics/report renderer。
- skill candidate builder 与 failure playbook builder。
- secret scanner 与 budget limiter。
- API mock 与 dashboard fixture prototype。
- advanced search prototype 与 optional dependency unavailable-path tests。

### 12.2 必须串行链路

1. Doctrine → PRD/outline → Phase 4+ architecture。
2. `.gitignore` → broad staging。
3. package skeleton → schemas → trace。
4. TaskSpec → Candidate / ExecutionRun / VerificationResult。
5. sandbox → command runner integration → LocalLoop。
6. OperationRecorder → Reconciler → ResumeFlow。
7. provider roles → ModelRoleRouter → TeacherInterventionPolicy integration。
8. provider contract → structured output → CandidateService。
9. LocalLoop + FeedbackAnalyzer + CandidateRevisionLoop → IterationLoop。
10. teacher guidance schema → distillation → skill/playbook candidates。
11. eval runner → strategy comparison → automatic strategy update。
12. redaction/safety → training data export。
13. OpenAPI schema → dashboard real data integration。

---

## 13. Phase Promotion Gates

每个 Phase 进入下一 Phase 前必须满足：

1. 测试计划存在。
2. Functional Acceptance 通过。
3. Code Quality & Cleanliness Acceptance 通过。
4. RED/GREEN 证据存在，新增代码至少关键行为先失败再通过。
5. Phase 指定测试命令通过。
6. Full core regression 通过：`python -m pytest -q`。
7. compile/import check 通过：`python -m compileall -q feiyue_core`。
8. secret scan 通过。
9. 文档/README/计划同步更新。
10. git working tree clean。
11. 对远端同步任务，必须验证 remote HEAD 或 remote file hash。

---

## 14. Immediate Next Development Slice

当前代码状态已经完成：

- Phase 0 基线文档。
- Phase 1 schemas / trace。
- Phase 2 LocalLoop / sandbox / verifier。
- Phase 3 resilient runtime 主干。
- Phase 4 的 deterministic CandidateGenerator、FeedbackAnalyzer、CandidateRevisionLoop。

下一步应执行：

### Slice 4.1：Role-aware Provider Contract + Fake Student/Teacher Providers

功能：

- `ProviderRole`
- `ModelProfile`
- `ProviderRequest`
- `ProviderResponse`
- `ProviderError`
- `FakeStudentProvider`
- `FakeTeacherProvider`

测试：

- student provider deterministic response。
- teacher provider returns guidance, not success verdict。
- provider response records role/model/provider/request_id。
- auth/secret fields redacted。
- provider error taxonomy 覆盖 timeout / rate_limit / auth_error / invalid_json。

验收命令：

- `python -m pytest tests/test_provider_payloads.py -q`
- `python -m compileall -q feiyue_core && python -m pytest -q && git diff --check`

完成后才能进入：

- Slice 4.2：TeacherInterventionPolicy。
- Slice 4.3：ModelRoleRouter。
- Slice 4.4：Structured Candidate Output。
- Slice 4.5：Toy Student/Teacher IterationLoop。
