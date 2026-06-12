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
- 当前完整测试：`321 passed`
- 最新开发状态：已具备 schemas、sandbox、verifier、recovery runtime、candidate/feedback/teacher toy loop、iteration trace replay、fallback resume prompt、provider-free resume demo、M5 workflow assets、M6 curator/distillation、M7 capability、M8 creative、M9 evaluation，以及 M10 safe provider/profile integration foundation、M11 provider-free toy workflow execution / fake teacher-guided retry foundation。

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
- Product dashboard / API。

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
- source repo clean guarantee：当前 M11 foundation 不直接修改 source repo，promotion 仍是后续显式步骤。
- sandbox rollback：worktree sandbox 在 run 后被清理。

尚未完成且后续需要：

- 真实 worker/provider 生成 patch。
- 多轮 teacher repair loop（当前只支持 provider-free 单次 fake teacher retry）。
- verified patch promotion 到目标 branch/worktree。
- worker/teacher markdown reports 的持久化。

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
- worker/teacher persisted reports（后续）。
- source repo clean guarantee 保持。

## Code Quality & Cleanliness Acceptance

- 所有 mutating operations 在 sandbox/worktree 中执行。
- promotion readiness 需要 verifier pass。
- sandbox rollback 测试覆盖。
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

| Milestone | 状态 | 说明 |
|---|---:|---|
| M0 Doctrine / Blueprint | Done | Master Blueprint 已写入并链接 |
| M1 Core Schemas | Done | schemas / trace contracts 已测 |
| M2 Local Execution / Verifier | Done MVP | sandbox/verifier/local loop 已有 |
| M3 Resilient Runtime | Done Foundation | anti-amnesia 基础闭环完成 |
| M4 Candidate / Feedback / Teacher Loop | Done Foundation | fake provider / toy loop / trace resume 完成 |
| M5 Workflow Asset Layer | Done Foundation | Project knowledge、task contract、bug dossier、lesson packet、regression eval、routing table 与 integration smoke 已完成；后续批量持久化/学习策略归入 M6/M7 |
| M6 Curator / Distillation | Done Foundation | CuratorInput、TeacherGuidanceSummary、DistillationProposal、ReviewGate 与 curation smoke 已完成；promotion writer/dedup 作为后续增强 |
| M7 Weak Model Capability Expansion | Done Foundation | CapabilityLadder、TaskComplexity、WorkerPerformanceRecord、ModelCapabilityProfile、recommendation rules 与 capability smoke 已完成；routing adapter/真实数据连接后续增强 |
| M8 Creative Role Development | Done Foundation | CreativeBrief、CreativeVariant、CreativeCritique、UserSelectionFeedback 与 creative smoke 已完成；opportunity/metrics/real provider 后续增强 |
| M9 Strategy/Evaluation Harness | Done Foundation | StrategyEvaluationRecord、StrategyScorecard、BenchmarkSuite、StrategyComparisonReport 与 evaluation smoke 已完成；真实 benchmark/provider 后续增强 |
| M10 Real Provider Integration | Not Started | 需要授权，不改 Hermes config |
| M11 Real Workflow Execution | Not Started | 依赖 M5/M6/M10，provider-free toy path 可先做 |
| M12 Safety/Budget Governor | Not Started | 依赖 M7/M10/M11 |
| M13 Productization | Not Started | 依赖数据模型稳定 |
| M14 Release Hardening | Not Started | 可部分提前做 CI skeleton |

---

# 20. Immediate Next Development Slice

## M9.3 / M9.4：Benchmark Task Suite + Strategy Comparison Report

下一步继续 M9。Evaluation records/scorecards 已能聚合单个策略；接下来要建立 provider-free benchmark task suite 和多策略 comparison report，用 fixture records 比较 weak-only / weak+Feiyue / weak+sparse-teacher 等策略。

### Objective

实现 deterministic toy benchmark task definitions 与 strategy comparison report。此阶段仍不调用真实 provider，只使用 fixture/evidence records，重点验证 scorecard comparison、cost-normalized quality、teacher-call tradeoff 和 unsafe/repeated-failure visibility。

### Files

Create:

- `packages/feiyue-core/feiyue_core/evaluation/benchmark.py`
- `packages/feiyue-core/feiyue_core/evaluation/comparison.py`
- `packages/feiyue-core/tests/test_benchmark_suite.py`
- `packages/feiyue-core/tests/test_strategy_comparison.py`

Update:

- `packages/feiyue-core/feiyue_core/evaluation/__init__.py`
- Extend evaluation integration smoke.
- `README.md`
- `docs/Feiyue-self-evolution-development-outline.md`

### Functional Acceptance

- BenchmarkTask can represent task id, required capability level, expected verifier, category, and source IDs.
- BenchmarkSuite can hold deterministic ordered tasks.
- StrategyComparisonReport can compare multiple scorecards and identify best pass-rate, lowest cost, lowest teacher-call-rate strategies without hiding unsafe count.
- Cost-normalized quality is explicit and deterministic.

### Code Quality & Cleanliness Acceptance

- Provider-free and deterministic.
- No real benchmark/provider claims.
- No LLM self-evaluation.
- Empty/missing strategy edge cases tested.
- compileall / pytest / diff-check / secret scan pass.

### Dependencies

- M9.1 StrategyEvaluationRecord.
- M9.2 StrategyScorecard.
- M7 capability levels.

### Parallelization

可并行：Benchmark Suite 与 Strategy Comparison Report 可以分两条 lane 开发。
必须串行：comparison integration smoke 需要两条 lane 合并后完成。
