# Feiyue Master Blueprint：创意进化开发组织总纲

> **版本**：v0.1  
> **日期**：2026-06-12  
> **状态**：Canonical blueprint。后续 Feiyue 的 PRD、开发大纲、任务拆分、验收标准和路线调整，默认以本文为最高层总纲。  
> **Source context**：结合 Obsidian 笔记《AI递归自我提升现状讨论 2026-06-12》、Feiyue System Doctrine、当前代码原型与用户最新补充要求整理。

---

## 1. Core Definition

Feiyue 是一个 **Hermes-based Creative Evolution Loop Orchestrator**：由 Hermes 编排的自进化开发组织系统。

Feiyue 的目标不是让单个模型神奇地修改自身权重，也不是做一个普通的弱模型 wrapper、fallback runtime、prompt optimizer 或 code repair bot。Feiyue 要构建的是一个能在真实项目中持续改进的开发组织：

```text
Human Creativity
→ Strong-model Specification
→ Weak-model Execution
→ Tool-grounded Verification
→ Teacher-guided Repair
→ Skill / Eval / Memory / Template / Routing Distillation
→ Better Next Iteration
```

中文表达：

```text
你的创意与品味
→ 强模型扩展 / PRD / Spec / Task Contract
→ 弱模型执行明确任务
→ 工具环境验证
→ 失败时老师诊断
→ 成功/失败经验沉淀
→ 下一轮任务更稳、更快、更少犯错、更有创造力
```

Feiyue 的“自我进化”发生在系统资产层，而不是默认在线修改基础模型权重。系统资产包括：

- PRD / spec / task contract templates
- project memory / project rules / design laws
- failure playbooks / bug dossiers / lesson packets
- verifier scripts / regression evals / benchmark cases
- model routing policies / escalation policies
- prompt templates / role prompts / worker prompts
- teacher guidance distillation artifacts
- skill candidates / approved skills
- trace / manifest / recovery state
- strategy versions / scorecards / promotion records

---

## 2. Why Feiyue Exists

Feiyue 来自一个现实问题：强模型很会规划、抽象、写 PRD/spec 和做高阶判断，但成本高、不可总是作为执行工人；弱模型和便宜模型可以承担大量执行工作，但容易在模糊任务、跨文件重构、审美约束、复杂 debug 和长期项目规则上犯错。

Feiyue 要解决的不是“用弱模型便宜地替代强模型”这么简单，而是：

1. 让强模型的能力被压缩成可复用的规格、模板、规则、评测和教学资产。
2. 让弱模型在明确边界内稳定执行，并通过反馈逐渐扩大任务边界。
3. 让工具环境和 verifier 成为 Ground Truth，避免 LLM 自嗨。
4. 让每一次失败都转化为 lesson、eval、template patch 或 routing update。
5. 让系统在模型切换、fallback、断电、断网后仍然保持进化状态。
6. 让系统逐渐从“只执行人的创意”发展到“能提出部分创意候选、变体、批判和改进方向”。

---

## 3. Non-Goals

Feiyue 当前阶段不追求：

- 在线修改基础模型权重。
- 宣称实现强意义上的无限 RSI 或智能爆炸。
- 让 AI 完全替代用户的产品方向和最终品味判断。
- 让强模型默认全程执行所有任务。
- 让弱模型直接读取模糊创意后自由发挥。
- 只依靠 LLM 自评作为完成依据。
- 只存 memory，不形成 skills、evals、templates 和 routing rules。
- 把 anti-amnesia runtime 当成项目全部目标。

---

## 4. Three Strategic Outcomes

Feiyue 必须同时追求三个结果。

### 4.1 Outcome A：Weak Models Become Reliable Workers

弱模型必须逐渐能保质保量完成更多工作。

这不要求弱模型权重本身发生变化，而是通过系统层进化让它们表现上更强：

- 更窄、更清晰的 task contract。
- 更好的 worker prompt。
- 更完整的 project memory。
- 更严格的 verifier。
- 更丰富的失败案例库。
- 更明确的禁止事项。
- 更准确的模型路由。
- 更低成本的 teacher escalation。
- 更高质量的 task templates。

衡量标准：

- 弱模型任务成功率提高。
- 平均重试次数下降。
- teacher call rate 下降或更精准。
- 同类错误重复次数下降。
- 可交付任务复杂度上升。
- 弱模型从简单 grep/doc/test 逐步推进到局部实现、debug、模块级实现。

### 4.2 Outcome B：System Boundary Expands

Feiyue 不应该永远停留在简单 boilerplate 或 toy demo。系统应该逐步扩大能承担的任务边界：

1. 文档同步、小修小补、grep audit。
2. 单文件修改、测试补充、i18n 迁移。
3. 小模块实现、局部 debug、UI 局部修改。
4. 多文件但明确边界的 feature slice。
5. 需要 teacher 诊断的复杂 bug 修复。
6. 可验证的产品功能端到端交付。
7. 在真实项目中自动生成 lesson/eval/template patch。
8. 在某些低风险范围内提出改进方案和实现路径。

边界扩大必须由 eval 和 verifier 证明，不能靠模型自称能力提升。

### 4.3 Outcome C：A Creative Role Emerges Inside the System

Feiyue 的初期创意主要来自用户，但长期目标之一是：系统内部逐渐形成能做部分创意工作的角色。

这个角色不是替代用户最终判断，而是逐步承担：

- 创意扩展：基于用户 seed 提出多个方向。
- 变体生成：提出功能、交互、UI、商业模式、技术路线变体。
- 反常规方案：提出非 obvious 的产品路径。
- 批判和筛选：解释每个方向为什么可能失败。
- 组合创新：把历史项目经验迁移到新项目。
- 机会发现：从 bug、用户痛点、失败轨迹中提出新功能候选。
- Taste-aware proposal：逐渐内化用户的审美铁律、产品偏好和禁区。

衡量标准：

- 系统提出的创意候选被用户采纳的比例。
- 创意候选违反用户禁区的比例下降。
- 创意候选从普通补全变成能提出有用的产品角度。
- 系统能基于历史 lessons 和 project memory 提出跨项目迁移建议。

---

## 5. Relation to Practical RSI

Obsidian 笔记中的关键判断是：现代务实 RSI 不是“AI 改写自己导致智能爆炸”，而是：

> 模型参与构造训练与推理闭环：生成候选 → 外部或 AI 评估 → 过滤 / 搜索 / 修订 / 微调 → 再生成。真正有效的系统通常不依赖模型单纯相信自己，而是引入环境反馈、程序执行、形式验证、模拟器、测试集或独立 reward model。

Feiyue 对这个判断的工程化落地是：

- **生成候选**：Student worker / candidate generator / creative role。
- **外部验证**：build、test、lint、runtime、screenshot、grep、API smoke、formal checker。
- **反馈归因**：FeedbackAnalyzer / bug dossier / teacher diagnosis。
- **修订重试**：CandidateRevisionLoop / worker retry。
- **经验沉淀**：lesson packet / skill candidate / eval case / template patch。
- **策略更新**：routing rule / worker prompt / task template / escalation policy。
- **持久恢复**：trace / manifest / resume context / anti-amnesia runtime。

Feiyue 的核心不是“自我”，而是“闭环”和“可验证反馈”。

---

## 6. Role System

Feiyue 至少包含以下逻辑角色。一个底层模型可以承担多个角色，但系统必须记录当时的角色、输入、输出摘要、成本、风险和对结果的影响。

### 6.1 User / Creative Director

职责：

- 原始创意。
- 产品方向。
- 审美铁律。
- 用户场景。
- 不可妥协的边界。
- 最终 go / no-go 判断。

Feiyue 第一阶段不是替代用户创造力，而是放大用户创造力。

### 6.2 Vision Expander / Creative Expander

推荐强模型承担。

职责：

- 扩展用户 seed。
- 提出多种产品方向。
- 生成极端用户场景。
- 生成反常规方案。
- 标注风险和非目标。

### 6.3 PRD Author

推荐强模型承担。

职责：

- 把方向写成 PRD。
- 明确 goal / non-goals / user stories。
- 写 acceptance criteria。
- 写 i18n、设计、技术和验证要求。

### 6.4 Spec Architect

推荐强模型承担。

职责：

- 把 PRD 转成工程 spec。
- 定义模块边界、API contract、数据模型、状态流、错误处理。
- 明确测试策略和验收方式。

### 6.5 Planner / Task Contract Author

职责：

- 把 spec 拆成 worker 可执行的 task contract。
- 明确 files、scope、do-not-touch、context、requirements、verification、escalation。

### 6.6 Worker

推荐弱模型 / 低成本模型承担。

职责：

- 只按 task contract 执行。
- 不重新设计产品。
- 不扩大 scope。
- 不跳过 verifier。
- 失败时输出 bug dossier。

### 6.7 Verifier

优先由工具环境承担，而不是 LLM 自评。

包括：

- unit tests / integration tests。
- build / typecheck / lint。
- runtime smoke。
- browser console / adb logcat。
- screenshot / visual checks。
- grep forbidden patterns。
- API smoke / real command output。

### 6.8 Teacher

推荐强模型承担，稀疏介入。

职责：

- 根据 bug dossier 诊断 root cause。
- 给出 minimal fix strategy。
- 产出 prevention rule。
- 判断是否需要更新 skill、template、eval 或 routing。

Teacher 不默认接管整个任务，否则弱模型和系统资产不会进化。

### 6.9 Reviewer

职责：

- 审查 spec compliance。
- 审查 code quality。
- 审查安全、隐私、越界修改、设计禁区。

### 6.10 Curator

职责：

- 从任务过程提炼 reusable lesson。
- 更新 project memory / skill / eval / task template / routing rule。
- 防止低质量经验污染正式资产。

### 6.11 Creative Role / Emerging Co-Creator

长期目标角色。

职责：

- 从项目历史、用户偏好、市场/技术约束中提出创意候选。
- 做创意组合、批判、变体探索。
- 逐渐形成 taste-aware proposal 能力。

该角色输出候选，不拥有最终决策权。

---

## 7. Core Workflow

### 7.1 Creative Intake

输入：

- 用户 seed。
- 用户偏好和禁区。
- 项目上下文。
- 目标用户和场景。

输出：

- creative brief。
- expansion candidates。
- risks and non-goals。

### 7.2 PRD / Spec Generation

强模型输出：

- PRD。
- technical spec。
- acceptance gates。
- verification plan。

### 7.3 Task Contracting

Planner 输出 worker contract：

```text
Task ID:
Title:
Scope:
Files to modify:
Files not to touch:
Context:
Requirements:
Acceptance criteria:
Verification commands:
Escalation rule:
```

### 7.4 Worker Execution

Worker 执行：

- 修改代码或文档。
- 运行指定 verifier。
- 失败时最多自修有限次数。
- 超过阈值生成 bug dossier。

### 7.5 Verification

Verifier 产出真实工具证据：

- pass/fail。
- command output summary。
- artifact refs。
- screenshots / logs where relevant。

### 7.6 Teacher Escalation

当 policy 触发时，生成 bug dossier 给 Teacher。

Teacher 返回：

- root cause。
- minimal fix strategy。
- prevention rule。
- reusable lesson candidate。

### 7.7 Retry / Repair

Worker 根据 teacher guidance 执行修复，再由 verifier 判定。

### 7.8 Curator Distillation

任务结束后，Curator 提炼：

- lesson packet。
- eval case。
- template patch。
- skill candidate。
- routing update。
- project memory update。

### 7.9 Next Iteration Improvement

下一次类似任务自动加载：

- 更好的 task template。
- 更准确的 project rules。
- 更严格的 regression checks。
- 更合适的 worker / teacher route。
- 更少的重复错误。

---

## 8. Minimal Viable Feiyue

Feiyue 的 MVP 不是大型 dashboard，也不是真实 provider 大一统。MVP 应该先实现自进化开发组织的最小闭环。

### 8.1 Project Knowledge Layer

每个项目有：

```text
.hermes/
  project-memory.md
  rules.md
  design-laws.md
  architecture.md
```

### 8.2 Task Contract Templates

```text
.hermes/task-templates/
  feature-task.md
  bugfix-task.md
  ui-task.md
  android-task.md
  chrome-extension-task.md
```

### 8.3 Bug Dossier Template

```text
.hermes/task-templates/bug-dossier.md
```

### 8.4 Regression Evals

```text
.hermes/evals/
  regression-checks.sh
  forbidden-patterns.txt
  smoke-tests.md
```

### 8.5 Lessons

```text
.hermes/lessons/
  YYYY-MM-DD-topic.md
```

### 8.6 Model Routing Table

```text
.hermes/model-routing.yaml
```

### 8.7 Worker and Teacher Reports

```text
.hermes/worker-reports/
.hermes/teacher-reports/
```

### 8.8 Curator Loop

每个任务结束后必须回答：

```text
1. What failed?
2. Why did it fail?
3. Which model failed?
4. Was the spec unclear?
5. Was the task too big?
6. Was the verifier missing?
7. Did teacher solve it?
8. What reusable lesson emerged?
9. Should we update project memory, skill, task template, verifier, eval, or routing rule?
```

---

## 9. Anti-Amnesia Module Positioning

防止失忆发疯是 Feiyue 的重要模块，但不是 Feiyue 的全部。

它的职责是保护系统闭环在以下情况下不断裂：

- 主模型不可用。
- fallback 到另一个模型。
- 网络中断。
- 断电。
- worker 进程崩溃。
- side effect 状态未知。

它维护：

- trace。
- journal。
- recovery manifest。
- pending operation。
- side-effect reconciliation。
- resume context。
- do-not-repeat rules。

它服务于更大的目标：让开发组织的进化状态和质量控制在模型切换后仍然存在。

---

## 10. Weak Model Capability Expansion

Feiyue 必须显式跟踪弱模型能力边界。

### 10.1 Capability Ladder

```text
Level 0: Read-only audit / grep / summarization
Level 1: Documentation sync / boilerplate / simple tests
Level 2: Single-file implementation with clear contract
Level 3: Localized multi-file change with strict do-not-touch scope
Level 4: Debug with verifier output and bounded retry
Level 5: Module-level feature slice with sandbox verification
Level 6: Teacher-assisted complex repair
Level 7: Independent proposal of implementation options
Level 8: Taste-aware creative variants under user direction
```

### 10.2 Promotion Rule

弱模型只有在某一层连续通过 verifier 和 reviewer 后，才能被允许进入更高层任务。

### 10.3 Demotion Rule

如果重复出现：

- scope creep。
- fake success。
- skipped verifier。
- repeated known mistake。
- design-law violation。

则降低该模型在对应任务类型上的路由优先级。

---

## 11. Emerging Creativity Plan

Feiyue 必须逐步培养系统内的创意角色，但需要分阶段推进。

### 11.1 Stage 1：Human Seed Expansion

用户提供 seed，系统提出扩展方向和批判。

### 11.2 Stage 2：Variant Generation

系统对已有 PRD/spec/feature 生成多个变体：

- conservative variant。
- bold variant。
- low-cost variant。
- high-impact variant。
- anti-pattern warning。

### 11.3 Stage 3：Cross-Project Transfer

系统从历史项目 lessons 中迁移创意：

- Voyager 的 offline survival 思路迁移到别的移动产品。
- MasqueGPS 的隐私/抗检测工程经验迁移到安全敏感 app。
- FRAutoEntrep 的表单自动化经验迁移到其他行政自动化。

### 11.4 Stage 4：Opportunity Discovery

系统从失败、用户摩擦、重复 bug、manual workaround 中提出新功能候选。

### 11.5 Stage 5：Taste-aware Co-Creation

系统逐渐内化用户偏好和禁区，提出更少违反审美铁律、更贴近用户方向的方案。

最终决策仍由用户做。

---

## 12. Evaluation Principles

Feiyue 的进化必须被评估证明。

核心比较：

- weak-only baseline。
- weak + Feiyue task contract。
- weak + Feiyue verifier/retry。
- weak + sparse teacher。
- strong full-run reference。

核心指标：

- task success rate。
- verifier pass rate。
- average attempts。
- repeated mistake count。
- teacher call rate。
- weak autonomy rate。
- cost-normalized quality。
- capability level promotion/demotion。
- accepted creative proposal rate。
- design-law violation rate。
- regression catch rate。

没有 eval 证据，不能声称系统进化。

---

## 13. Milestone Direction

后续路线应按以下主线推进。

### M0：Doctrine / Blueprint / Repository Baseline

定义 Feiyue 是创意进化开发组织，不是单一 runtime。

### M1：Core Schemas / Trace Contract

建立共享数据契约。

### M2：Local Execution / Verifier / Sandbox

让 candidate 可以被真实环境验证。

### M3：Resilient Runtime / Anti-Amnesia

保证中断和模型切换后不丢失进化状态。

### M4：Candidate / Feedback / Teacher Loop

建立 Student → Verify → Feedback → Teacher → Revision 的闭环原型。

### M5：Workflow Asset Layer

落地 project memory、task templates、bug dossier、lesson packets、regression evals、model routing table。

### M6：Curator / Distillation System

把 teacher guidance、worker failure 和 successful repair 转成可审核的 reusable assets。

### M7：Weak Model Capability Expansion

建立能力等级、任务晋升/降级、模型路由学习机制。

### M8：Creative Role Development

让系统从 human seed expansion 逐步发展到 variant generation、cross-project transfer、opportunity discovery。

### M9：Strategy Scoring / Evaluation Harness

证明不同策略、模型组合和模板是否真正提升质量。

### M10：Real Provider / Multi-Profile Worker Integration

接入真实模型角色和 Hermes profiles，支持多 worker 分工。

### M11：Productization / Dashboard / API

可视化 trace、tasks、lessons、routing、evals、capability boundaries。

---

## 14. Rules for Future Development

1. 任何新功能必须说明它服务于哪一个系统闭环。
2. 不得把 Feiyue 缩窄成防失忆工具。
3. 不得让弱模型直接执行模糊创意任务。
4. 强模型优先用于 PRD、spec、teacher、reviewer、curator、creative expansion。
5. 弱模型优先用于明确 task contract 下的执行。
6. Teacher guidance 必须尽量蒸馏成 template、lesson、eval 或 skill。
7. Verifier / human acceptance 优先于 LLM 自评。
8. Anti-amnesia 保护进化状态，但不是产品主线本身。
9. 系统必须跟踪弱模型能力边界，并以证据推进边界。
10. 系统必须逐步培养创意角色，但最终 taste selection 仍由用户掌握。

---

## 15. One-Sentence North Star

Feiyue 的北极星是：

> 让你的创意被一个由 Hermes 编排的 AI 开发组织持续放大：强模型负责抽象、规划、教学、评审和创意扩展；弱模型负责越来越复杂的明确执行；工具环境提供真实反馈；Curator 把每次失败和成功沉淀成 skills、evals、templates、memory 和 routing rules，使下一轮开发更可靠、更便宜、更有创造力。
