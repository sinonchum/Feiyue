# Feiyue System Doctrine：自我进化与弱模型质量放大

> **版本**：v0.1
> **日期**：2026-06-12
> **状态**：Canonical reference。后续 Feiyue 的开发、计划、评测与路线调整，默认以本文和 [`Feiyue-master-blueprint.md`](Feiyue-master-blueprint.md) 定义为准；除非用户明确说明，否则不得把 Feiyue 缩窄为单一 runtime、防失忆工具或普通弱模型增强框架。

---

## 1. Canonical Positioning

Feiyue 是一个**自我进化的、可验证反馈驱动的 AI Agent 系统**。

它的目标不是单纯让强模型完成任务，也不是单纯给弱模型套一层工具壳，而是让系统在真实任务中持续形成：

1. 任务结构化。
2. 候选方案生成。
3. 外部验证。
4. 失败归因。
5. 候选修订。
6. 策略更新。
7. 技能与经验沉淀。
8. 评测基准对比。
9. 安全和恢复约束。
10. 跨模型切换后的质量保持。

Feiyue 的“进化”属于系统层，而不默认意味着在线修改基础模型权重。系统通过 prompt、planner、tool policy、candidate generation strategy、failure playbook、skill library、eval cases、teacher guidance distillation 和 model routing policy 的持续更新，形成可审计、可回滚、可量化的能力改进。

---

## 2. Not Merely a Weak-Model Enhancement Wrapper

Feiyue 需要让 mimo-v2.5-pro、deepseek-v4-pro 等相对弱或低成本模型，在系统进化后尽量获得接近 GPT-5.5 / Gemini 3.1 Pro 等强模型的输出质量。

但这不等于 Feiyue 只是“弱模型增强框架”。

更准确地说：

> Feiyue 是一个自我进化系统；弱模型质量放大是它必须实现的核心结果之一。

弱模型增强只是外显效果。真正的内核是：

- 系统持续积累任务经验。
- 系统持续更新策略。
- 系统持续压缩强模型指导为弱模型可复用资产。
- 系统持续用外部 verifier 和 eval 判断哪些变化是真的提升。
- 系统在模型切换、fallback、断电、断网后仍能恢复这些进化资产，保持输出质量。

---

## 3. Strong Models as Sparse Teachers

GPT-5.5、Gemini 3.1 Pro 等强模型不应默认作为全程 executor。

它们在 Feiyue 中的默认角色是：

- **Teacher**：指出弱模型失败的根因、下一步学习方向和策略修正。
- **Reviewer**：审核弱模型 candidate 是否遗漏约束、违反安全或存在明显幻觉。
- **Labeler**：为失败轨迹标注 root cause、do-not-repeat、failure category、skill candidate 类型。
- **Strategy Critic**：解释策略版本之间的差异和 regression 原因。
- **Curriculum Designer**：帮助构造弱模型容易失败但可验证的训练/评测任务。
- **Distillation Source**：提供可转化为 checklist、prompt template、tool-use recipe、failure playbook 或 eval case 的高质量指导。

强模型介入应当是稀疏的、可计量的、可审计的。Feiyue 要优化的不是“永远不用强模型”，而是：

> 以尽量少的强模型调用，获得尽量接近强模型全程执行的最终质量。

---

## 4. Model Roles

Feiyue 的 provider / model 系统必须区分角色，而不是只有“主模型/备用模型”。

建议角色：

- **Student Model**：默认执行者，例如 mimo-v2.5-pro、deepseek-v4-pro。
- **Teacher Model**：稀疏介入的强模型，例如 GPT-5.5 / Gemini 3.1 Pro。
- **Reviewer Model**：审查 candidate、风险、遗漏约束。
- **Labeler Model**：标注失败原因和经验类型。
- **Judge Auxiliary Model**：只能辅助解释，不能单独决定成功。
- **Fallback Model**：在 provider failure 后接管，但必须从 Feiyue 的 durable state clean rebuild，而不是继承半坏上下文。

同一个底层模型可以承担多个角色，但系统必须记录它当时扮演的角色、触发原因、成本、输入摘要、输出摘要和对最终结果的影响。

---

## 5. Self-Evolution Loop

Feiyue 的核心进化闭环是：

1. **Task Intake**：接收任务、约束、权限、预算和上下文。
2. **Task Spec Builder**：生成结构化目标、验收条件、风险和 verifier 配置。
3. **Student Candidate Generation**：弱模型生成一个或多个 candidate。
4. **Execution Sandbox**：在隔离环境执行 candidate。
5. **Verifier Layer**：外部 verifier 判断成败。
6. **Feedback Analyzer**：把失败转换为 evidence-backed feedback。
7. **Candidate Revision**：student 根据 feedback 修订 candidate。
8. **Teacher Escalation**：当 policy 触发时，teacher 给出结构化指导，但不直接替代整个系统闭环。
9. **Distillation**：把 teacher guidance、成功修订和失败反例沉淀为 reusable assets。
10. **Strategy Optimizer**：更新 prompt、planner、tool policy、routing policy 或 skill retrieval policy。
11. **Evaluation Harness**：用固定 eval 和回归门证明这些更新是否真的提升。
12. **Resilient Runtime**：确保中断、fallback、模型切换后不丢失进化状态和质量控制。

没有外部 verifier 或人工验收的“自我感觉变好”不算进化。

---

## 6. Cross-Model Quality Preservation

Feiyue 必须解决一个核心问题：

> 当执行模型从强模型切到弱模型，或从一个弱模型切到另一个弱模型时，系统如何仍然保证高质量输出？

答案不能是“让新模型记住聊天上下文”。答案必须是系统化资产：

- TaskSpec。
- Acceptance criteria。
- Verifier configs。
- Candidate lineage。
- Failure taxonomy。
- Known mistakes / do-not-repeat。
- Teacher guidance distilled into checklists and prompts。
- Strategy versions。
- Skill candidates。
- Evaluation cases。
- Recovery manifest。
- Side-effect reconciliation records。

模型可以切换，但 Feiyue 的进化状态必须持久存在。新模型接手时，应从这些 durable artifacts 中重建任务理解和质量约束。

---

## 7. Evaluation: Proving Amplification and Evolution

Feiyue 必须用指标回答：系统是否真的让弱模型更接近强模型质量？

基础指标：

- Success rate。
- Verifier score。
- Average iterations。
- Cost。
- Latency。
- Rollback rate。
- Human intervention rate。
- Repeated mistake count。

模型放大指标：

- **Weak-only baseline**：弱模型单独完成任务的表现。
- **Weak + Feiyue scaffold**：弱模型在 verifier/feedback/revision 下的表现。
- **Weak + Sparse Teacher**：少量 teacher 介入后的表现。
- **Strong full-run baseline**：强模型全程执行的质量上限参考。
- **Quality gap to teacher**：距离强模型 baseline 的差距。
- **Teacher call rate**：每任务强模型调用次数。
- **Teacher token ratio**：强模型 token / 总 token。
- **Weak autonomy rate**：无需 teacher 完成的比例。
- **Recovery from weak failure**：弱模型首次失败后通过反馈循环恢复成功的比例。
- **Distillation gain**：teacher guidance 被沉淀后，弱模型在同类任务上的后续提升。
- **Cost-normalized quality**：单位成本质量。

没有这些指标，不能声称 Feiyue 达成了“进化”或“弱模型接近强模型质量”。

---

## 8. Development Implications

后续开发必须遵守以下方向：

1. Provider 设计必须是 role-aware，不只是普通 API wrapper。
2. Candidate generation 默认优先 student model。
3. Teacher model 默认稀疏介入，不默认全程执行。
4. Teacher 输出必须尽量转化为可复用资产，而不是一次性答案。
5. Resilient runtime 的任务是保护系统进化状态，而不是成为产品主线。
6. Evaluation harness 必须比较 weak-only、weak+Feiyue、weak+sparse-teacher、strong-full-run。
7. Strategy optimizer 必须以 eval 证据为准，不允许无证据覆盖默认策略。
8. Skill / memory 写入必须有来源、适用条件、验证证据和人工审核路径。
9. 模型切换后质量保持必须依赖 durable state 和 verifier，不依赖某个模型的临时上下文。

---

## 9. Immediate Roadmap Correction

M4 之后的开发重点应从普通 “LLM candidate + feedback” 调整为：

**Role-aware student/teacher candidate generation + feedback-driven self-evolution.**

优先顺序：

1. Role-aware Provider Contract。
2. FakeStudentProvider / FakeTeacherProvider。
3. TeacherInterventionPolicy。
4. ModelRoleRouter。
5. Structured Candidate Output。
6. Prompt Template Versioning。
7. Feedback Taxonomy。
8. Student → Verify → Feedback → Student Revision loop。
9. Policy-triggered Teacher Guidance。
10. Teacher Guidance Distillation。
11. Eval comparison across weak-only / weak+Feiyue / weak+sparse-teacher / strong-full-run。

---

## 10. Rule for Future Planning

除非用户明确说明，否则后续任何 Feiyue 计划、开发任务、PRD 修改、架构设计和验收标准都必须以本文为参照。

不得把 Feiyue 简化成：

- 普通 Agent runner。
- 普通弱模型 wrapper。
- 普通 fallback/recovery runtime。
- 普通 prompt optimizer。
- 普通 code repair bot。

Feiyue 的核心定义是：

> 一个系统层自我进化框架，通过 verifier-driven feedback、role-aware weak/strong model collaboration、teacher guidance distillation、strategy/eval loop 和 resilient durable state，让弱模型在模型切换和低强模型调用条件下仍能稳定输出接近强模型质量的结果。
