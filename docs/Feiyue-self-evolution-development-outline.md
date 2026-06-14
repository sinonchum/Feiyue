# Feiyue 自我进化系统开发计划 v2

> **版本**：v0.2
> **日期**：2026-06-12
> **Canonical reference**：[`Feiyue-master-blueprint.md`](Feiyue-master-blueprint.md) 与 [`Feiyue-system-doctrine.md`](Feiyue-system-doctrine.md)
> **状态**：开发计划重构版。本文根据 Master Blueprint 和当前代码资产重新定义 Feiyue 的 milestone、功能范围、技术栈、双轨验收、依赖与并行开发边界。
> **For Hermes**：后续 Feiyue 开发不得把项目缩窄为 anti-amnesia runtime、普通 weak-model wrapper、普通 prompt optimizer 或普通 code repair bot。每个任务必须说明它服务于哪个 Feiyue 闭环。

---

## 0. 总目标

Feiyue 是一个 **Hermes-based Creative Evolution Loop Orchestrator**：由 Hermes 编排的自进化开发组织系统。

核心闭环：

```text
Human Creativity
→ Strong-model Specification
→ Weak-model Execution
→ Tool-grounded Verification
→ Teacher-guided Repair
→ Skill / Eval / Memory / Template / Routing Distillation
→ Better Next Iteration
```

Feiyue 追求三个战略结果：

1. **弱模型可靠执行**：弱模型在明确 task contract、verifier、teacher escalation 和经验沉淀支持下，逐渐保质保量完成更多任务。
2. **系统能力边界推进**：系统从文档同步、grep audit、小修小补，逐渐推进到局部 feature、复杂 debug、真实项目端到端交付。
3. **系统内创意角色成长**：系统逐渐能提出创意扩展、方案变体、跨项目迁移、机会发现和 taste-aware proposal，但最终选择权仍属于用户。

---

## 1. 当前代码资产盘点

### 1.1 已验证状态

当前代码状态：

- Core package：`packages/feiyue-core`
- Python source/test 文件：持续扩展中（当前 provider-free foundation 覆盖 workflow、curation、capability、creative、evaluation、providers）。
- 当前完整测试：`394 passed`
- 最新开发状态：已具备 schemas、sandbox、verifier、recovery runtime、candidate/feedback/teacher toy loop、iteration trace replay、fallback resume prompt、provider-free resume demo、M5 workflow assets、M6 curator/distillation、M7 capability、M8 creative、M9 evaluation，以及 M10 safe provider/profile integration foundation、M11 provider-free toy workflow execution / fake teacher-guided retry / verified branch promotion / report persistence foundation、M12 policy governor / run evidence / YAML policy config / human approval primitive / approval evidence handoff / run catalog / `feiyue-runs` local inspection CLI / read-only local API/dashboard/static export manifest+verify+bundle+all-in-one pipeline foundation，以及 GitHub Actions CI contract、provider-free example smoke、provider-free benchmark smoke、release checklist、contributing guide 与 architecture doc foundation。

### 1.2 已完成核心资产

#### Core Schemas / Contracts

主要文件：

- `feiyue_core/schemas/task.py`
- `feiyue_core/schemas/candidate.py`
- `feiyue_core/schemas/execution.py`
- `feiyue_core/schemas/verification.py`
- `feiyue_core/schemas/strategy.py`
- `feiyue_core/schemas/skill.py`
- `feiyue_core/schemas/trace.py`

状态：已完成基础数据契约。

#### Local Execution / Verifier / Sandbox

主要文件：

- `feiyue_core/sandbox/worktree.py`
- `feiyue_core/sandbox/command_runner.py`
- `feiyue_core/verifiers/pytest_verifier.py`
- `feiyue_core/orchestrator/local_loop.py`

状态：已完成本地执行和 pytest verifier MVP。

#### Resilient Runtime / Anti-Amnesia

主要文件：

- `feiyue_core/runtime/journal.py`
- `feiyue_core/runtime/operation_recorder.py`
- `feiyue_core/runtime/side_effect_inspector.py`
- `feiyue_core/runtime/reconciler.py`
- `feiyue_core/runtime/resume_flow.py`
- `feiyue_core/runtime/recovery_prompt.py`
- `feiyue_core/runtime/recovery_safety_gate.py`
- `feiyue_core/runtime/interruption_simulation.py`
- `feiyue_core/recovery/manifest.py`
- `feiyue_core/recovery/operation_record.py`
- `feiyue_core/recovery/known_mistakes.py`

状态：已完成基础中断恢复、side-effect 对账和 anti-amnesia runtime。

#### Candidate / Feedback / Teacher Loop

主要文件：

- `feiyue_core/candidates/generator.py`
- `feiyue_core/candidates/feedback.py`
- `feiyue_core/candidates/revision.py`
- `feiyue_core/providers/base.py`
- `feiyue_core/providers/fake.py`
- `feiyue_core/routing/model_role_router.py`
- `feiyue_core/routing/teacher_policy.py`
- `feiyue_core/generation/prompt_loader.py`
- `feiyue_core/generation/structured_output.py`
- `feiyue_core/generation/candidate_service.py`
- `feiyue_core/generation/iteration_loop.py`
- `feiyue_core/generation/trace_replay.py`
- `feiyue_core/generation/iteration_resume_demo.py`

状态：已完成 provider-free / fake-provider 的 role-aware candidate loop、teacher sparse intervention、iteration trace 和 resume prompt demo。

### 1.3 尚未完成的关键资产

根据 Master Blueprint，以下仍未系统实现：

- Real provider / Hermes profile worker execution（需明确授权和配置）。
- OpenAI-compatible HTTP adapter 的真实 provider smoke（需凭据和授权）。
- Product dashboard/API deeper interactions and static report navigation。

---

## 2. 开发原则

### 2.1 双轨验收

每个 milestone 必须同时通过两类验收。

#### Functional Acceptance

证明“做对了事”：

- 功能行为符合 Master Blueprint。
- 输入/输出 schema 稳定。
- CLI 或 public API 可真实运行。
- 状态持久化可重放。
- verifier 证据可检查。
- 不靠 LLM 自评声称完成。

#### Code Quality & Cleanliness Acceptance

证明“做得干净”：

- `python -m compileall -q feiyue_core` 通过。
- `python -m pytest -q` 通过。
- `git diff --check` 通过。
- 无 secret-like pattern。
- 无无关 diff。
- 无 eager import executable module 导致 CLI stdout 污染。
- demo / CLI 的 `--json` 模式 stdout 必须是 clean JSON。
- 工作区 clean，远端 hash 可校验。

### 2.2 TDD 顺序

每个代码 slice 默认采用：

1. 写 RED test。
2. 运行并确认失败原因正确。
3. 最小实现。
4. targeted test 通过。
5. full suite 通过。
6. 文档同步。
7. commit / push / remote verify。

### 2.3 不允许的路线偏移

- 不得把 anti-amnesia 继续扩展成项目主线。
- 不得在没有 task contract / verifier / lesson packet 的情况下宣称自进化。
- 不得让 weak model 直接消费模糊创意。
- 不得让 Teacher 默认全程接管 worker 任务。
- 不得把 strategy scoring 提前到没有 workflow assets 的阶段。

---

# 3. Milestone 0：Doctrine / Blueprint / Repository Baseline

## 目标

建立 Feiyue 的 canonical 定义、项目边界和公开文档基线。

## 已完成的功能设计

- Master Blueprint。
- System Doctrine。
- PRD。
- Development outline。
- README 文档索引。
- Obsidian RSI 讨论归档和引用。
- 私有 GitHub repo。

## 当前状态

**已完成。**

## 技术栈

- Markdown。
- Git / GitHub。
- Hermes file / terminal tools。

## 主要文件

- `docs/Feiyue-master-blueprint.md`
- `docs/Feiyue-system-doctrine.md`
- `docs/Feiyue-PRD.md`
- `docs/Feiyue-self-evolution-development-outline.md`
- `README.md`

## Functional Acceptance

- Master Blueprint 明确定义 Feiyue 是 Creative Evolution Loop Orchestrator。
- 文档明确 anti-amnesia 只是模块，不是全部。
- 文档包含弱模型能力边界推进与创意角色成长。
- README 链接 canonical 文档。

## Code Quality & Cleanliness Acceptance

- Markdown 链接存在。
- `git diff --check` 通过。
- 文档无 secret-like pattern。
- 远端 hash 与本地一致。

## 依赖

无代码依赖。依赖用户确认项目定位。

## 并行性

可并行：PRD、Doctrine、Blueprint 草案。
必须串行：Blueprint 必须作为后续路线最高层定义。

---

# 4. Milestone 1：Core Schemas / Trace Contract

## 目标

建立 Feiyue 所有后续模块共享的数据契约。

## 已完成的功能设计

- TaskSpec。
- Candidate。
- ExecutionRun。
- VerificationResult。
- StrategyVersion。
- SkillCandidate。
- TraceEvent。
- Recovery contracts。
- JSON serialization / round trip。
- JSONL trace writer。

## 当前状态

**已完成。**

## 技术栈

- Python 3.11+。
- Pydantic v2。
- pytest。
- JSON / JSONL。

## 主要文件

- `packages/feiyue-core/feiyue_core/schemas/*.py`
- `packages/feiyue-core/feiyue_core/audit/trace_writer.py`
- `packages/feiyue-core/tests/test_schemas.py`
- `packages/feiyue-core/tests/test_trace_writer.py`
- `packages/feiyue-core/tests/test_recovery_contracts.py`

## Functional Acceptance

- 每个 schema 能创建实例。
- 每个 schema 能 JSON round-trip。
- 非法 enum / 缺失字段 validation fail。
- TraceEvent 可 append 到 JSONL。

## Code Quality & Cleanliness Acceptance

- 无循环 import。
- 无 provider/network 调用。
- compileall 通过。
- schema / trace tests 通过。

## 依赖

依赖 M0。

## 并行性

可并行：各 schema、trace writer、schema tests。
必须串行：TaskSpec / Candidate / VerificationResult 稳定后，后续 runtime 和 generation 才能依赖。

---

# 5. Milestone 2：Local Execution / Verifier / Sandbox

## 目标

让 candidate 可以被真实工具环境执行和验证，建立 Feiyue 的 Ground Truth 层。

## 已完成的功能设计

- Git worktree sandbox。
- command runner。
- pytest verifier。
- LocalLoop。
- candidate file writes → sandbox → verifier → result。
- source repo clean guarantee。

## 当前状态

**已完成 MVP。**
后续 M9 会把它与真实 workflow asset / worker execution 完整融合。

## 技术栈

- Python subprocess。
- Git worktree。
- pytest。
- pathlib / tempfile。

## 主要文件

- `feiyue_core/sandbox/worktree.py`
- `feiyue_core/sandbox/command_runner.py`
- `feiyue_core/verifiers/pytest_verifier.py`
- `feiyue_core/orchestrator/local_loop.py`
- `tests/test_worktree_sandbox.py`
- `tests/test_command_runner.py`
- `tests/test_pytest_verifier.py`
- `tests/test_local_loop.py`

## Functional Acceptance

- command runner 捕获 stdout/stderr/exit code/duration。
- pytest verifier 返回 VerificationResult。
- LocalLoop 能在 isolated worktree 执行 candidate。
- source repo 在测试后保持 clean。

## Code Quality & Cleanliness Acceptance

- 不硬编码 `python3`，内部 verifier 使用当前 interpreter。
- sandbox cleanup 测试通过。
- 无 shell injection 风险的未转义动态命令。

## 依赖

依赖 M1 schemas。

## 并行性

可并行：command runner、pytest verifier、worktree sandbox。
必须串行：LocalLoop 依赖 sandbox 和 verifier。

---

# 6. Milestone 3：Resilient Runtime / Anti-Amnesia

## 目标

保护系统进化状态，使模型 fallback、中断、断电、断网后不会失忆、重复 side effect 或重复犯错。

## 已完成的功能设计

- Session journal。
- Recovery manifest。
- OperationRecord / OperationRecorder。
- side-effect check specs。
- SideEffectInspector。
- Reconciler。
- ResumeFlow。
- RecoveryPrompt。
- high-risk recovery safety gate。
- interruption simulation CLI。
- file/artifact/git/GitHub ref inspection。

## 当前状态

**已完成基础闭环。**
后续仅作为支撑模块按需增强，不作为主线继续扩张。

## 技术栈

- Python。
- Pydantic。
- JSONL。
- atomic file write。
- Git / GitHub CLI for ref inspection。
- pytest。

## 主要文件

- `feiyue_core/runtime/*.py`
- `feiyue_core/recovery/*.py`
- `tests/test_resume_flow.py`
- `tests/test_reconciler.py`
- `tests/test_operation_recorder.py`
- `tests/test_side_effect_inspector.py`
- `tests/test_interruption_simulation.py`
- `tests/test_recovery_safety_gate.py`

## Functional Acceptance

- pending operations 可以持久化。
- confirmed side effects 被清出 pending。
- unknown/high-risk operation 不会被盲目重复。
- interruption simulation 能输出 clean JSON summary。
- RecoveryPrompt 能渲染 None，而不是让 fallback model 脑补。

## Code Quality & Cleanliness Acceptance

- manifest 写入原子化。
- side-effect specs 可跨进程解释，不依赖内存对象。
- CLI `--json` 无 warning/noise。
- full pytest 通过。

## 依赖

依赖 M1 / M2。

## 并行性

可并行：journal、manifest、side-effect inspector、prompt builder。
必须串行：OperationRecorder → Reconciler → ResumeFlow → safety gate。

---

# 7. Milestone 4：Candidate / Feedback / Teacher Loop

## 目标

建立 role-aware Student → Candidate → Verifier → Feedback → Teacher → Revision 的闭环原型，并能从 trace 恢复。

## 已完成的功能设计

- CandidateGenerator。
- FeedbackAnalyzer。
- CandidateRevisionLoop。
- ProviderRole / ModelProfile / ProviderRequest / ProviderResponse。
- FakeStudentProvider / FakeTeacherProvider。
- TeacherInterventionPolicy。
- ModelRoleRouter。
- Structured Candidate Output Parser。
- Prompt Template Versioning。
- CandidateService。
- ToyIterationLoop。
- Iteration JSONL trace。
- IterationTraceReader。
- IterationResumeContextBuilder。
- IterationResumePromptBuilder。
- Provider-free iteration resume demo CLI。

## 当前状态

**基本完成。**
剩余建议只做 closeout，不再扩张 M4，以免继续偏向 runtime/toy loop。

## 技术栈

- Python。
- Pydantic。
- Markdown prompt templates。
- JSONL trace。
- fake provider fixtures。
- pytest。

## 主要文件

- `feiyue_core/candidates/*.py`
- `feiyue_core/providers/*.py`
- `feiyue_core/routing/*.py`
- `feiyue_core/generation/*.py`
- `tests/test_candidate_generation.py`
- `tests/test_candidate_service.py`
- `tests/test_iteration_loop.py`
- `tests/test_iteration_trace_replay.py`
- `tests/test_iteration_resume_prompt.py`
- `tests/test_iteration_resume_demo.py`

## Functional Acceptance

- Student candidate 可以生成并解析。
- Teacher guidance 不被误当成 candidate 或 success verdict。
- Verifier failure 可以变成 structured feedback。
- Candidate revision 保留 parent lineage。
- Iteration loop 可以 fail → teacher → revise → pass。
- Trace replay 可以生成 resume context。
- Fallback resume prompt 包含 do-not-repeat 和 next safe action。
- Provider-free CLI 输出 clean JSON。

## Code Quality & Cleanliness Acceptance

- fake providers 不调用网络。
- executable demo module 不被 `__init__.py` eager import。
- full pytest 通过。
- prompt hash deterministic。
- structured parser 对 invalid output fail fast。

## 依赖

依赖 M1 schemas、M2 verifier concept、M3 trace/recovery principles。

## 并行性

可并行：provider contract、prompt templates、feedback analyzer。
必须串行：CandidateService 依赖 provider/prompt/parser/generator；IterationLoop 依赖 CandidateService 和 feedback/revision；trace replay 依赖 trace event 稳定。

## M4 Closeout 建议

M4 后续只做文档 closeout：

- 在 README / outline 标明 M4 complete。
- 不继续增加 anti-amnesia guard，除非后续真实 workflow 需要。
- 进入 M5 Workflow Asset Layer。

---

# 8. Milestone 5：Workflow Asset Layer

## 目标

实现 Master Blueprint 中 Feiyue MVP 的核心：project memory、task templates、bug dossier、lesson packets、regression evals、model routing table。让 Feiyue 从 toy candidate loop 进入真实“自进化开发组织”工作流。

## 当前状态

**Foundation 已完成。**

本轮并行开发已完成：

- M5.1 Project Knowledge Layer。
- M5.2 Task Contract renderer 基础。
- M5.3 Bug Dossier model 基础。
- M5.4 Lesson Packet model 基础。
- M5.5 Regression Eval Assets。
- M5.6 Model Routing Table。
- 跨 lane workflow asset integration smoke：knowledge → routing → task contract → bug dossier → lesson → regression eval。

后续增强项：

- `.hermes/lessons/` 批量持久化 helper。
- `.hermes/evals/` 多 lesson 合并和去重策略。
- model routing performance learning 需要 M7 capability evidence。

## 新功能范围

### M5.1 Project Knowledge Layer

功能：

- 初始化项目 `.hermes/` 知识目录。
- 管理 `project-memory.md`、`rules.md`、`design-laws.md`、`architecture.md`。
- 支持读取并打包成 worker context。

建议文件：

- `feiyue_core/workflow/project_knowledge.py`
- `tests/test_project_knowledge.py`

### M5.2 Task Contract Templates

功能：

- 定义 feature / bugfix / ui / android / chrome-extension task contract 模板。
- 渲染 TaskSpec + project knowledge 成 worker task contract。
- 明确 files、do-not-touch、acceptance、verification、escalation。

建议文件：

- `feiyue_core/workflow/task_contract.py`
- `feiyue_core/workflow/templates/task-contract.md`
- `tests/test_task_contract.py`

### M5.3 Bug Dossier

功能：

- 标准化 worker 失败升级给 teacher 的材料。
- 包含 original task、diff summary、failing command、error excerpt、attempts、suspected cause、teacher request。
- 支持 Markdown 和 JSON serialization。

建议文件：

- `feiyue_core/workflow/bug_dossier.py`
- `tests/test_bug_dossier.py`

### M5.4 Lesson Packet

功能：

- 从失败/修复/teacher guidance 中形成 lesson packet。
- 字段包括 trigger、root cause、prevention prompt rule、verifier、skill patch suggestion、applies_to。
- 存入 `.hermes/lessons/`。

建议文件：

- `feiyue_core/workflow/lesson_packet.py`
- `tests/test_lesson_packet.py`

### M5.5 Regression Eval Assets

功能：

- 从 lesson packet 生成 regression check 候选。
- 管理 `.hermes/evals/forbidden-patterns.txt` 和 `regression-checks.sh`。
- 先只生成安全、可读、低风险的 grep-style checks。

建议文件：

- `feiyue_core/workflow/regression_eval.py`
- `tests/test_regression_eval.py`

### M5.6 Model Routing Table

功能：

- 定义 `.hermes/model-routing.yaml`。
- 支持 role → primary/fallback/reviewer/teacher。
- 暂不接真实 provider，只做配置解析、校验和 fake routing。

建议文件：

- `feiyue_core/workflow/model_routing_table.py`
- `tests/test_model_routing_table.py`

## 技术栈

- Python。
- Pydantic。
- Markdown templates。
- YAML parsing。
- pathlib。
- pytest。

## Functional Acceptance

- 可以初始化一个示例项目 `.hermes/` 目录。
- 可以从 project knowledge + TaskSpec 渲染 worker task contract。
- worker failure 可以转为 bug dossier。
- teacher guidance 可以转为 lesson packet。
- lesson packet 可以生成 regression eval 候选。
- model routing table 可解析并校验 role mapping。
- 所有 artifact 都可 read/write round-trip。

## Code Quality & Cleanliness Acceptance

- 不写入真实用户项目，测试使用 tmp_path。
- 模板渲染 deterministic。
- YAML/Markdown 解析 fail fast。
- 不存 raw secrets；长日志必须截断。
- full pytest / compileall / diff-check 通过。

## 依赖

依赖 M0 Master Blueprint、M1 schemas。
可复用 M4 TaskSpec / Candidate / provider role 概念。
不依赖 real provider。

## 并行性

可并行：Project Knowledge、Task Contract、Bug Dossier、Lesson Packet schema。
必须串行：Regression Eval 依赖 Lesson Packet；Model Routing Table 后续被 M7/M10 使用。

---

# 9. Milestone 6：Curator / Distillation System

## 目标

把 worker failure、teacher guidance、successful repair 和 verifier evidence 转化为可审核、可复用的系统资产。

## 当前状态

**Foundation 已完成。**

本轮并行开发已完成：

- M6.1 CuratorInput bundle。
- M6.2 DistillationProposal model。
- M6.3 Teacher Guidance Normalizer。
- M6.4 Review Gate。
- Curation integration smoke：workflow assets → curator input → normalized teacher guidance → review-required distillation proposal → review decision。

后续增强项：

- Lesson candidate generator 自动化。
- Asset promotion / rejection writer。
- Dedup / merge policy。
- Review decisions 到正式 `.hermes/` asset writes 的安全落地。

## 新功能范围

- CuratorInput bundle。
- Teacher guidance normalizer。
- Lesson candidate generator。
- Skill candidate proposal。
- Task template patch proposal。
- Eval patch proposal。
- Human review gate。
- Asset promotion / rejection state。

## 技术栈

- Python。
- Pydantic。
- Markdown/YAML artifact writer。
- JSONL trace refs。
- pytest。

## Functional Acceptance

- 给定 bug dossier + teacher report + verifier pass，可以生成 lesson candidate。
- lesson candidate 不会自动污染正式 skill，需要 review status。
- Curator 输出明确建议更新哪些资产：memory / skill / template / eval / routing。
- 同一个 lesson 可去重或合并。

## Code Quality & Cleanliness Acceptance

- Curator artifacts 带 provenance：source task、trace refs、teacher report refs、verifier refs。
- 不保存完整敏感日志。
- review gate 状态机测试覆盖。
- 输出 deterministic。

## 依赖

依赖 M5 Bug Dossier、Lesson Packet、Regression Eval Assets。
可读取 M4 trace / M3 recovery artifacts。

## 并行性

可并行：normalizer、proposal schemas、review gate。
必须串行：promotion 逻辑依赖 review gate 和 asset schemas。

---

# 10. Milestone 7：Weak Model Capability Expansion

## 目标

显式跟踪弱模型的任务能力边界，并用 verifier/reviewer 证据推进或回退边界。

## 当前状态

**Foundation 已完成。**

本轮并行开发已完成：

- M7.1 Capability Ladder。
- M7.2 Worker Performance Record。
- M7.3 Model Capability Profile。
- M7.4 Promotion/Demotion Recommendation Rules。
- Capability integration smoke：task complexity → reviewed curation evidence → worker performance records → model capability profile → recommendation。

后续增强项：

- Worker boundary report。
- Routing recommendation adapter（仍不直接修改 routing table）。
- Cross-model comparison report。
- 与真实 provider/worker 数据的连接。

## 新功能范围

- Capability ladder schema。
- Model capability profile。
- Task complexity level。
- Promotion rule。
- Demotion rule。
- Repeated mistake counter。
- Worker performance record。
- Routing recommendation based on capability evidence。

## 技术栈

- Python。
- Pydantic。
- JSON/YAML persistence。
- aggregation functions。
- pytest。

## Functional Acceptance

- 模型在某类任务连续通过后可被推荐升级 task level。
- 模型重复 scope creep / fake success / known mistake 后会降级或触发 teacher。
- capability profile 可解释为什么某模型适合或不适合某任务。
- 能输出 worker boundary report。

## Code Quality & Cleanliness Acceptance

- 晋升/降级规则 deterministic。
- 不基于 LLM 自评更新能力，只基于 verifier/reviewer/curator evidence。
- 聚合逻辑有边界测试。
- 避免把单次偶然成功误判成能力提升。

## 依赖

依赖 M5 Model Routing Table、M6 Curator evidence、M2/M4 verifier results。

## 并行性

可并行：capability schema、performance record、report renderer。
必须串行：promotion/demotion 依赖 performance records 和 evidence schema。

---

# 11. Milestone 8：Creative Role Development

## 目标

让系统中逐渐形成能做部分创意工作的角色：创意扩展、变体生成、跨项目迁移、机会发现、taste-aware proposal。

## 当前状态

**Foundation 已完成。**

本轮并行开发已完成：

- M8.1 Creative Brief。
- M8.2 Creative Variant Schema。
- M8.3 Creative Critique。
- M8.4 User Selection Feedback。
- Creative integration smoke：project knowledge + capability ladder → creative brief → candidate-only variants → critique → user selection feedback。

后续增强项：

- Opportunity discovery from lessons / failures。
- Accepted creative proposal metrics。
- Creative prompt/template hashing。
- 与真实 creative provider 的连接。

## 新功能范围

- Creative brief schema。
- Human seed expansion workflow。
- Variant generation task template。
- Creative critique template。
- Cross-project transfer proposal。
- Opportunity discovery from lessons / failures。
- User selection feedback record。
- Accepted creative proposal metrics。

## 技术栈

- Python。
- Markdown prompt templates。
- Pydantic。
- optional fake creative provider for tests。
- pytest。

## Functional Acceptance

- 给定 human seed，可以生成 structured creative brief。
- 可以输出 conservative / bold / low-cost / high-impact variants。
- 每个 variant 必须带风险、non-goals、verification idea。
- 用户选择反馈可记录，并用于后续 taste-aware proposal。
- 可从 lesson packets 中提出 opportunity candidate。

## Code Quality & Cleanliness Acceptance

- creative output 是候选，不自动变成 PRD 或 task。
- 不绕过 user final selection。
- prompt templates versioned/hashable。
- tests 使用 fake provider，不调用真实模型。

## 依赖

依赖 M5 Project Knowledge、M6 lessons、M7 capability/routing 可选。
不依赖 real provider，先用 fake provider 和 templates。

## 并行性

可并行：brief schema、variant template、critique template。
必须串行：opportunity discovery 依赖 lesson corpus；taste-aware metrics 依赖 user selection records。

---

# 12. Milestone 9：Strategy Scoring / Evaluation Harness

## 目标

证明 Feiyue 是否真的让弱模型接近强模型质量，并比较不同策略、模板、路由、teacher policy 的效果。

## 当前状态

**Foundation 已完成。**

本轮并行开发已完成：

- M9.1 Strategy Evaluation Record。
- M9.2 Strategy Scorecard。
- M9.3 Benchmark Task Suite。
- M9.4 Strategy Comparison Report。
- Evaluation integration smoke：benchmark suite + creative selection evidence → strategy evaluation records → scorecards → comparison report。

后续增强项：

- Real benchmark runner。
- weak-only / weak+task-contract / weak+verifier / weak+sparse-teacher / strong-reference real comparison。
- Real provider / real workflow metrics ingestion。
- Longitudinal distillation gain report。

## 新功能范围

- StrategyEvaluationRecord。
- StrategyScorecard。
- Benchmark task suite。
- weak-only / weak+task-contract / weak+verifier / weak+sparse-teacher / strong-reference comparison。
- cost-normalized quality metrics。
- repeated mistake count。
- distillation gain。
- creative proposal acceptance rate。

## 技术栈

- Python。
- Pydantic。
- JSONL/JSON reports。
- pytest。
- optional Markdown report renderer。

## Functional Acceptance

- 能运行 deterministic toy benchmark。
- 能聚合 pass rate、attempts、teacher call rate、repeated mistakes。
- 能比较至少两个 strategy/template 版本。
- 能输出 machine-readable scorecard。

## Code Quality & Cleanliness Acceptance

- benchmark deterministic。
- 不依赖真实 provider。
- metrics 定义清晰，不混淆 LLM judge 与 external verifier。
- no benchmark leakage claims。

## 依赖

依赖 M5/M6/M7。
真实 weak-vs-strong 对比依赖 M10 real provider。

## 并行性

可并行：metric schema、report renderer、toy benchmark。
必须串行：真实 strategy scoring 依赖 workflow records。

---

# 13. Milestone 10：Real Provider / Multi-Profile Worker Integration

## 目标

接入真实模型角色和 Hermes profiles，使强模型/弱模型分工从 fake provider 进入真实可运行环境。

## 当前状态

**Partial Foundation 已完成。**

已完成 provider-free / safe integration 子集：

- `FakeProfileRunner`：以 canned profile response 模拟 Hermes profile，不执行真实 subprocess，不读取或修改 Hermes 配置。
- `ProviderDiagnostic` / `ProviderFailureKind`：将 provider stderr / exit code / timeout 分类为结构化诊断。
- `redact_secrets()`：对 API key、token、password、Authorization bearer 做确定性脱敏。
- `run_profile_with_diagnostic()`：把 fake profile runner、raw result、失败分类、prompt/stderr 脱敏串成 provider integration smoke 边界。
- `tests/test_provider_integration.py`：验证 success 无 diagnostic、missing profile 失败可分类且脱敏、timeout 优先级高于 auth error。

尚未完成且必须等待授权：

- 真实 Hermes profile runner subprocess invocation。
- OpenAI-compatible provider adapter 的真实 HTTP smoke。
- teacher escalation with real model profile。
- role-bound provider config validation 对真实配置的读取。

## 新功能范围

- OpenAI-compatible provider adapter。
- Hermes profile runner integration。
- worker process invocation。
- teacher escalation with real model profile。
- request/response redaction。
- provider retry/backoff。
- rate limit and failure classification。
- role-bound provider config validation。

## 技术栈

- Python。
- subprocess / Hermes CLI integration。
- HTTP client for OpenAI-compatible adapters if needed。
- YAML config。
- pytest with fake HTTP / fake subprocess。

## Functional Acceptance

- fake subprocess/profile runner tests pass。
- provider integration smoke passes without network, credentials, real subprocess, or Hermes config access。
- failure diagnostics classify exit/timeout/stderr and redact prompt/stderr secrets。
- fake HTTP provider tests pass（后续）。
- role routing can select profile without changing global Hermes config。
- real provider smoke requires explicit user authorization and configured credentials。

## Code Quality & Cleanliness Acceptance

- 不在 repo 写入 secrets。
- logs/prompt/stderr diagnostic context redact API keys/tokens/passwords/bearer values。
- provider failures produce structured diagnostics。
- fake runner 不读取或修改真实 Hermes 配置。
- no model/provider changes without user permission。

## 依赖

依赖 M4 provider contract、M5 routing table、M7 capability profiles。
真实 smoke 依赖用户授权。

## 并行性

可并行：fake HTTP adapter、fake subprocess adapter、redaction tests。
必须串行：真实 provider smoke 必须等配置和授权。

---

# 14. Milestone 11：Real Workflow Execution / Promotion

## 目标

把 project workflow assets、worker execution、sandbox verifier 和 promotion/rollback 连接起来，让 Feiyue 能在真实项目中端到端执行一个受控 feature slice。

## 当前状态

**Provider-free Foundation 已完成。**

已完成 toy repo / safe workflow 子集：

- `CandidateFileWrite`：provider-free worker candidate side effect。
- `ToyWorkflowExecutor`：在 detached git worktree sandbox 中应用 candidate file writes。
- verifier-gated promotion readiness：只有 verification commands 通过时才 `promotion_ready=True`。
- failure → `BugDossier`：verifier failure 或 scope violation 会生成 teacher handoff。
- fake teacher-guided retry：一次 verifier failure 后可记录 `TeacherGuidanceEvent` 并用 revised writes 重试，成功仍由 verifier 判定。
- success → `LessonPacket` + `RegressionCheck`：成功后生成 lesson/eval candidate。
- verified branch promotion：`promote_verified_writes()` 只接受 `promotion_ready=True` 的 report，在临时 worktree 中创建/更新目标 branch 并提交 verified writes。
- workflow report persistence：`WorkflowReportWriter` 将 execution JSON/Markdown、bug dossier、teacher guidance、promotion result 写入 `.hermes/runs/<task_id>/`。
- source repo clean guarantee：execution 不直接修改 source checkout；promotion 只更新目标 branch ref，当前 checkout 保持 clean。
- sandbox / promotion rollback：execution worktree 和 promotion worktree 在 run 后被清理。

尚未完成且后续需要：

- 真实 worker/provider 生成 patch。
- 多轮 teacher repair loop（当前只支持 provider-free 单次 fake teacher retry）。
- promotion failure 的更细粒度 rollback report。

## 新功能范围

- TaskContract → WorkerRun。
- WorkerRun → candidate file writes / patch application。
- sandbox execution。
- verifier execution。
- bug dossier on failure。
- teacher repair loop。
- promotion to target branch/worktree。
- rollback on failure。
- worker/teacher reports。

## 技术栈

- Python。
- Git worktree。
- subprocess。
- pytest / project-specific verifier commands。
- JSONL trace。

## Functional Acceptance

- 在 toy repo 中从 task contract 到 sandboxed candidate file write 再到 verifier-gated promotion readiness 全链路运行。
- 失败时生成 bug dossier。
- scope violation 会被 blocked 且生成 teacher handoff。
- 成功后生成 lesson candidate 和 regression eval candidate。
- teacher fake guidance 后 worker retry 成功。
- verified patch promotion 到目标 branch/worktree。
- unverified report promotion blocked。
- worker/teacher persisted reports。
- source repo clean guarantee 保持。

## Code Quality & Cleanliness Acceptance

- 所有 mutating operations 在 sandbox/worktree 中执行。
- promotion readiness 需要 verifier pass。
- unverified report 不允许 promotion。
- sandbox / promotion worktree rollback 测试覆盖。
- 无 untracked artifacts 泄漏到 source repo。

## 依赖

依赖 M2、M3、M4、M5、M6。
真实 worker/provider 路径依赖 M10；provider-free toy path 可先做。

## 并行性

可并行：worker report、promotion decision、artifact collector。
必须串行：promotion 依赖 verifier pass 和 side-effect tracking。

---

# 15. Milestone 12：Safety / Budget / Policy Governor

## 目标

统一成本、安全、风险、teacher escalation、provider fallback、human approval 和 privacy gates。

## 新功能范围

- PolicyGovernor。
- teacher call budget。
- worker retry budget。
- risk-based escalation。
- privacy gate。
- unsafe action blocker。
- verifier confidence gate。
- human approval gate。
- budget/cost report。

## 技术栈

- Python。
- Pydantic policy configs。
- YAML。
- pytest。

## Functional Acceptance

- 高风险任务必须触发 approval 或 teacher。
- 超预算任务被 blocked 或 downgraded。
- privacy-sensitive context 不进入不允许的 provider role。
- repeated failure 触发 escalation。

## Code Quality & Cleanliness Acceptance

- policy decisions explainable。
- safe defaults。
- no hidden global provider config mutation。
- tests 覆盖 allow/block/escalate。

## 依赖

依赖 M5 routing、M7 capability、M10 provider metadata、M11 workflow execution。

## 并行性

可并行：policy schema、budget counters、risk gate。
必须串行：provider budget 依赖 provider metadata。

---

# 16. Milestone 13：Productization / Dashboard / API

## 目标

让 Feiyue 的任务、trace、lessons、evals、routing、capability boundary 和 creative proposals 可视化、可操作。

## 新功能范围

- CLI commands。
- local API。
- static report pages。
- trace viewer。
- lesson / eval browser。
- routing table viewer。
- capability boundary report。
- creative proposal review UI。

## 技术栈

- Python CLI。
- FastAPI or lightweight local server。
- JSON reports。
- optional static HTML。

## Functional Acceptance

- CLI 可以列出项目 assets、lessons、evals、routing、capability profiles。
- API/dashboard 可以查看任务链路和 trace。
- creative proposals 可 review / accept / reject。

## Code Quality & Cleanliness Acceptance

- read-only viewer 默认不修改项目。
- API schema documented。
- dashboard 不泄漏 secrets。
- snapshot/static report tests。

## 依赖

依赖 M5–M12 的数据资产。

## 并行性

可并行：CLI、static report、trace viewer。
必须串行：完整 dashboard 依赖稳定数据模型。

---

# 17. Milestone 14：Release Hardening / CI / Documentation

## 目标

把 Feiyue 从研究原型变成可维护项目。

## 新功能范围

- GitHub Actions CI。
- benchmark CI。
- example projects。
- docs site。
- architecture diagrams。
- contribution guide。
- security checklist。
- release checklist。

## 技术栈

- GitHub Actions。
- pytest。
- Markdown docs。
- optional MkDocs / static site。

## Functional Acceptance

- CI 运行 tests / compile / diff-check / secret scan。
- example project 可跑通 provider-free MVP。
- release checklist 明确。

## Code Quality & Cleanliness Acceptance

- CI 无 flaky tests。
- docs 与 CLI 命令一致。
- release artifact 不含 secrets。

## 依赖

建议 M5–M9 基础完成后系统推进。部分 CI 可提前做。

## 并行性

可并行：docs、CI skeleton、examples。
必须串行：benchmark CI 依赖 M9；provider docs 依赖 M10。

---

# 18. 并行开发矩阵

## 18.1 可并行 Lane

### Lane A：Runtime / Recovery

负责：M3 支撑、M11 promotion/rollback、M12 safety gate。
当前状态：M3 基础完成。

### Lane B：Workflow Assets

负责：M5 project knowledge、task templates、bug dossier、lesson packets、routing table。
当前状态：未开始，是下一阶段主线。

### Lane C：Curator / Distillation

负责：M6 teacher guidance normalizer、lesson proposal、skill/eval/template patch proposal。
当前状态：依赖 M5。

### Lane D：Capability / Routing Evolution

负责：M7 capability ladder、promotion/demotion、routing recommendation。
当前状态：依赖 M5/M6 records。

### Lane E：Creative Role

负责：M8 creative brief、variant generation、opportunity discovery、taste-aware proposal。
当前状态：可在 M5 Project Knowledge 后启动。

### Lane F：Evaluation

负责：M9 metrics、scorecards、toy benchmark、reports。
当前状态：可先做 toy metrics，但真实效果依赖 M5–M8。

### Lane G：Provider / Worker Integration

负责：M10 real provider / Hermes profile worker。
当前状态：需要用户授权真实 provider 配置；可先做 fake adapters。

### Lane H：Productization

负责：M13 CLI/API/dashboard/report。
当前状态：等数据资产稳定后推进。

## 18.2 必须串行链路

```text
M0 Blueprint
→ M1 Schemas
→ M5 Workflow Assets
→ M6 Curator Distillation
→ M7 Capability Expansion
→ M9 Evaluation Harness
```

```text
M2 Sandbox
→ M11 Real Workflow Execution
→ M12 Safety/Budget Governor
```

```text
M4 Provider/Candidate Loop
→ M10 Real Provider Integration
→ M11 Real Workflow Execution with real workers
```

```text
M5 Project Knowledge
→ M8 Creative Role Development
→ M9 Creative proposal metrics
```

---

# 19. 当前完成度矩阵

> **Status sync date**：2026-06-14
> **Verified baseline**：`664 passed`（local full gate for Wave 1/2/3 provider-free and authorization-gated lanes, M14 provider-free smokes, docs/release contract, Wave4 live-benchmark scoring contracts, Wave4-2 profile-worker bridge contracts, Wave4-2B real profile workflow smoke status contract, Wave4-2C real teacher retry smoke status contract, Wave4-2D productized runner contracts, Wave4-3A dry-run/no-promotion contract, Wave4-3B approval-gated promotion contracts, Wave4-3B-3 low-risk real-project branch-only promotion smoke, Wave4-3C productized approval CLI smoke, Wave4-4 audit-only capability feedback loop, Wave4-4B human-reviewed routing proposal, and Wave4-4C approval-gated routing apply；remote CI mirrors provider-free smokes）。Current verified baseline: `664 passed`.
> **Scope note**：以下状态按 Master Blueprint 对照当前代码、测试、README、CI 与 provider-free 产物整理。`Foundation` 表示可测试的 provider-free/typed/smoke 基础已完成，但真实 provider、真实多 worker、长期资产写入或生产级 UI 仍未完成。

| Milestone | 状态 | 说明 |
|---|---:|---|
| M0 Doctrine / Blueprint | Done | Master Blueprint、System Doctrine、PRD、development outline、README 索引、私有 GitHub repo 已完成。 |
| M1 Core Schemas | Done | schemas / trace contracts / JSON round-trip / JSONL writer 已测。 |
| M2 Local Execution / Verifier | Done MVP | worktree sandbox、command runner、pytest verifier、LocalLoop、source repo clean guarantee 已完成。 |
| M3 Resilient Runtime | Done Foundation | journal、recovery manifest、operation recorder、side-effect inspector、reconciler、resume flow、recovery prompt、安全 gate 与 interruption simulation 已完成；后续只作为支撑模块按需增强。 |
| M4 Candidate / Feedback / Teacher Loop | Done Foundation | fake provider、role-aware student/teacher、candidate service、feedback/revision、iteration trace/replay、fallback resume prompt demo 已完成。 |
| M5 Workflow Asset Layer | Done Foundation | project knowledge、task contract、bug dossier、lesson packet、regression eval、routing table 与 integration smoke 已完成；批量 lesson persistence / routing learning 后续增强。 |
| M6 Curator / Distillation | Done Foundation++ | CuratorInput、TeacherGuidanceSummary、DistillationProposal、ReviewGate、asset proposal persistence、append-only review decisions、provider-free promotion gate、per-patch lesson/regression_eval/task_template promotion 与 duplicate lesson blocking 已完成；更完整的 asset lifecycle/versioning/UI 后续增强。 |
| M7 Weak Model Capability Expansion | Done Foundation+ | CapabilityLadder、WorkerPerformanceRecord、ModelCapabilityProfile、promotion/demotion recommendation rules、capability smoke、Phase C live evidence ingestion 与 capability-history records 已完成；长期纵向收益仍需 mini-program 量化。 |
| M8 Creative Role Development | Partial Real Creative Lane | CreativeBrief、CreativeVariant、CreativeCritique、UserSelectionFeedback、provider-free creative E2E、creative metrics skeleton 与 C5 real strong-profile creative dry-run `real_creative_e2e` evidence 已完成；真实 human acceptance/taste feedback 与 opportunity discovery 仍需长期数据。 |
| M9 Strategy/Evaluation Harness | Done Foundation++++ | StrategyEvaluationRecord、StrategyScorecard、BenchmarkSuite、StrategyComparisonReport、evaluation smoke、benchmark cases、trace fixtures、authorized live benchmark runner、rubric scoring、forbidden-claim checks、Phase C live evidence ingestion、capability-history、longitudinal-gain 与 C2 controlled variants 已完成；下一 frontier 是 longitudinal mini-program，而不是再盲目扩 profile 轮次。 |
| M10 Real Provider / Multi-Profile Worker Integration | Partial Real Workflow Lane | FakeProfileRunner、ProviderDiagnostic、redaction、typed authorization/evidence、Hermes profile subprocess runner、Wave4-1F 45/45 profile benchmark、real weak workflow worker、real teacher retry、real multi-worker dry-run seam 与 C5 real strong creative dry-run 已完成；真实多 worker project slice 仍未完成。 |
| M11 Real Workflow Execution / Promotion | Partial Real Workflow + Gated Promotion | CandidateFileWrite、ToyWorkflowExecutor、real-profile workflow runner、teacher retry、approval-gated promotion、branch-only real promotion smoke、draft PR fake adapter、release-candidate readiness 与 production safety/rollback gates 已完成；真实 GitHub PR creation、merge/deploy、production promotion/rollback 仍需显式授权。 |
| M12 Safety / Budget / Policy Governor | Done Foundation | PolicyGovernor、budget/risk/privacy gates、PolicyGovernorConfigLoader、HumanApprovalRecord、approval persistence、run-evidence、safe_to_retry/next_safe_action、handoff summary 与 action evidence 已完成。 |
| M13 Productization / Dashboard / API | Done Foundation+ | `feiyue-runs` CLI、RunCatalog、read-only API/dashboard、drill-down、read-only asset catalog/API/dashboard page、static HTML export、manifest SHA256、verifier、portable bundle、export-all pipeline 已完成；full review UI 尚未完整产品化。 |
| M14 Release Hardening / CI / Documentation | Partial Foundation+ | GitHub Actions CI、CI contract tests、compileall、pytest、static export-all smoke、provider-free example smoke、provider-free benchmark smoke、release checklist、contributing guide、architecture doc、docs index、static SVG architecture diagram、secret scan、Node24 actions runtime opt-in 已完成；full docs site 仍未完成。 |

## 19.1 Blueprint Status Sync v2：当前最准确阶段判断

旧状态矩阵已压缩：当前 Feiyue 约 **75–80%** 完成 Master Blueprint 的工程目标。它已经完成 provider-free safety foundation、真实 Hermes profile evidence、Phase C live evidence ingestion、real_creative_e2e creative dry-run、asset/review/promotion gates、capability-history、longitudinal-gain reporting、首个 longitudinal mini-program 与 productized real teacher-retry CLI；但仍不是完全自治的真实生产开发组织。

当前已证明的闭环是：

```text
Blueprint / Doctrine
→ typed schemas / trace contracts
→ sandbox verifier
→ anti-amnesia runtime
→ fake student/teacher candidate loop
→ workflow assets
→ real profile benchmark + real weak workflow + real teacher retry + real creative dry-run
→ Phase C live evidence ingestion into capability-history
→ policy governor + exact approval/action evidence
→ run evidence, asset catalog, CLI/API/dashboard/static export/bundle
→ GitHub Actions CI gate
```

尚未进入或尚未完成的主线是：

1. **longitudinal mini-program 已启动，下一步需要真实化**：首个 provider-free run `longitudinal-mini-program-20260614` 已证明 3-batch measurement path，teacher_call_rate_delta -1.0、retry_count_delta -2、repeat_error_count_delta -2；下一步应换成真实重复任务 batch，而不是再盲目扩 profile 到 5 轮。
2. **real multi-worker project slice**：真实多 profile 在一个小型真实项目任务中分工执行、teacher 只在失败时介入、verifier 决定成败。
3. **真实 GitHub PR / merge / deploy / rollback**：现有 fake draft PR、release-candidate readiness 与 production gates 已完成，但外部副作用仍需显式 credentials、approval、CI 与 rollback evidence。
4. **operator review UI v1**：CLI 很完整，Web UI 仍主要是 read-only/disabled skeleton；需要 proposal diff、approval/reject、asset/routing/capability review surfaces。
5. **creative role 长期人审指标**：C5 real strong-profile creative dry-run 已完成，但 accepted proposal rate、taste violation rate、cross-project opportunity discovery 需要持续积累。
6. **full docs site / release packaging**：CI 与 docs index 已有，完整 docs site、versioned releases 与 onboarding 仍可增强。

---

# 20. Completed Slice: M14 Provider-Free Example Project Smoke

## 已完成：M14 Provider-Free Example Project Smoke

### Rationale

现在 roadmap/status 已经同步，下一步最稳的是补一个 **committed provider-free example project**，让新模型、人类 reviewer 和 CI 都能从零运行 Feiyue 的最小可复现链路。这个 slice 不需要真实 provider、不读取或修改 Hermes 配置，也不会引入凭据。

它服务于 Master Blueprint 的位置：

- M11：真实 workflow execution 的 provider-free 可复现示例。
- M12：run evidence / handoff / policy evidence 的可复现样例。
- M13：CLI/API/static export 的真实 fixture 来源。
- M14：release hardening / example project / CI smoke。

### Objective

创建一个小型、可提交、无 secrets 的 `examples/provider-free-smoke/` 文档入口和 `feiyue_core.examples.provider_free_smoke` 可执行模块。该 smoke 会生成一个 fresh toy git repo，跑 provider-free workflow、teacher retry、verified promotion、run evidence handoff、static export、manifest verify、bundle、extract verify 的完整链路。

1. example 可以被现有 provider-free workflow 或 run-evidence export 管线消费。
2. 生成的 report/export/bundle 可验证。
3. example 不依赖网络、真实模型、真实 Hermes profile 或真实 credentials。

### Candidate Files

Create:

- `examples/provider-free-smoke/README.md`
- `packages/feiyue-core/feiyue_core/examples/__init__.py`
- `packages/feiyue-core/feiyue_core/examples/provider_free_smoke.py`
- `packages/feiyue-core/tests/test_provider_free_example_smoke.py`

Update:

- `.github/workflows/ci.yml`：加入 provider-free example smoke。
- `packages/feiyue-core/tests/test_ci_workflow.py`：覆盖 CI contract。
- `README.md`：加入 example usage。
- `docs/Feiyue-self-evolution-development-outline.md`：更新 M14 example 状态。

### Functional Acceptance

- example project 可在 fresh checkout 中运行 provider-free smoke。
- smoke 输出明确 `PROVIDER_FREE_EXAMPLE_SMOKE_OK` 稳定 marker。
- static export-all pipeline 可消费 example run evidence 并通过 manifest verification。
- README 中给出可复制命令。

### Code Quality & Cleanliness Acceptance

- provider-free、deterministic、no network。
- 不包含 API key、token、password、Authorization bearer 或连接串。
- 不修改真实 Hermes config。
- tests 覆盖 README contract、SDK smoke、CLI smoke 与 CI workflow contract。
- `python -m compileall -q feiyue_core`、`python -m pytest -q`、secret scan、GitHub Actions 均通过。

### Dependencies

- M11 provider-free workflow/report foundation。
- M12 run-evidence and export-all pipeline。
- M13 CLI/static export。
- M14 CI skeleton。

### Execution Notes

- 本 slice 已串联现有 M11/M12/M13 资产，未新增真实 provider、网络调用或 Hermes config 修改。
- CI 已加入 `Provider-free example smoke`，在 Ubuntu 上运行同一 module 并检查 run evidence、handoff、manifest、bundle 与 extracted manifest。

# 21. Completed Slice: M14 Benchmark CI Skeleton

## 已完成：M14 Benchmark CI Skeleton

### Objective

在 provider-free 前提下新增 deterministic benchmark runner/report artifact，固定未来真实 weak/strong model 对照的 JSON/Markdown 输出格式，并让 CI 运行 quick benchmark smoke。

### Created / Updated Files

Create:

- `packages/feiyue-core/feiyue_core/evaluation/benchmark_runner.py`
- `packages/feiyue-core/tests/test_benchmark_runner.py`

Update:

- `.github/workflows/ci.yml`：加入 `Provider-free benchmark smoke`。
- `packages/feiyue-core/tests/test_ci_workflow.py`：覆盖 benchmark CI contract。
- `README.md`：加入 benchmark smoke command。
- `docs/Feiyue-self-evolution-development-outline.md`：更新 M14 benchmark status。

### Output Contract

Benchmark JSON schema version: `feiyue.benchmark.v1`。

Quick benchmark emits:

- `suite_id: toy-benchmark-suite`
- `mode: quick`
- `cases_total: 3`
- `pass_rate: 0.6667`
- `teacher_call_rate: 0.3333`
- `average_cost: 2.5000`
- `average_latency: 18.0000`
- per-case exact match and token F1 metrics。

CLI marker: `BENCHMARK_SMOKE_OK`。

### Execution Notes

- Metrics are deterministic and provider-free: exact match and token-level F1.
- The quick dataset is tiny and checked into code, suitable for CI.
- The smoke writes both JSON and Markdown artifacts and asserts their existence in CI.

# 22. Completed Slice: M14 Docs / Release Checklist Skeleton

## 已完成：M14 Docs / Release Checklist Skeleton

### Objective

补齐 repo-level release checklist、contribution notes、architecture doc entry 与 README 索引，让 provider-free smokes、CI gates、secret scan 和 authorization boundaries 对 reviewer 可见且可测试。

### Created / Updated Files

Create:

- `docs/release-checklist.md`
- `CONTRIBUTING.md`
- `docs/architecture.md`
- `packages/feiyue-core/tests/test_docs_release_contract.py`

Update:

- `README.md`：索引 release checklist、contributing guide、architecture doc。
- `docs/Feiyue-self-evolution-development-outline.md`：更新 M14 docs/release status。

### Functional Acceptance

- Release checklist lists compileall、pytest、static export-all、provider-free example、provider-free benchmark、secret scan、remote CI 与 authorization boundaries。
- Contributing guide documents RED-GREEN-REFACTOR、provider-free defaults、no credentials、no Hermes config mutation。
- Architecture doc explains Human Creative Direction、Strong Spec / Teacher、Weak Worker / Student、Verifier、Policy Governor、Run Evidence、Static Export Bundle 与 Provider-Free Foundation。
- README links all three docs.

## Completed Parallel Waves: Wave 1 and Wave 2

### Wave 1 completed

- **M6 Asset Promotion Writer**：新增 asset proposal persistence、append-only review decisions 与 provider-free promotion gate。proposal 安全写入 `.hermes/asset-proposals/<proposal_id>/`，approved 之前不能 promotion，rejected fail closed；不写正式 skills/evals/templates。
- **M13 Asset Browser Expansion**：新增 read-only asset catalog、`GET /assets`、`GET /dashboard/assets` 与 static export `assets/index.html`；缺失目录返回空列表，输出相对路径和摘要，不 dump raw logs/secrets。
- **M14 Visual Architecture Diagram / Docs Site Stub**：新增 `docs/index.md` 与 `docs/assets/feiyue-architecture.svg`，并用 docs contract tests 覆盖链接、核心角色标签和无外部资源。

### Wave 2 completed

- **M9 Real Benchmark Preparation**：新增 benchmark case schema v1、provider-free trace fixtures 与 fixture strategy comparison contract；用于未来真实 weak/strong 对照的格式准备，不调用真实模型。
- **M10 Real Provider Plan Only**：新增 `docs/real-provider-integration-plan.md`，明确 fake tests → diagnostics/redaction → explicit authorization → isolated smoke → run evidence → rollback/abort gates；不执行真实 provider。
- **M11 Multi-round Fake Teacher Retry**：provider-free workflow 支持 bounded multi-round fake teacher retry；每轮记录 attempt evidence 和 teacher guidance，成功仍只由 verifier pass 决定。

### Wave 1/2 local verification

- `python -m pytest -q`：`469 passed`。
- `python -m compileall -q feiyue_core`：passed。
- `git diff --check`：passed。
- `STATIC_EXPORT_ALL_OK`、`PROVIDER_FREE_EXAMPLE_SMOKE_OK`、`BENCHMARK_SMOKE_OK`、`SECRET_SCAN_OK` 均已本地验证。

## Completed Parallel Wave: Wave 3

### Wave 3 completed

- **W3 Provider authorization/evidence + gated Hermes profile subprocess**：新增 typed authorization/evidence records、`.hermes/provider-runs/<run_id>/run-evidence.json` writer、global config mutation blocker 与 fake-tested subprocess adapter。真实 Hermes profile command 仍需 exact authorization；默认 fail closed。
- **W3 Gated live benchmark and multi-worker routing contracts**：新增 live benchmark replay/plan contracts 与 multi-worker routing / teacher escalation gate。replay mode provider-free；live mode 无授权时 blocked，有授权时也只生成计划，不自动联网执行。
- **W3 Promotion/rollback safety boundary**：新增 production promotion request / safety report，要求 verified report、exact human approval、branch allowlist、clean source repo、rollback plan/ref、post-promotion target-ref verification；外部生产 promotion 仍需独立授权。

### Wave 3 local verification

- `python -m pytest -q`：`469 passed`。
- `python -m compileall -q feiyue_core`：passed。
- `git diff --check`：passed。

### Wave 3 scope note

Wave 3 已完成真实 provider / Hermes profile / weak-vs-strong / teacher escalation / production promotion 的 **authorization-gated seams**，但没有执行真实 provider/network calls、没有读取凭据、没有修改 Hermes config、没有进行真实外部 production promotion。

## Completed Parallel Wave: Wave 4-1 Real Profile Benchmark Checkpoint

### Wave4-1 completed

- **W4-1B Real matrix**：authorized live benchmark runner 已实际调用 5 个 Hermes profiles，完成弱/中/强 profile smoke matrix，并写入 redacted JSON/Markdown evidence。
- **W4-1C Rubric scoring**：新增 required concepts、forbidden claims、quality score 与 negation-aware forbidden-claim handling，避免 `no evidence found` 误触发 forbidden claim。
- **W4-1D Hard rubric matrix**：补充更难 rubric cases，并将 nested Hermes profile 调用限制为 toolless `--ignore-rules --max-turns 1 -t ''`，防止 benchmark subject 自己作为 agent 修改 repo。
- **W4-1E Gemini reliability upgrade**：Gemini strong profile 实际模型切到 `gemini-3.1-pro`，可靠性诊断无 timeout / empty output。
- **W4-1F Multi-round reliability sweep**：完成 45/45 real Hermes profile calls，覆盖 weak/mid/strong profiles；DeepSeek Flash 当前是最稳低成本 worker 候选，Gemini 3.1 Pro 是可用但更慢更贵的 strong/reviewer 候选。

### Wave4-1 local verification

- `python -m pytest -q`：`664 passed`。
- `python -m compileall -q feiyue_core`：passed。
- `git diff --check`：passed。
- Latest remote CI for status-sync predecessor: success.

### Wave4-1 scope note

Wave4-1 证明 **M10 real profile benchmark lane usable**：真实 Hermes profiles 能被安全、可预算、可脱敏地调用，并能产出 quality/latency/reliability evidence。它尚未证明真实 workflow worker execution；**M10 real multi-worker execution lane not yet implemented**，下一步必须把 profile runner 接到 M11 sandbox workflow，而不是继续只跑 prompt benchmark。

## Completed Slice: Wave4-2B Real Profile Workflow Smoke

### Wave4-2B completed

- Marker: `WAVE4_2B_REAL_PROFILE_WORKFLOW_OK`。
- Profile: `feiyue-weak-deepseek-flash`。
- provider_call_count: 1。
- workflow_status: verified。
- verification_passed: true。
- promotion_ready: true。
- source checkout remained clean; the real profile output was parsed into `CandidateFileWrite` and executed only through the sandboxed `ProfileWorkflowBridge` / `ToyWorkflowExecutor` path.

### Wave4-2B scope note

Wave4-2B proves the first real worker-profile bridge: TaskContract → real weak Hermes profile JSON candidate writes → sandbox patch → pytest verifier → verified workflow report. It does not yet include real teacher escalation, multi-worker orchestration, or real-project production promotion.

## Completed Slice: Wave4-2C Real Teacher Retry Smoke

### Wave4-2C completed

- Marker: `WAVE4_2C_REAL_TEACHER_RETRY_OK`。
- Weak worker profile: `feiyue-weak-deepseek-flash`。
- Teacher profile: `feiyue-strong-gpt55`。
- provider_call_count: 3。
- initial_workflow_status: needs_teacher。
- initial_verification_passed: false。
- final_workflow_status: verified。
- final_verification_passed: true。
- retry_performed: true。
- teacher_guidance_events: 1。
- promotion_ready: true。
- source checkout remained clean; first real weak-worker candidate failed verifier and produced a bug dossier, real strong-teacher guidance was recorded as an audit event, and the real weak-worker retry passed only through the sandbox verifier path.

### Wave4-2C scope note

Wave4-2C proves the first real teacher retry bridge on a controlled toy workflow: real weak worker failure → verifier-backed bug dossier → real strong teacher guidance → real weak worker retry → verifier-backed success. It does not yet include multi-worker orchestration or real-project production promotion.

## Completed Slice: Wave4-2D Productized Real Profile Workflow Runner

### Wave4-2D completed

- Added `RealProfileWorkflowRunner` as the reusable SDK boundary for worker profile calls, optional teacher escalation, retry, verifier-backed workflow reports, dry-run semantics, source cleanliness checks, and redacted `.hermes/workflow-smokes/<run_id>/` evidence.
- Added `RealProfileWorkflowAuthorization` with explicit scopes, max_profile_calls, dry_run_only, and real-project allowance flags.
- Added `feiyue-runs workflow-smoke <run_id>` for JSON inspection of productized workflow-smoke evidence.
- Fake-first contracts cover worker failure → teacher guidance → worker retry → verified report, provider_call_count: 3, retry audit event, and no source mutation.

## Completed Slice: Wave4-3A Real-Project Dry-run Boundary

### Wave4-3A completed

- Added a real-project-style dry-run/no-promotion contract through `RealProfileWorkflowRunner`.
- dry_run_only: true。
- promotion_attempted: false。
- A verifier-backed workflow can become promotion_ready, but the productized runner still does not call promotion APIs or mutate the source checkout.
- This creates the safe entry point for evaluating real project tasks before Wave4-3B human-approved promotion.

## Completed Slice: Wave4-3B-1 / Wave4-3B-2 Approval-gated Promotion

### Wave4-3B-1 completed

- Added `RealProfilePromotionApproval` as the exact approval record for promoting a verified real-profile dry run.
- Approval binding covers run_id, task_id, changed_files, target_branch, source_commit_sha, workflow_report_hash, approver, approved_at, and approved_action.
- `compute_workflow_report_hash` pins approval to the verifier-backed dry-run report rather than model self-report.

### Wave4-3B-2 completed

- Added `RealProfilePromotionGate` as the fail-closed promotion boundary.
- Missing approval returns `missing_promotion_approval`, promotion_attempted: false, approval_applies: false, and writes `promotion-evidence.json` without branch side effects.
- Exact approval returns `promotion_approval_applies`, then calls the existing verifier-gated promotion path into an isolated target branch.
- Added `feiyue-runs workflow-promotion <run_id>` for promotion evidence inspection.

### Wave4-3B-3 completed

- Executed low-risk real-project branch-only promotion smoke using run_id `wave4-3b-3-low-risk-real-project-promotion-smoke-v3`.
- Dry-run verifier passed with command `python -m pytest packages/feiyue-core/tests/test_cli.py::test_runs_cli_shows_workflow_promotion_evidence -q`.
- Exact approval promoted docs-only candidate `docs/wave4-3b-promotion-smoke.md` into target branch `feiyue/w43b-approved-promotion-smoke`.
- Promoted commit: `66f6055fec5a90f192b78bc6719e6938d46ba053`.
- Remote branch verification passed: local target branch head matched origin.
- Main checkout remained clean after promotion and push.

### Wave4-3B remaining scope

The approval gate and branch-only real-project promotion smoke exist. The next safe step is Wave4-3C: add an explicit approval CLI/API flow so approval records are generated/audited by the product surface instead of test/smoke scripts.

## Completed Slice: Wave4-3C Productized Approval CLI

### Wave4-3C completed

- Added `feiyue-runs approve-promotion <run_id>` to generate persisted `approval.json` under `.hermes/workflow-promotions/<run_id>/` from dry-run evidence.
- Added `feiyue-runs promote-approved <run_id>` to read persisted approval evidence, recover candidate writes from workflow smoke stdout, and call `RealProfilePromotionGate`.
- Added CLI contract test `test_runs_cli_approves_and_promotes_verified_dry_run` covering approval creation, approval hashing, branch promotion, and clean source checkout.
- Executed real-project branch-only smoke run_id `wave4-3c-productized-approval-cli-smoke-v2`.
- Productized CLI smoke target branch: `feiyue/w43c-productized-approval-cli-smoke`.
- Productized CLI smoke promoted commit: `d8370868a992320590d23865b2e77099b57930ad`.
- Remote branch verification passed and main checkout remained clean.

### Wave4-3C remaining scope

The productized CLI path exists for approval creation and promotion execution. The next safe slice is Wave4-4: feed real execution/promotion evidence into capability metrics and routing updates without allowing automatic mutation of routing tables.

## Completed Slice: Wave4-4 Capability Metrics Feedback Loop

### Wave4-4 completed

- Added `CapabilityFeedbackAggregator` to collect `.hermes/workflow-smokes/*/evidence.json` and `.hermes/workflow-promotions/*/promotion-evidence.json` into per-profile metrics.
- Metrics include workflow_runs, verified_runs, needs_teacher_runs, blocked_runs, teacher_guidance_events, provider_call_count, promotion_attempts, promoted_runs, verification_rate, promotion_rate, and teacher_or_blocked_rate.
- Added audit-only recommendations: `consider_promotion`, `keep_review`, and `keep_routing`; every recommendation records `mutates_routing_table: false`.
- Added `feiyue-runs capability-feedback --write-report` to print JSON and persist `.hermes/capability-feedback/latest.json` plus `.hermes/capability-feedback/latest.md`, with `routing_table_mutated: false`.
- Added `.hermes/capability-feedback/` to `.gitignore`; reports are local evidence artifacts, not committed source.
- Capability feedback intentionally does not rewrite `.hermes/model-routing.yaml`; routing table changes remain human-reviewed follow-up work.

### Wave4-4 remaining scope

The current feedback loop is audit-only. Wave4-4B adds a human-reviewed route-update proposal file that can be reviewed before any routing table mutation.

## Completed Slice: Wave4-4B Human-reviewed Routing Proposal

### Wave4-4B completed

- Added `RoutingProposalGenerator` to load `.hermes/capability-feedback/latest.json` and `.hermes/model-routing.yaml`.
- Added proposal hashing: every proposal records `source_feedback_hash` and `current_routing_hash` so later approvals can bind to exact evidence and exact routing state.
- Added `RoutingUpdateProposal` and `RoutingProposalChange` with `requires_human_approval: true` and `routing_table_mutated: false`.
- Added `feiyue-runs routing-proposal --proposal-id <id> --write-proposal` to print JSON and persist `.hermes/routing-proposals/<proposal_id>/proposal.json` plus `proposal.md`.
- Added fail-closed missing-feedback behavior: the CLI exits non-zero and leaves `.hermes/model-routing.yaml` unchanged when `.hermes/capability-feedback/latest.json` is absent.
- Added `.hermes/routing-proposals/` to `.gitignore`; proposals are local review artifacts, not committed source.
- Smoke run `wave4-4b-routing-proposal-smoke` generated a human-reviewed proposal with `requires_human_approval: true`, `routing_table_mutated: false`, and unchanged routing hash.

### Wave4-4B remaining scope

Wave4-4B only proposes routing changes. Wave4-4C adds exact approval for a proposal hash/current routing hash before applying any `.hermes/model-routing.yaml` mutation.

## Completed Slice: Wave4-4C Approval-gated Routing Apply

### Wave4-4C completed

- Added `RoutingProposalApproval` with exact bindings: proposal_id, approved_action, source_feedback_hash, current_routing_hash, recommended_changes_hash, approver, timestamp, and reason.
- Added `RoutingApplyGate` with fail-closed behavior for missing approval, proposal mismatch, action mismatch, feedback hash mismatch, routing hash mismatch, recommended changes hash mismatch, and current routing drift.
- Added `approve-routing-proposal` and `apply-approved-routing` CLI commands.
- Successful apply writes `.hermes/model-routing.yaml` only after exact approval and records `routing_proposal_approval_applies` in `apply-evidence.json`.
- Blocked apply writes audit evidence with `missing_routing_proposal_approval` and leaves routing unchanged.
- Smoke run `wave4-4c-routing-apply-smoke` verified the productized CLI path: feedback -> proposal -> approval -> apply, mutated a temporary routing table worker primary to `steady-4c`, then cleaned local artifacts.

### Wave4-4C remaining scope

Wave4-4C can apply exact approved routing changes. Wave4-5 hardens multi-worker orchestration on top of those approved project-local routes without executing providers or mutating global Hermes config.

## Completed Slice: Wave4-5 Multi-worker Orchestration Hardening

### Wave4-5 completed

- Added `MultiWorkerOrchestrationPlanner` to load `.hermes/model-routing.yaml`, discover latest applied routing evidence, and create provider-free multi-worker route plans.
- Added `MultiWorkerOrchestrationPlan` evidence with selected route source, `routing_apply_evidence_loaded`, route reason codes, and explicit safety flags.
- Added `feiyue-runs multi-worker-plan --plan-id <id> --task-id <id> --capability <capability> --risk-level <level> --write-plan` to print JSON and persist `.hermes/multi-worker-plans/<plan_id>/plan.json` plus `plan.md`.
- Added fail-closed missing routing table behavior with no provider execution and no routing/global config mutation.
- Teacher escalation remains guarded by the existing multi-worker escalation gate; repeated-failure plans block with `teacher_escalation_authorization_missing` unless explicit authorization is supplied.
- Added `.hermes/multi-worker-plans/` to `.gitignore`; generated plans are local evidence artifacts.
- Smoke run `wave4-5-multi-worker-orchestration-smoke` selected `steady-4c` from the approved Wave4-4C route with `routing_apply_evidence_loaded`, `provider_execution_requested: false`, and `global_hermes_config_mutated: false`.

### Wave4-5 remaining scope

Wave4-5 is a provider-free planning seam. Wave4-5B connects approved multi-worker plans to dry-run workflow execution with exact local authorization, while keeping promotion and global config mutation out of scope.

## Completed Slice: Wave4-5B Approved Multi-worker Workflow Dry-run Orchestrator

### Wave4-5B completed

- Added `MultiWorkerWorkflowDryRunAuthorization` with exact bindings for plan_id, task_id, approved_action, selected worker profile ids, scopes, dry_run_only, and max_profile_calls.
- Added `MultiWorkerWorkflowDryRunOrchestrator` to consume a `MultiWorkerOrchestrationPlan`, validate exact authorization, and delegate only authorized selected-worker dry-runs to `RealProfileWorkflowRunner`.
- Added fail-closed gates for missing authorization, mismatched plan/task/action/worker ids, non-dry-run authorization, exhausted profile-call budget, and plans that are not `selected`.
- Added `.hermes/multi-worker-workflows/<run_id>/evidence.json` plus `report.md` evidence with `multi_worker_plan_authorization_applies`, `dry_run_only: true`, `promotion_attempted: false`, and `global_hermes_config_mutated: false`.
- Added `feiyue-runs multi-worker-workflow <run_id>` to inspect persisted multi-worker workflow dry-run evidence.
- Added `.hermes/multi-worker-workflows/` to `.gitignore`; generated workflow dry-run evidence remains local.
- Smoke run `wave4-5b-approved-multi-worker-dry-run-smoke` selected `steady-4c`, executed one fake profile dry-run, verified the sandbox workflow, left the source checkout unchanged, and cleaned local artifacts.

### Wave4-5B remaining scope

Wave4-5B proves the approved-plan-to-dry-run execution seam. Wave4-5C productizes approval CLI and persisted plan/workflow authorization evidence for multi-worker dry-runs, still before any real provider or teacher escalation smoke.

## Completed Slice: Wave4-5C Productized Multi-worker Dry-run Approval CLI

### Wave4-5C completed

- Added persisted multi-worker dry-run approval evidence at `.hermes/multi-worker-plans/<plan_id>/approval.json`.
- Added `approve-multi-worker-dry-run --plan-id <id> --approved-by <name> --approval-id <id> --reason <reason>` to create exact approval for `execute_multi_worker_workflow_dry_run` from a persisted plan.
- Added `run-approved-multi-worker-dry-run --plan-id <id> --run-id <id> ... --fake-worker-response-json <json>` to execute an approved provider-free fake-worker dry-run via CLI.
- The productized CLI flow still keeps `dry_run_only: true`, `promotion_attempted: false`, and never mutates global Hermes config.
- Smoke run `wave4-5c-productized-dry-run-approval-smoke` created persisted approval, ran the approved `steady-4c` fake-worker dry-run, verified the sandbox workflow, and emitted `WAVE4_5C_PRODUCTIZED_DRY_RUN_APPROVAL_OK`.

### Wave4-5C remaining scope

Wave4-5C was still fake-first/provider-free for execution. The parallel A-F completion added the remaining gated foundations while preserving explicit authorization boundaries for live providers and production side effects.

## Completed Parallel Lanes: Remaining A-F Foundations

### Lane A / Wave4-5D completed

- Added the authorization-gated Hermes profile runner seam for selected-worker multi-worker dry-runs.
- `run-approved-multi-worker-dry-run` can select `--profile-runner fake|hermes`; fake remains default and Hermes mode requires a persisted authorized provider run record.
- Missing/mismatched Hermes authorization blocks before any profile call and writes dry-run-safe blocked evidence.

### Lane B completed

- Added `MultiWorkerTeacherEscalationAuthorization` for separate teacher escalation/retry approval.
- Multi-worker dry-run now fails closed with `teacher_escalation_authorization_missing` when verifier failure would require a teacher but authorization is absent.
- Exact fake teacher authorization permits teacher guidance plus worker retry evidence while keeping dry_run_only: true and promotion_attempted: false.

### Lane C completed

- Added `CapabilityHistoryCollector` and `feiyue-runs capability-history --write-report`.
- Longitudinal history reads workflow-smoke, workflow-promotion, and multi-worker workflow evidence and writes `.hermes/capability-history/history.jsonl`, `latest.json`, and `latest.md`.
- Reports preserve `routing_table_mutated: false`; routing learning remains human-reviewed.

### Lane D completed

- Added sandboxed curator asset promotion into project-local `.hermes/assets`, `.hermes/lessons`, `.hermes/evals`, and `.hermes/task-templates` allowlisted paths.
- Promotion evidence records proposal id, target path, content hash, rollback snapshot, promoted flag, and reason codes.
- Missing/rejected approval, path escape, duplicate content, and missing rollback reference all fail closed; rollback simulation restores or deletes sandbox assets.

### Lane E completed

- Added read-only review inbox aggregation for pending routing proposals, workflow promotions, multi-worker plan approvals/runs, and asset proposals.
- Added `feiyue-runs review-inbox --format json`; every item records `mutates_state: false`.
- No approval/apply/run/promotion side effects are performed by the inbox.

### Lane F completed

- Added local-only promotion lifecycle contracts for PR-plan evidence and rollback simulation.
- PR plans record `external_pr_created: false`; rollback evidence records local verifier-backed rollback attempts.
- Missing promotion evidence, dirty repos, missing rollback refs, non-allowlisted target branches, and non-promoted evidence fail closed.

### Remaining scope after A-F

The repo now has the gated seams/foundations for all A-F lanes. Batch1 adds the operator-facing preparation layer before any live side effects.

## Completed Parallel Batch 1: Live Prep, Longitudinal Gain, Review UI, Operator Docs

### Batch1 Live A/B prep completed

- Added `feiyue-runs live-smoke-plan --write-plan` and `LiveSmokePlanBuilder` for exact-authorized live A/B smoke readiness checks without live calls.
- Plans validate selected worker, optional teacher, required approval/evidence paths, dry_run_only: true, promotion disabled, budget/timeout, verifier command, and fail-closed reason codes.
- Missing or mismatched approvals remain blocked with provider_call_count: 0, global_hermes_config_mutated: false, and production_side_effects_enabled: false.

### Batch1 longitudinal gain completed

- Added `feiyue-runs longitudinal-gain --write-report` and longitudinal gain evaluation over capability history.
- Reports compute before/after pass-rate deltas, teacher-call-rate deltas, optional cost/latency deltas, confidence labels, and insufficient-data states.
- Reports preserve `routing_table_mutated: false`; route learning remains human-reviewed.

### Batch1 review UI completed

- Added read-only `/review-inbox` JSON and `/dashboard/review-inbox` HTML surfaces.
- Static export now includes `review-inbox/index.html` and bundle/manifest verification covers it.
- The UI renders item_type, recommended_action, and mutates_state: false without approval POST forms or write controls.

### Batch1 operator docs completed

- Added `docs/operator-guide.md`, `docs/approval-runbooks.md`, `docs/live-smoke-playbook.md`, `docs/security-boundaries.md`, and `docs/rollback-guide.md`.
- Docs index and README link the new runbooks.
- Docs contract tests assert exact authorization, no global Hermes config mutation, dry_run_only: true, production PR/promotion disabled by default, rollback evidence, and review inbox read-only boundaries.

### Remaining scope after Batch1

Serial Live A/B smoke has now executed under exact authorization, and the first curator live asset loop has promoted a project-local lesson from the verified Live B teacher-retry evidence. Remaining live/production work is still deliberately authorization-gated: broader asset promotion for regression eval/task-template patches, GitHub draft PR creation, production promotion/rollback, longitudinal improvement measurement after asset reuse, and creative-to-execution E2E require exact approvals and configured credentials.

## Completed Curator Live Asset Loop

- Added `feiyue-runs curator-live-proposal --write-proposal` to convert verified multi-worker Live B evidence into a review-required `DistillationProposal` with lesson, regression_eval, and task_template patches.
- Added `feiyue-runs promote-curator-asset` to approve and promote one project-local `.hermes` asset patch with rollback evidence, using existing `AssetPromotionStore` fail-closed gates.
- Ran the live loop on `live-b-real-teacher-retry-smoke-20260614`, producing proposal `asset-live-b-real-teacher-retry-20260614` and promoting `.hermes/lessons/asset-live-b-real-teacher-retry-20260614.md`.
- The loop requires verified dry-run evidence with teacher-guided retry, first verifier failure, final verifier pass, `dry_run_only: true`, `promotion_attempted: false`, `global_hermes_config_mutated: false`, and clean source evidence.

## Recommended Next Slice

Wave5-1 through Wave5-6 are now implemented and locally smoke-verified. Remaining real-world actions are deliberately operational approvals rather than missing code paths: optional real Hermes profile calls for broader live matrices, optional real GitHub draft PR creation, and optional production promotion/merge/deploy require exact credentials, approval records, CI success, and rollback evidence.

## Completed Wave5 Run-to-End

- **Wave5-1 Asset Reuse / Longitudinal Gain Smoke**：added `asset-reuse-smoke`, project-local lesson loading, deterministic lesson injection, longitudinal-compatible before/after metrics, and actual smoke `wave5-1-asset-reuse-smoke-20260614` with lesson_loaded true, error_prevented true, teacher_call_required false.
- **Wave5-2 Distillation Bundle Promotion**：added patch-id/patch-index promotion for lesson, regression_eval, and task_template patches with per-patch rollback evidence. The actual Live B bundle promoted regression_eval and task_template; the lesson patch was safely blocked as duplicate because the original lesson asset already existed.
- **Wave5-3 Real Multi-worker Dry-run Evidence Seam**：added exact-authorized real multi-worker dry-run evidence under `.hermes/real-multi-worker-runs/`, capability-history ingestion, and actual fake-runner smoke `wave5-3-real-multi-worker-smoke-20260614` with status verified, provider_call_count 1, promotion_attempted false, and global_hermes_config_mutated false.
- **Wave5-4 Draft PR Mode**：added local draft PR plan, exact `create_draft_pr` approval, fake adapter creation evidence, review inbox surface, and fail-closed tests. It never auto-merges and records external_pr_created false in fake mode.
- **Wave5-5 Creative-to-Execution E2E**：added provider-free `creative-e2e-smoke`, deterministic seed → variants → critique → selected variant → PRD/spec → task contract → verified workflow evidence, and actual smoke `wave5-5-creative-e2e-smoke-20260614` with curator_proposal_ready true.
- **Wave5-6 Release Candidate / Production Safety Gate**：added release-candidate plan, production approval, readiness verification, CI/rollback/post-promotion-plan requirements, and fake-first readiness smoke with status ready, dry_run true, and production_mutated false.

## Completed Phase B Productization Batch

- **B1 Write-side review UI skeleton**：`/dashboard/review-inbox` and static `review-inbox/index.html` now show disabled approval-gated action buttons (`button disabled`, no forms, no POST routes). The skeleton exposes intended actions while preserving `mutates_state: false` and no provider/global-config mutation.
- **B2 CLI reference generator**：added `feiyue-runs cli-reference --output <path>` and generated `docs/cli-reference.md` from the productized command registry, covering evidence inspection, learning loops, multi-worker dry-runs, and approval-gated operations.
- **B3 Semantic reviewer skeleton**：added provider-free `semantic-review` evidence over required/forbidden term rubrics. It writes `.hermes/semantic-reviews/<review_id>/evidence.json`, records `provider_call_count: 0`, and stays dry-run-only.
- **B4 Creative metrics skeleton**：added append-only `.hermes/creative-metrics/decisions.jsonl` plus `creative-metrics-record` for human accepted/rejected/deferred proposal decisions, acceptance rate, and taste-violation rate. It records `provider_call_count: 0` and `mutates_state: false`.

### Completed Longitudinal Mini-Program

- **Blueprint Status Sync v2**：compressed the current matrix against Master Blueprint into a 75–80% engineering-completion assessment, clarifying that Phase C live evidence ingestion, `real_creative_e2e`, capability-history, longitudinal-gain, approval gates, and release-readiness seams are complete while real multi-worker project execution and production side effects remain gated.
- **Longitudinal Mini-Program 20260614**：added `LongitudinalMiniProgramRunner` and `feiyue-runs longitudinal-mini-program --run-id longitudinal-mini-program-20260614 --write-report`. The provider-free 3-batch run persisted `.hermes/longitudinal-mini-programs/longitudinal-mini-program-20260614/evidence.json`, recorded baseline → lesson_injected → routing_adjusted phases, and ingested 3 `longitudinal_mini_program` records into capability-history.
- **4A Productized real teacher retry**：added `SequencedHermesProfileRunner` and `feiyue-runs run-approved-multi-worker-teacher-retry` so the real worker initial call, real teacher guidance call, and real worker retry call are bound to three exact `AuthorizedProviderRunRecord` files instead of a temporary script. Real Feiyue repo smoke `real-repo-4a-productized-teacher-retry-dry-run` verified `feiyue-mid-deepseek-pro` + `feiyue-strong-gpt55` with provider_call_count `3`, retry_performed `true`, teacher_guidance_events `1`, `dry_run_only: true`, `promotion_attempted: false`, and `global_hermes_config_mutated: false`.
- **4C true multi-student planner design**：added `docs/true-multi-student-planner-design.md`, explicitly separating the current one student + teacher retry lane from future multiple student workers with assignment scopes, merge strategy, conflict handling, and combined verifier evidence. The design states that promotion remains out of scope for the first true multi-student slice.
- **5A–5B true multi-student dry-run productization**：added `MultiStudentDryRunExecutor`, exact `MultiStudentDryRunApproval`, assignment hashing, `reject_on_conflict` merge behavior, `.hermes/multi-student-workflows/<run_id>/` evidence, and CLI commands `approve-true-multi-student-dry-run`, `run-approved-true-multi-student-dry-run`, and `true-multi-student-workflow`.
- **5C–5D real Feiyue repo smokes**：`real-repo-5c-one-real-one-fake-dry-run` verified one real + one fake student assignment; `real-repo-5d-all-real-multi-student-dry-run` verified `feiyue-mid-deepseek-pro` + `feiyue-strong-gpt55` as distinct real student assignments with provider_call_count `2`, conflict_files `[]`, `dry_run_only: true`, `promotion_attempted: false`, `global_hermes_config_mutated: false`, and clean source worktrees.
- **6A approval-gated PR plan bridge**：added `create_multi_student_pr_plan` to convert verified true multi-student evidence into a local-only PR plan. The 6A smoke exact-approved the 5D plan and emitted fake draft PR evidence with approval_applies `true`, external_pr_created `false`, auto_merge `false`, and mutates_production `false`.
- **6B GitHub draft PR adapter smoke**：added `GitHubDraftPRAdapter` and `create-approved-draft-pr --adapter github`. Real smoke created draft PR #2 (`https://github.com/sinonchum/Feiyue/pull/2`) from branch `feiyue/6b-draft-pr-smoke` to `main`; PR verification showed isDraft `true`, state `OPEN`, autoMergeRequest `null`, checks passed, and no merge/deployment/production mutation.
- **7A–7D real feature PR readiness chain**：7A ran `real-repo-7a-true-multi-student-feature-dry-run` with `feiyue-mid-deepseek-pro` + `feiyue-strong-gpt55`, provider_call_count `2`, conflict_files `[]`, combined verifier passed, `dry_run_only: true`, and no promotion/global mutation. 7B created real feature Draft PR #3 (`https://github.com/sinonchum/Feiyue/pull/3`) from `feiyue/7b-real-feature-pr`; 7C attached provider-free semantic/safety review `wave7-7c-pr3-semantic-safety-review` to the PR body via GitHub REST PATCH; 7D generated `wave7-7d-pr3-merge-readiness-evidence-only` with PR checks passed, isDraft `true`, autoMergeRequest `null`, merge_performed `false`, auto_merge_enabled `false`, deploy_performed `false`, and production_mutated `false`. The remaining frontier is the real multi-worker project slice beyond evidence-only readiness: explicitly approved merge/rollback/deploy operations.
- **8A merge/rollback/deploy readiness design**：added `MergeRollbackDeployReadinessPlan` plus CLI commands `merge-rollback-deploy-readiness-plan`, `approve-merge-rollback-deploy-readiness`, and `verify-merge-rollback-deploy-readiness`. Smoke `wave8-8a-pr3-readiness-design` bound PR #3 7D readiness evidence, rollback plan, deploy plan, and post-merge verifier into an exact-approved evidence-only readiness report with status `ready`, approval_applies `true`, merge_performed `false`, auto_merge_enabled `false`, deploy_performed `false`, and production_mutated `false`.
- **8B approved merge execution smoke**：added `MergeExecutionApproval`, `MergeExecutionAdapterResult`, `approve-merge-execution`, and `execute-approved-merge`. Smoke `wave8-8b-pr3-fake-merge-smoke` ran the fake adapter against `wave8-8a-pr3-readiness-design`, producing `fake_adapter_simulated_merge_only` with simulated_merge_performed `true`, merge_performed `false`, external_side_effect_performed `false`, deploy_performed `false`, and production_mutated `false`; the GitHub adapter inspection returned blocked with `pr_is_draft` for PR #3 before any merge/API side effect.
- **8C PR ready-for-review transition gate**：added `PRReadyForReviewApproval`, `PRReadyForReviewAdapterResult`, `approve-pr-ready-for-review`, and `transition-pr-ready-for-review`. Smoke `wave8-8b-pr3-fake-merge-smoke` recorded `fake_adapter_simulated_ready_for_review_only` with simulated_ready_for_review_performed `true`, ready_for_review_performed `false`, external_side_effect_performed `false`, merge_performed `false`, deploy_performed `false`, and production_mutated `false`; the GitHub adapter blocked with `external_pr_mutation_not_authorized`, preserving PR #3 as Draft/Open until an explicit external PR mutation approval is given.
- **8D real PR ready-for-review transition**：added `PRReadyForReviewExternalMutationApproval`, `approve-pr-ready-for-review-external-mutation`, and `transition-pr-ready-for-review --adapter github --perform-external-mutation`. Approval `wave8-8d-pr3-real-ready-for-review-approval` performed the real GitHub Draft-to-ready transition for PR #3 only and persisted `github_pr_marked_ready_for_review` evidence with isDraft `false`, ready_for_review_performed `true`, external_side_effect_performed `true`, merge_performed `false`, autoMergeRequest `null`, deploy_performed `false`, and production_mutated `false`.
- **8E non-Draft merge-readiness refresh**：added `RefreshedMergeReadinessEvidence` and `refresh-merge-readiness`. Smoke `wave8-8e-pr3-nondraft-merge-readiness-refresh` inspected non-Draft PR #3 and checks, then persisted status `ready_for_human_merge_review` with `pr_non_draft_checks_passed_merge_readiness_refreshed`, isDraft `false`, checks_passed `true`, merge_performed `false`, auto_merge_enabled `false`, deploy_performed `false`, and production_mutated `false`.
- **8F-1 pre-merge final audit**：added `PreMergeFinalAudit` and `pre-merge-final-audit`. Smoke `wave8-8f1-pr3-pre-merge-final-audit` generated an `approval_requested` artifact for PR #3 with `pre_merge_final_audit_passed_approval_request_ready`, merge_approval_request_ready `true`, head SHA `3f6537124c4bf353daf09cf2384d8eceb30b6a86`, changed files `packages/feiyue-core/feiyue_core/workflow/wave7_feature_marker.py` and `packages/feiyue-core/tests/test_wave7_feature_marker.py`, merge_performed `false`, auto_merge_enabled `false`, deploy_performed `false`, and production_mutated `false`.
- **8F-2 real merge execution**：added `RealMergeExecutionApproval`, `RealMergeExecutionEvidence`, `approve-real-merge`, and `execute-approved-real-merge`. Approval id `wave8-8f2-pr3-real-merge-approval` bound action `execute_real_github_merge`, 8F-1 audit hash, PR #3, head SHA, target branch, and merge_method `squash`; execution status `merged` recorded `real_merge_execution_approval_applies` and `github_pr_merged`, merge commit `7615eff150594a6d42c89ba5b309921d9d712ebb`, auto_merge_enabled `false`, deploy_performed `false`, and production_mutated `false`.
- **8G post-merge no-deploy handoff**：added `PostMergeVerificationHandoff` and `post-merge-handoff`. Smoke `wave8-8g-pr3-post-merge-no-deploy-handoff` recorded post-merge verification status `handoff_ready`, `post_merge_verification_passed`, `no_deploy_release_handoff_ready`, release_handoff_ready `true`, local_test_baseline `664 passed`, CI run `27510205254`, deploy_performed `false`, and production_mutated `false`.
- **8H / Wave 9 planning**：saved `docs/plans/wave9-real-multi-worker-project-slice-plan.md`, defining the next real multi-worker project slice, immediate Wave9-2 task-pack step, dry_run_only: true, promotion_attempted: false, global_hermes_config_mutated: false, no-deploy scope, and production_mutated `false`.
- **Wave9-2 real multi-worker task pack**：added `Wave9TaskPack`, `Wave9TaskAssignment`, and `wave9-task-pack`. Smoke `wave9-2-real-multi-worker-task-pack` persisted provider-free task-pack evidence with provider_call_count `0`, dry_run_only: true, promotion_attempted: false, global_hermes_config_mutated: false, and production_mutated `false`.
- Observed measurement deltas: pass_rate_delta `+1.0`, teacher_call_rate_delta `-1.0`, retry_count_delta `-2`, repeat_error_count_delta `-2`, with `provider_call_count: 0`, `dry_run_only: true`, `promotion_attempted: false`, `production_mutated: false`, and `global_hermes_config_mutated: false`.

### Phase B local verification

- `python -m pytest -q`：`664 passed`。
- New targeted contracts cover review UI disabled actions, CLI reference generation, provider-free semantic review evidence, and creative acceptance/taste metrics.
- Phase C remains explicit-authorization-gated for external PR/merge/deploy/production promotion and larger real-provider matrices.
