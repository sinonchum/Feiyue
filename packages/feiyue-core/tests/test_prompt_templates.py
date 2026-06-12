import pytest

from feiyue_core.generation import PromptTemplateError, PromptTemplateLoader, ProviderCandidateOutput
from feiyue_core.schemas import TaskSpec, TaskStatus, TaskType


def task_spec() -> TaskSpec:
    return TaskSpec(
        id="task_prompt_001",
        title="Fix arithmetic helper",
        type=TaskType.CODE,
        status=TaskStatus.READY,
        goal="Make add return a + b",
        acceptance_criteria=["pytest passes", "source repo remains clean"],
        metadata={"target_files": ["math_tools.py"], "constraints": ["Do not change tests"]},
    )


def test_prompt_template_loader_loads_versioned_template() -> None:
    artifact = PromptTemplateLoader().load("student_candidate_generation")

    assert artifact.name == "student_candidate_generation"
    assert artifact.version == "v0.1"
    assert artifact.template_hash.startswith("sha256:")
    assert len(artifact.template_hash) == len("sha256:") + 64
    assert "Student Candidate Generation" in artifact.template


def test_prompt_template_hash_is_stable() -> None:
    loader = PromptTemplateLoader()

    first = loader.load("student_candidate_generation")
    second = loader.load("student_candidate_generation")

    assert first.template_hash == second.template_hash


def test_prompt_template_loader_fails_clearly_for_missing_template() -> None:
    with pytest.raises(PromptTemplateError) as error_info:
        PromptTemplateLoader().load("missing_template")

    assert "missing_template" in str(error_info.value)
    assert "not found" in str(error_info.value)


def test_candidate_generation_prompt_contains_task_context_and_output_schema() -> None:
    artifact = PromptTemplateLoader().render_student_candidate_prompt(
        task=task_spec(), output_schema=ProviderCandidateOutput.model_json_schema()
    )

    rendered = artifact.rendered_prompt

    assert artifact.name == "student_candidate_generation"
    assert artifact.template_hash.startswith("sha256:")
    assert "## Role" in rendered
    assert "student model" in rendered
    assert "## Task" in rendered
    assert "Make add return a + b" in rendered
    assert "pytest passes" in rendered
    assert "source repo remains clean" in rendered
    assert "math_tools.py" in rendered
    assert "Do not change tests" in rendered
    assert "## Output Schema" in rendered
    assert "file_writes" in rendered
    assert "must_be_verified_externally" in rendered
    assert "Do not claim success" in rendered


def test_candidate_generation_prompt_render_is_stable() -> None:
    loader = PromptTemplateLoader()

    first = loader.render_student_candidate_prompt(task=task_spec(), output_schema=ProviderCandidateOutput.model_json_schema())
    second = loader.render_student_candidate_prompt(task=task_spec(), output_schema=ProviderCandidateOutput.model_json_schema())

    assert first.rendered_hash == second.rendered_hash
    assert first.rendered_prompt == second.rendered_prompt
