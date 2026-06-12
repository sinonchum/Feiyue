from feiyue_core.runtime import simulate_interrupted_resume


def test_full_interruption_simulation_reconciles_file_artifact_and_git_side_effects(tmp_path) -> None:
    result = simulate_interrupted_resume(tmp_path)

    assert result.manifest.pending_operations == []
    assert result.warnings == []
    assert "operation op_file_sim reconciled as confirmed" in result.manifest.verified_outputs
    assert "operation op_artifact_sim reconciled as confirmed" in result.manifest.verified_outputs
    assert "operation op_git_sim reconciled as confirmed" in result.manifest.verified_outputs
    assert result.manifest.next_safe_action == "continue with next planned step"
    assert "## Pending / unknown operations\n- None" in result.recovery_prompt
    assert result.file_path.exists()
    assert result.artifact_path.exists()
