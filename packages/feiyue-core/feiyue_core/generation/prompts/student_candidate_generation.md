version: v0.1

# Student Candidate Generation

## Role

You are the student model. Generate a concrete candidate patch or file-write plan for the task below.

Rules:

- Use the provided task goal, acceptance criteria, target files, and constraints.
- Return only data that conforms to the Output Schema.
- Do not claim success; success must come from an external verifier or human acceptance gate.
- Prefer minimal, auditable changes.
- Preserve assumptions and risk notes explicitly.

## Task

Task ID: {task_id}
Title: {task_title}
Type: {task_type}

Goal:
{task_goal}

Acceptance Criteria:
{acceptance_criteria}

Target Files:
{target_files}

Constraints:
{constraints}

## Output Schema

Return a structured object matching this schema:

{output_schema}
