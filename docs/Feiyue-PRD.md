# Feiyue PRD：可验证反馈驱动的 AI 自我提升系统

> **版本**：v0.1
> **日期**：2026-06-12
> **仓库**：Feiyue
> **定位**：一个面向代码、推理、研究与工具型任务的“工程化自我提升”系统，而不是宣称模型能够自主无限改写自身底层权重的强 RSI 系统。

---

## 1. 产品一句话

Feiyue 是一个受控的 AI 自我提升系统：它让 Agent 在真实任务环境中生成候选方案、执行验证器、收集反馈、形成经验资产，并通过评测、提示词/策略优化、技能库沉淀和可选训练数据产出，实现可审计、可回滚、可量化的局部能力提升闭环。

---

## 2. 背景与问题

当前“递归自我提升”（Recursive Self-Improvement, RSI）的务实方向已经从“AI 直接改写自身源代码/底层权重导致智能爆炸”的叙事，转向更工程化的闭环：

- 合成数据与自对弈：STaR、SPIN、RLAIF、Self-Rewarding 等。
- 推理期自我修正：Reflexion、Self-Refine、Tree Search、Verifier-guided reasoning。
- 环境驱动反馈：代码编译器、测试、模拟器、Lean/Coq、浏览器、真实 API。
- Agent 技能沉淀：类似 Voyager，将成功策略存入技能库，未来复用。
- 自动化科研与实验闭环：类似 AI Scientist，但需要严格验证与安全边界。

核心问题是：纯模型自我评价很容易出现幻觉、奖励作弊、模型坍塌和不可审计。Feiyue 的出发点是：**把“自我提升”定义为受控任务域内，基于外部可验证反馈的系统能力改进。**

---

## 3. 产品目标

### 3.1 核心目标

1. **形成闭环**：任务输入 → 候选生成 → 外部验证 → 反馈归因 → 策略更新 → 复测。
2. **以外部 Ground Truth 为主**：优先使用编译器、测试、形式验证器、环境执行、数据集指标作为反馈源。
3. **可量化提升**：每次策略/提示词/工具链/技能变化都必须跑评测并记录指标。
4. **可审计与可回滚**：保留每次实验的输入、输出、工具调用摘要、指标、变更 diff 与结论。
5. **防止自嗨循环**：LLM-as-Judge 只能作为辅助信号，不能单独决定“能力提升”。
6. **沉淀可复用能力**：成功策略进入技能库、提示词库、任务模板、评测集或训练数据候选池。

### 3.2 非目标

Feiyue v0.x 不做：

- 不训练或在线修改基础模型底层权重作为默认路径。
- 不宣称通用 AGI 自我进化。
- 不允许模型不经验证直接修改核心执行器或安全策略。
- 不以单一 LLM 自评作为成功标准。
- 不把用户私有数据直接变成训练数据；训练数据导出必须有显式许可与脱敏流程。

---

## 4. 目标用户与使用场景

### 4.1 目标用户

- AI Agent / LLM 应用开发者。
- 需要持续优化工作流的工程团队。
- 研究自动化、代码 Agent、评测系统、Prompt Optimization 的研究者。
- 需要可审计自动化改进系统的产品团队。

### 4.2 核心场景

#### 场景 A：代码任务自我提升

用户提供一个代码仓库与目标，例如“修复测试失败”或“实现功能”。Feiyue 让 Agent 生成方案、执行测试、分析失败、迭代修复。成功策略被归档为可复用技能或补充到评测集。

#### 场景 B：提示词与策略优化

系统针对同一类任务运行多组 Prompt / Planner / Tool-use 策略，比较通过率、成本、耗时、回滚次数，自动选择更稳健策略。

#### 场景 C：研究/文档任务质量提升

系统生成研究摘要、PRD、计划或论文段落后，通过事实检查、引用检查、结构评分、人工审阅标注等反馈改进输出策略。

#### 场景 D：工具使用能力沉淀

系统记录 Agent 在某类工具链中的成功操作模式，例如 GitHub PR、Obsidian 同步、CI 排错、浏览器自动化，形成技能或操作模板。

#### 场景 E：受控训练数据生成

当某类任务有稳定验证器时，系统把成功轨迹转化为训练样本候选，包括任务、上下文、动作序列、验证结果与失败反例。

---

## 5. 产品原则

1. **Ground Truth 优先**：代码测试 > 形式验证 > 环境运行 > 人类审核 > 多模型裁判 > 单模型自评。
2. **每次改变都可评测**：没有指标的“改进”不算改进。
3. **小步迭代**：策略变化、技能变化、提示词变化要小而可归因。
4. **安全分层**：生成者、执行器、评估器、策略更新器分离。
5. **人类可介入**：高风险变更必须等待人工批准。
6. **失败可学习**：失败轨迹同样重要，用于反例库和防错策略。
7. **默认隐私保护**：任务日志、用户数据、密钥、私有代码默认不外传、不训练。

---

## 6. 系统概览

Feiyue 由以下核心模块组成：

1. **任务入口 Task Intake**：接收任务、约束、代码仓库、评测目标和安全权限。
2. **任务建模 Task Spec Builder**：把自然语言任务转成结构化规格。
3. **候选生成 Candidate Generator**：生成多个计划、补丁、提示词或策略。
4. **执行沙箱 Execution Sandbox**：在隔离环境中运行代码、测试、工具调用或模拟器。
5. **验证器 Verifier Layer**：运行单元测试、静态检查、数据集指标、形式验证、人类检查表等。
6. **反馈归因 Feedback Analyzer**：把失败原因分类，提取可操作修正。
7. **策略优化器 Strategy Optimizer**：比较候选方案，更新 Prompt、Planner 参数、工具选择或技能。
8. **记忆与技能库 Memory/Skill Library**：保存可复用模式、反例、任务模板。
9. **评测基准 Evaluation Harness**：长期追踪能力变化。
10. **审计与回滚 Audit/Replay Store**：保存轨迹、指标、版本、变更和回滚点。
11. **抗失忆会话运行时 Resilient Session Runtime**：在模型 fallback、断电、断网、进程重启后，从持久 journal/manifest/artifacts 重建上下文，避免重复踩坑和未知副作用。
12. **安全治理 Safety Governor**：权限控制、数据脱敏、预算限制、人工批准。
13. **可视化控制台 Dashboard**：展示实验、指标、候选比较、失败模式和改进历史。

---

## 7. 功能需求

## 7.1 Task Intake：任务入口

### 功能

- 支持创建任务：自然语言目标、项目路径、任务类型、评测方法、预算限制。
- 支持任务类型：代码、文档、研究、工具操作、评测、提示词优化。
- 支持设置权限：只读、可写、可运行命令、可联网、可推送 GitHub。
- 支持上传/引用上下文：文件、仓库、历史对话、Obsidian 笔记、GitHub issue。

### 技术栈

- Backend：Python FastAPI。
- Schema：Pydantic v2。
- Storage：PostgreSQL。
- File references：本地路径 + Git commit SHA + content hash。

### 依赖

- 依赖用户授权与项目路径解析。
- 依赖安全权限模型。

### 验收标准

- 能创建任务并生成稳定 task_id。
- 所有输入都有结构化 schema。
- 不允许未授权写文件或运行命令。

---

## 7.2 Task Spec Builder：结构化任务规格

### 功能

- 将用户自然语言转成结构化规格：目标、非目标、约束、验证器、风险等级。
- 自动识别任务是否需要串行执行或可并行探索。
- 生成 acceptance criteria。
- 生成初始执行计划。

### 技术栈

- LLM provider adapter：OpenAI-compatible API。
- Structured output：Pydantic schema / JSON Schema。
- Prompt templates：版本化 YAML/Markdown 模板。

### 依赖

- 依赖 Task Intake。
- 依赖 provider adapter。
- 依赖基础 prompt 模板。

### 验收标准

- 对同一任务重复运行时结构稳定。
- 缺失关键上下文时提出澄清问题，而不是猜测。
- 输出必须包含验证方法。

---

## 7.3 Candidate Generator：候选生成器

### 功能

- 为同一任务生成多个候选：计划、补丁、Prompt、工具使用策略。
- 支持多策略生成：single-shot、plan-and-execute、reflection、tree search、best-of-N。
- 支持不同模型/不同温度/不同系统提示的候选对比。
- 为每个候选记录生成元数据。

### 技术栈

- Python async orchestration。
- Provider abstraction：OpenAI-compatible clients。
- Queue：Redis + RQ/Celery，或 Temporal（后期）。
- Trace format：JSONL。

### 依赖

- 依赖 Task Spec Builder。
- 依赖 provider credentials。
- 依赖预算管理。

### 验收标准

- 同一任务可生成 N 个候选。
- 每个候选有独立 trace_id。
- 失败候选不会污染成功候选。

---

## 7.4 Execution Sandbox：执行沙箱

### 功能

- 在隔离工作区执行候选方案。
- 支持 Git worktree / temp dir / Docker sandbox。
- 支持运行测试、lint、build、脚本、浏览器自动化。
- 支持超时、资源限制、网络限制。
- 自动保存 stdout/stderr 摘要和产物 hash。

### 技术栈

- 本地 MVP：Python subprocess + temporary worktree。
- 安全隔离：Docker / Firecracker / Modal sandbox（后续）。
- Git：worktree + patch apply + diff capture。

### 依赖

- 依赖项目是 Git 仓库时效果最好。
- 依赖安全策略和权限模型。

### 验收标准

- 候选执行不会直接污染主工作区。
- 每次执行都有可回放命令摘要。
- 超时和失败可被正常归类。

---

## 7.5 Verifier Layer：验证器层

### 功能

- 支持多种验证器：
  - 单元测试、集成测试、端到端测试。
  - Lint、typecheck、build。
  - 数据集指标：accuracy、pass@k、F1、BLEU、ROUGE、custom score。
  - 形式验证：Lean/Coq/SMT（后期）。
  - Web/API 环境探测。
  - 人工审阅 checklist。
  - LLM-as-Judge 辅助评分。
- 支持验证器权重和可信度等级。

### 技术栈

- Python plugin interface。
- pytest for internal tests。
- Evaluation adapters。
- Optional: lm-eval-harness / custom eval harness。

### 依赖

- 依赖 Execution Sandbox。
- 依赖任务规格提供验证目标。

### 验收标准

- 每个验证器输出结构化结果。
- 外部客观验证器结果优先级高于 LLM 自评。
- 验证失败必须有可读原因。

---

## 7.6 Feedback Analyzer：反馈归因器

### 功能

- 从验证失败中提取失败类型：语法、类型、测试断言、依赖缺失、环境问题、规格误解、权限问题、幻觉。
- 生成修复建议。
- 识别是否值得再次迭代。
- 识别是否需要人工介入。

### 技术栈

- Rule-based classifier + LLM summarizer。
- Error taxonomy YAML。
- Embedding similarity for historical failures（后期）。

### 依赖

- 依赖 Verifier 输出。
- 依赖历史失败库。

### 验收标准

- 能把常见测试失败归到稳定类别。
- 能区分任务失败与环境失败。
- 不把 LLM 猜测当作事实；必须引用日志片段或验证结果。

---

## 7.7 Strategy Optimizer：策略优化器

### 功能

- 根据候选结果选择最佳策略。
- 更新 Prompt、计划模板、工具选择规则、搜索参数。
- 维护策略版本。
- 支持 A/B 对比和回滚。

### 技术栈

- Bayesian optimization / bandit（后期）。
- 初期 rule-based ranking。
- Strategy config：YAML + version hash。
- Metrics DB：PostgreSQL。

### 依赖

- 依赖 Evaluation Harness。
- 依赖策略版本管理。

### 验收标准

- 每次策略变更都有前后指标。
- 指标下降自动回滚或标记为失败。
- 不允许在无评测证据时覆盖默认策略。

---

## 7.8 Memory / Skill Library：记忆与技能库

### 功能

- 将成功轨迹沉淀为：
  - Skill 文档。
  - Prompt 模板。
  - Tool-use recipe。
  - Failure playbook。
  - Evaluation case。
- 支持检索：按任务类型、错误类型、技术栈、仓库。
- 支持人工审核后发布为正式技能。

### 技术栈

- Markdown skill docs。
- SQLite/PostgreSQL metadata。
- Embeddings：LanceDB / sqlite-vss / pgvector（后期）。

### 依赖

- 依赖 Feedback Analyzer。
- 依赖人工审核队列。

### 验收标准

- 成功经验不会自动污染全局技能，默认进入候选区。
- 每个技能有来源、适用条件、验证方式。
- 能从新任务中检索到相关经验。

---

## 7.9 Evaluation Harness：评测基准

### 功能

- 维护固定任务集与动态任务集。
- 支持 replay 历史任务。
- 指标：成功率、平均迭代次数、成本、耗时、回滚率、人工介入率、误改率。
- 支持按任务类型和技术栈分组。

### 技术栈

- Python pytest-style eval runner。
- JSONL fixtures。
- PostgreSQL metrics。
- Optional CI integration：GitHub Actions。

### 依赖

- 依赖 Verifier。
- 依赖 Audit Store。

### 验收标准

- 任意策略版本可以跑同一评测集。
- 指标可对比。
- 评测失败时输出可复现命令。

---

## 7.10 Audit / Replay Store：审计与回放

### 功能

- 保存任务输入、候选、执行摘要、验证结果、策略版本、diff、产物 hash。
- 支持按 trace_id 回放。
- 支持导出 evidence packet。
- 支持隐私脱敏视图。

### 技术栈

- PostgreSQL + object storage/local artifacts。
- JSONL traces。
- Content-addressed storage for large files。

### 依赖

- 依赖所有模块输出 trace。

### 验收标准

- 任意成功/失败结论都能追溯到证据。
- 用户私有数据可脱敏导出。
- 不保存明文密钥。

---

## 7.11 Resilient Session Runtime：抗失忆会话运行时

### 功能

- 模型 fallback、provider 失败、断电、断网、进程重启后，从持久状态恢复任务。
- 维护 append-only session journal、latest recovery manifest、durable summary、artifacts。
- 记录 `known_mistakes` / `do_not_repeat`，避免 fallback 模型重复之前已确认失败的做法。
- 所有 side-effect tool call 执行前创建 operation record，恢复时先调和 pending/unknown operation。
- fallback 不继承半坏内存消息列表，而是从 manifest + journal tail + artifacts clean rebuild context。
- 恢复后第一步必须分类：confirmed facts、unknowns、unsafe assumptions、next safe action。

### 技术栈

- JSONL session journal。
- Pydantic recovery schemas。
- Local artifact store：command logs、tool results、diffs、model errors。
- Optional SQLite index：只保存 metadata/offset，不保存大 payload。
- Git/filesystem/GitHub reconciliation probes。

### 依赖

- 依赖 Audit / Replay Store。
- 依赖 Safety Governor 阻止 unknown side effect。
- 依赖 Evaluation Harness 统计 repeated mistake / recovery success 指标。
- 依赖 Memory / Skill Library，但本轮 mistake ledger 默认不直接进入长期记忆。

### 验收标准

- 主模型失败并 fallback 后，恢复 prompt 包含 confirmed facts 和 do-not-repeat 列表。
- 断电/重启后能从 latest manifest 恢复 task state。
- file/Git/GitHub side effect 状态 unknown 时，系统先查询 sha256、git status、remote HEAD 或 API 状态，不自动重复执行。
- auxiliary 任务失败不会污染主任务状态。
- repeated_mistake_count 可被 Evaluation Harness 统计。

详见：[`docs/resilient-session-runtime.md`](resilient-session-runtime.md)。

---

## 7.12 Safety Governor：安全治理

### 功能

- 权限控制：读、写、执行、联网、Git push、删除。
- 风险分级：低风险文档、高风险代码、危险系统命令。
- 预算限制：token、时间、候选数、并行度。
- 数据保护：PII/secret 扫描，训练数据导出审批。
- 人工批准：高风险操作前阻断。
- 恢复状态不明确时，阻止继续执行高风险 side effect。

### 技术栈

- Policy engine：YAML rules + Python evaluator。
- Secret scanner：regex + entropy + git-secrets style rules。
- Approval workflow：UI / CLI / Telegram gateway。

### 依赖

- 贯穿所有执行模块。
- 依赖 Resilient Session Runtime 提供 operation status 与 recovery state。

### 验收标准

- 未授权操作被拦截。
- 所有 side-effect 操作进入 audit log。
- 危险命令必须人工批准。
- pending/unknown side effect 未调和前，不允许重复 push/send/delete。

---

## 7.13 Dashboard：可视化控制台

### 功能

- 任务列表、状态、指标。
- 候选方案比较。
- 失败原因分布。
- 策略版本变化。
- 技能候选审核。
- 评测趋势。

### 技术栈

- Frontend：Next.js + TypeScript + React。
- UI：Tailwind 或 CSS Modules；保持扁平、专业、克制。
- Charts：Recharts / ECharts。
- API：FastAPI REST initially，后期可加 WebSocket。

### 依赖

- 依赖后端 API 和 metrics store。

### 验收标准

- 能查看任务全链路证据。
- 能比较候选结果。
- 能审批技能/策略更新。

---


## 7.14 Testing & Acceptance System：测试验收体系

### 功能

- 为每个 Phase、每个核心模块、每个策略版本定义明确的测试计划和验收门槛。
- 支持测试类型分层：unit、contract、integration、smoke、regression、recovery、security、manual acceptance checklist。
- 每个开发任务必须写清楚：测试什么、如何运行、预期输出、失败如何归因、通过后如何归档证据。
- 将测试结果纳入 Audit / Replay Store：命令摘要、exit code、报告路径、artifact hash、失败分类、人工验收结论。
- 对不可自动化判断的文档/研究/UI/技能审核任务，必须生成人工验收 checklist，并记录 reviewer、时间、结论和修改意见。
- 测试验收不能只看 LLM 自评；LLM 只能辅助解释失败或生成 checklist，最终结果必须来自外部验证器或人工确认。
- 测试验收必须拆成两条独立 gate：
  - **Functional Acceptance：功能性测试验收**：证明需求行为真的成立，例如功能输出、业务流程、恢复行为、权限行为、用户可见结果。
  - **Code Quality & Cleanliness Acceptance：代码完整干净度测试验收**：证明实现没有破坏工程质量，例如测试覆盖、lint/typecheck、架构边界、无死代码/重复代码、无 secret、无临时文件、工作区干净。
- 两条 gate 都必须通过才算完成；功能通过但代码脏，或代码整洁但功能未验收，都不能进入下一 Phase。

### 技术栈

- Python：pytest、pytest fixtures、coverage（后期）。
- Contract tests：Pydantic schema round-trip、JSON Schema snapshot、prompt contract snapshot。
- Integration tests：toy repo、fake provider、fake Git remote、temporary artifact store。
- Security tests：secret scanner fixtures、permission deny cases、dangerous command deny cases。
- Manual acceptance：Markdown checklist + structured review metadata。
- CI（后期）：GitHub Actions 运行 unit/contract/integration smoke gates。

### 依赖

- 依赖 Task Spec Builder 输出 acceptance criteria。
- 依赖 Verifier Layer 统一输出结构化测试结果。
- 依赖 Audit / Replay Store 保存验收证据。
- 依赖 Safety Governor 阻断高风险测试和真实副作用。

### 验收标准

- 每个 Phase 在开发大纲中都有“测试与验收方式”，不能只写功能清单。
- 每个 Phase 的验收必须同时包含 Functional Acceptance 和 Code Quality & Cleanliness Acceptance。
- 每个 PR/commit 前至少运行对应单元/契约测试和相关集成测试；无法运行时必须记录 blocker。
- 每个成功结论都能追溯到测试命令、结果摘要、artifact/hash 或人工 checklist。
- 每个失败都必须分类为代码失败、规格失败、环境失败、权限失败、provider 失败或未知状态。
- 发布策略/技能/恢复机制前，必须跑固定 regression/eval gate，防止重复踩坑和能力回退。

---

## 8. 推荐技术栈

### MVP 技术栈

- Language：Python 3.11+。
- Backend：FastAPI。
- Schema：Pydantic v2。
- DB：PostgreSQL；本地开发可 SQLite 起步但生产建议 PostgreSQL。
- Queue：Redis + RQ/Celery。
- Agent orchestration：自研轻量 orchestrator，避免过早引入复杂框架。
- Sandbox：Git worktree + temp dirs；后期 Docker。
- Frontend：Next.js + TypeScript。
- Eval：pytest-style eval runner + JSONL fixtures。
- Observability：structured logs + trace_id。
- Secrets：`.env` + never commit；后期接 Vault/1Password/Cloud secrets。

### 可选后期技术

- Temporal：复杂长任务工作流。
- Docker/Firecracker：强隔离执行。
- pgvector / LanceDB：经验检索。
- lm-eval-harness：模型能力评测集成。
- Modal：远程 GPU / 沙箱执行。
- LangGraph：如果状态机复杂后再引入。

---

## 9. 数据模型草案

### Task

- id
- title
- type
- status
- risk_level
- created_by
- permissions
- budget
- source_context_refs
- acceptance_criteria
- created_at / updated_at

### Candidate

- id
- task_id
- strategy_version
- model_provider
- model_name
- prompt_version
- status
- generated_plan
- patch_ref
- trace_ref
- created_at

### ExecutionRun

- id
- candidate_id
- sandbox_id
- commands_summary
- stdout_ref
- stderr_ref
- diff_ref
- artifacts_ref
- exit_code
- duration_ms

### VerificationResult

- id
- execution_run_id
- verifier_type
- verifier_name
- passed
- score
- confidence
- evidence_ref
- failure_category

### StrategyVersion

- id
- name
- config_hash
- prompt_refs
- tool_policy
- created_at
- parent_version
- metrics_snapshot

### SkillCandidate

- id
- source_task_id
- source_trace_id
- title
- applicability
- content
- status
- reviewer

---

## 10. 成功指标

### MVP 指标

- 能跑通 10 个固定代码修复任务。
- 至少 70% 任务能通过外部验证器完成。
- 每个任务有完整 trace 和验证证据。
- 能从一次成功轨迹生成技能候选。
- 能对两个策略版本跑同一 eval 并比较指标。
- 每个 Phase 都有可执行测试命令或人工验收 checklist，且验收证据进入 trace/audit。
- 任何恢复/fallback 场景的成功都必须通过 manifest、journal、side-effect reconciliation 证据确认。

### 长期指标

- 任务成功率提升。
- 平均迭代次数下降。
- 成本下降。
- 人工介入率下降。
- 回归率下降。
- 技能复用命中率提升。
- 失败归因准确率提升。

---

## 11. 主要风险与应对

### 风险 1：奖励作弊

- **表现**：模型优化 judge 分数而不解决真实问题。
- **应对**：外部验证器优先；LLM judge 只做辅助；引入反例集。

### 风险 2：模型坍塌 / 经验污染

- **表现**：系统持续用自己生成内容训练或更新策略，质量下降。
- **应对**：保留真实任务锚点；技能候选需人工审核；策略更新必须跑固定评测集。

### 风险 3：不可复现

- **表现**：一次成功无法重跑。
- **应对**：保存版本、命令、环境、seed、依赖、diff、hash。

### 风险 4：安全越权

- **表现**：模型删除文件、泄露密钥、推送错误代码。
- **应对**：权限模型、危险命令审批、secret scan、sandbox。

### 风险 5：成本失控

- **表现**：best-of-N、tree search 消耗过高。
- **应对**：预算上限、早停、候选并行度限制、成本指标纳入优化目标。

### 风险 6：过早工程复杂化

- **表现**：还没跑通闭环就引入 Temporal、K8s、复杂向量库。
- **应对**：MVP 先用本地 worktree + FastAPI + PostgreSQL + pytest eval。

---

## 12. MVP 范围

MVP 只做一个最小但真实的闭环：

1. 用户创建代码任务。
2. 系统生成 2-3 个候选修复计划/补丁。
3. 在 Git worktree 中执行。
4. 跑 pytest/lint/build 验证。
5. 选择通过候选。
6. 记录 trace、diff、验证结果。
7. 生成经验候选。
8. 用固定评测集比较策略版本。

MVP 不做完整训练，不做复杂 UI，不做分布式沙箱，不做通用科研自动化。

---

## 13. 开放问题

1. 初始任务域先选代码修复，还是文档/研究质量提升？建议先选代码修复，因为验证器更客观。
2. 是否直接嵌入 Hermes 作为执行 Agent，还是先做独立 orchestrator？建议先独立，后续接 Hermes/Claude Code/Codex 作为 worker。
3. 是否需要 Web UI 进入 MVP？建议先 API + CLI，Dashboard 放到 M1。
4. 技能库是否兼容 Hermes Skills 格式？建议兼容，便于复用。
5. 是否允许真实模型训练？建议放到后期，只先导出训练数据候选。
