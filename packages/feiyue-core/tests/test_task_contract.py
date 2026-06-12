from feiyue_core.workflow.task_contract import TaskContract, build_task_contract


def test_task_contract_renders_deterministic_markdown():
    contract = TaskContract(
        task_id="M5-B",
        title="Task Contract Template rendering",
        scope="Render a task contract without provider dependencies.",
        files_to_modify=[
            "packages/feiyue-core/feiyue_core/workflow/task_contract.py",
            "packages/feiyue-core/tests/test_task_contract.py",
        ],
        files_not_to_touch=["packages/feiyue-core/feiyue_core/providers/"],
        context=["Lane B runs in parallel from the M5 base."],
        requirements=[
            "Expose a TaskContract model.",
            "Render markdown with stable section order.",
        ],
        acceptance_criteria=["Empty list sections render '- None'."],
        verification_commands=[
            "python -m pytest tests/test_task_contract.py -q",
            "python -m compileall -q feiyue_core",
        ],
        escalation_rule="Ask before expanding file scope.",
    )

    assert contract.render_markdown() == """# Task Contract: Task Contract Template rendering

## Task ID
M5-B

## Scope
Render a task contract without provider dependencies.

## Files to Modify
- packages/feiyue-core/feiyue_core/workflow/task_contract.py
- packages/feiyue-core/tests/test_task_contract.py

## Files Not to Touch
- packages/feiyue-core/feiyue_core/providers/

## Context
- Lane B runs in parallel from the M5 base.

## Requirements
- Expose a TaskContract model.
- Render markdown with stable section order.

## Acceptance Criteria
- Empty list sections render '- None'.

## Verification Commands
- `python -m pytest tests/test_task_contract.py -q`
- `python -m compileall -q feiyue_core`

## Escalation Rule
Ask before expanding file scope.
"""


def test_empty_list_sections_render_none():
    contract = build_task_contract(
        task_id="empty",
        title="Empty Sections",
        scope="No scoped lists.",
        files_to_modify=[],
        files_not_to_touch=[],
        context=[],
        requirements=[],
        acceptance_criteria=[],
        verification_commands=[],
        escalation_rule="Escalate blockers.",
    )

    markdown = contract.render_markdown()

    assert "## Files to Modify\n- None" in markdown
    assert "## Files Not to Touch\n- None" in markdown
    assert "## Context\n- None" in markdown
    assert "## Requirements\n- None" in markdown
    assert "## Acceptance Criteria\n- None" in markdown
    assert "## Verification Commands\n- None" in markdown


def test_from_task_spec_uses_stable_task_spec_fields_and_metadata_defaults():
    class MinimalTaskSpec:
        id = "task-123"
        title = "Use TaskSpec"
        goal = "Convert TaskSpec fields into a contract."
        acceptance_criteria = ["Contract includes acceptance criteria."]
        metadata = {
            "files_to_modify": ["src/example.py"],
            "files_not_to_touch": ["src/locked.py"],
            "context": ["Metadata supplies contract context."],
            "requirements": ["Support duck-typed TaskSpec inputs."],
            "verification_commands": ["python -m pytest"],
            "escalation_rule": "Escalate unclear metadata.",
        }

    contract = TaskContract.from_task_spec(MinimalTaskSpec())

    assert contract.task_id == "task-123"
    assert contract.title == "Use TaskSpec"
    assert contract.scope == "Convert TaskSpec fields into a contract."
    assert contract.files_to_modify == ["src/example.py"]
    assert contract.files_not_to_touch == ["src/locked.py"]
    assert contract.context == ["Metadata supplies contract context."]
    assert contract.requirements == ["Support duck-typed TaskSpec inputs."]
    assert contract.acceptance_criteria == ["Contract includes acceptance criteria."]
    assert contract.verification_commands == ["python -m pytest"]
    assert contract.escalation_rule == "Escalate unclear metadata."
