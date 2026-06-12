from feiyue_core.providers import (
    ProviderDiagnostic,
    ProviderFailureKind,
    classify_provider_failure,
    redact_secrets,
)


def test_redact_secrets_masks_key_token_password_and_auth_values() -> None:
    auth_line = "Authorization: " + "Bearer " + "bear4"
    stderr = "\n".join(
        [
            "api_key=key1",
            "token: tok2",
            "password = pw3",
            auth_line,
            "safe trace id trace_123 remains visible",
        ]
    )

    redacted = redact_secrets(stderr)

    assert "key1" not in redacted
    assert "tok2" not in redacted
    assert "pw3" not in redacted
    assert "bear4" not in redacted
    assert redacted.count("[REDACTED]") == 4
    assert "safe trace id trace_123 remains visible" in redacted
    assert "api_key=[REDACTED]" in redacted
    assert ("Authorization: " + "Bearer " + "[REDACTED]") in redacted


def test_redact_secrets_is_deterministic_and_handles_empty_text() -> None:
    assert redact_secrets("") == ""
    text = "OpenAI API key: key1 Token tok2"
    assert redact_secrets(text) == redact_secrets(text)


def test_classify_provider_failure_prioritizes_timeout_flag() -> None:
    diagnostic = classify_provider_failure(
        "401 unauthorized with api_key=key1", exit_code=124, timed_out=True
    )

    assert isinstance(diagnostic, ProviderDiagnostic)
    assert diagnostic.kind == ProviderFailureKind.TIMEOUT
    assert diagnostic.message == "provider request timed out"
    assert diagnostic.exit_code == 124
    assert diagnostic.timed_out is True
    assert "key1" not in diagnostic.redacted_stderr


def test_classify_provider_failure_detects_rate_limit() -> None:
    diagnostic = classify_provider_failure("HTTP 429: rate limit exceeded", exit_code=1)

    assert diagnostic.kind == ProviderFailureKind.RATE_LIMITED
    assert diagnostic.message == "provider rate limited request"


def test_classify_provider_failure_detects_authentication_errors() -> None:
    diagnostic = classify_provider_failure("invalid api key: unauthorized", exit_code=1)

    assert diagnostic.kind == ProviderFailureKind.AUTH_ERROR
    assert diagnostic.message == "provider authentication failed"


def test_classify_provider_failure_detects_provider_unavailable() -> None:
    diagnostic = classify_provider_failure("503 service unavailable from upstream", exit_code=1)

    assert diagnostic.kind == ProviderFailureKind.PROVIDER_UNAVAILABLE
    assert diagnostic.message == "provider unavailable"


def test_classify_provider_failure_defaults_to_unknown_with_redacted_stderr() -> None:
    diagnostic = classify_provider_failure("boom password: pw3", exit_code=2)

    assert diagnostic.kind == ProviderFailureKind.UNKNOWN
    assert diagnostic.message == "provider failed with exit code 2"
    assert diagnostic.exit_code == 2
    assert diagnostic.timed_out is False
    assert "pw3" not in diagnostic.redacted_stderr
    assert "password: [REDACTED]" in diagnostic.redacted_stderr
