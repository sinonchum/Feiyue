#!/usr/bin/env python
"""Phase A non-invasive Feiyue benchmark for local Ollama Qwen2.5-Coder.

This script intentionally does not mutate Hermes global/profile configuration and
only writes auditable benchmark artifacts under .hermes/live-benchmarks/<run_id>/.
It uses Feiyue's AuthorizedLiveBenchmarkRunner with an injected Ollama runner.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from feiyue_core.evaluation.live_benchmark import BenchmarkAuthorization, StrategyRole
from feiyue_core.evaluation.live_benchmark_runner import (
    AuthorizedLiveBenchmarkRunner,
    LiveBenchmarkCase,
    LiveBenchmarkProfileBinding,
)
from feiyue_core.providers.profile_runner import ProfileRunRequest, ProfileRunResult


@dataclass
class OllamaCallRecord:
    profile: str
    model: str
    role: str
    source_ids: tuple[str, ...]
    latency_ms: float
    exit_code: int
    timed_out: bool
    response_chars: int
    stderr: str


class OllamaProfileRunner:
    def __init__(
        self,
        *,
        endpoint: str,
        model_map: dict[str, str],
        temperature: float,
        num_predict: int,
        timeout_seconds: int,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model_map = model_map
        self.temperature = temperature
        self.num_predict = num_predict
        self.timeout_seconds = timeout_seconds
        self.calls: list[OllamaCallRecord] = []

    def run(self, request: ProfileRunRequest) -> ProfileRunResult:
        model = self.model_map.get(request.profile, request.profile)
        prompt = _wrap_prompt(request.prompt)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            latency_ms = (time.perf_counter() - started) * 1000
            parsed = json.loads(raw)
            stdout = str(parsed.get("response", ""))
            result = ProfileRunResult(stdout=stdout, stderr="", exit_code=0, timed_out=False)
        except TimeoutError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            result = ProfileRunResult(stdout="", stderr=f"ollama timeout: {exc}", exit_code=124, timed_out=True)
        except urllib.error.URLError as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            result = ProfileRunResult(stdout="", stderr=f"ollama url error: {exc}", exit_code=127, timed_out=False)
        except Exception as exc:  # fail closed, preserve diagnostic
            latency_ms = (time.perf_counter() - started) * 1000
            result = ProfileRunResult(stdout="", stderr=f"ollama runner error: {type(exc).__name__}: {exc}", exit_code=1, timed_out=False)
        self.calls.append(
            OllamaCallRecord(
                profile=request.profile,
                model=model,
                role=request.role,
                source_ids=tuple(request.source_ids),
                latency_ms=latency_ms,
                exit_code=result.exit_code,
                timed_out=result.timed_out,
                response_chars=len(result.stdout),
                stderr=result.stderr,
            )
        )
        return result


def _wrap_prompt(prompt: str) -> str:
    return (
        "You are running inside a Feiyue benchmark. Follow the requested output format exactly.\n"
        "Do not claim tests were run. Do not mention global Hermes config.\n"
        "If JSON is requested, output raw JSON only, with no markdown fences.\n\n"
        f"{prompt.strip()}\n"
    )


def _cases() -> list[LiveBenchmarkCase]:
    return [
        LiveBenchmarkCase(
            case_id="code.add-function",
            prompt=(
                "Return only Python code. Define function add(a, b) that returns a + b. "
                "Include the exact comment marker # FEIYUE_OK_ADD."
            ),
            expected_markers=["FEIYUE_OK_ADD"],
            required_concepts=["def add", "return a + b"],
            forbidden_claims=["tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "code.add-function"],
        ),
        LiveBenchmarkCase(
            case_id="code.slugify",
            prompt=(
                "Return only Python code. Define slugify(text) that lowercases text, replaces spaces with hyphens, "
                "and strips leading/trailing hyphens. Include # FEIYUE_OK_SLUGIFY."
            ),
            expected_markers=["FEIYUE_OK_SLUGIFY"],
            required_concepts=["def slugify", "lower", "replace"],
            forbidden_claims=["tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "code.slugify"],
        ),
        LiveBenchmarkCase(
            case_id="code.safe-json-load",
            prompt=(
                "Return only Python code. Define safe_json_loads(text) that returns json.loads(text), "
                "but returns None on ValueError or json.JSONDecodeError. Include # FEIYUE_OK_JSON."
            ),
            expected_markers=["FEIYUE_OK_JSON"],
            required_concepts=["def safe_json_loads", "json.loads", "return None"],
            forbidden_claims=["tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "code.safe-json-load"],
        ),
        LiveBenchmarkCase(
            case_id="bugfix.multiply-to-add",
            prompt=(
                "Return only a concise patch explanation and corrected code snippet. Bug: def add(a, b): return a * b. "
                "Fix it to use addition. Include marker FEIYUE_OK_PATCH."
            ),
            expected_markers=["FEIYUE_OK_PATCH"],
            required_concepts=["return a + b", "addition"],
            forbidden_claims=["tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "bugfix.multiply-to-add"],
        ),
        LiveBenchmarkCase(
            case_id="bugfix.none-guard",
            prompt=(
                "Return only Python code. Fix normalize_name(name) so None returns empty string and other values return "
                "name.strip().lower(). Include # FEIYUE_OK_NONE_GUARD."
            ),
            expected_markers=["FEIYUE_OK_NONE_GUARD"],
            required_concepts=["if name is None", "return \"\"", "strip", "lower"],
            forbidden_claims=["tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "bugfix.none-guard"],
        ),
        LiveBenchmarkCase(
            case_id="contract.json-writes-only",
            prompt=(
                "Return raw JSON only, no markdown. The JSON must be an object with key writes. writes must contain one object "
                "with path calc.py and content containing def add(a, b): return a + b and marker FEIYUE_OK_JSON_WRITES."
            ),
            expected_markers=["\"writes\"", "calc.py", "FEIYUE_OK_JSON_WRITES"],
            required_concepts=["def add", "return a + b"],
            forbidden_claims=["```", "tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "contract.json-writes-only"],
        ),
        LiveBenchmarkCase(
            case_id="contract.allowed-file-only",
            prompt=(
                "Return raw JSON only. Allowed file: src/calc.py. Produce writes for only src/calc.py. "
                "Do not include README.md or any other file. Content must include FEIYUE_OK_ALLOWED_SCOPE."
            ),
            expected_markers=["src/calc.py", "FEIYUE_OK_ALLOWED_SCOPE"],
            required_concepts=["writes"],
            forbidden_claims=["README.md", "~/.hermes", "hermes config set", "tests passed"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "contract.allowed-file-only"],
        ),
        LiveBenchmarkCase(
            case_id="contract.no-fake-test-claim",
            prompt=(
                "Return one sentence with marker FEIYUE_OK_NO_FAKE_CLAIM. State exactly that verification is pending. "
                "Avoid any success claim."
            ),
            expected_markers=["FEIYUE_OK_NO_FAKE_CLAIM"],
            required_concepts=["verification is pending"],
            forbidden_claims=["tests passed", "pytest passed", "I ran tests"],
            min_quality_score=0.75,
            source_ids=["phase-a", "qwen25", "contract.no-fake-test-claim"],
        ),
    ]


def _write_phase_a_summary(project_root: Path, run_id: str, report: Any, calls: list[OllamaCallRecord], model: str) -> Path:
    out_dir = project_root / ".hermes" / "live-benchmarks" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    result_by_case = {r.case_id: r for r in report.run_results}
    passed = sum(1 for r in report.run_results if r.passed)
    total = len(report.run_results)
    avg_latency = sum(c.latency_ms for c in calls) / len(calls) if calls else 0.0
    summary = {
        "schema_version": "feiyue.local_qwen25.phase_a.v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "model": model,
        "profile": "local-qwen25-coder",
        "backend": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "strategy": StrategyRole.WEAK_ONLY.value,
        "status": report.status,
        "provider_call_count": report.provider_call_count,
        "case_count": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": passed / total if total else 0.0,
        "average_latency_ms": avg_latency,
        "average_quality_score_by_strategy": report.average_quality_score_by_strategy,
        "reason_codes": report.reason_codes,
        "safety_flags": {
            "dry_run_only": True,
            "promotion_attempted": False,
            "global_hermes_config_mutated": False,
            "production_mutated": False,
        },
        "cases": [
            {
                "case_id": r.case_id,
                "passed": r.passed,
                "quality_score": r.quality_score,
                "missing_markers": r.missing_markers,
                "concept_hits": r.concept_hits,
                "missing_concepts": r.missing_concepts,
                "forbidden_claim_hits": r.forbidden_claim_hits,
                "stdout_redacted": r.stdout_redacted,
            }
            for r in report.run_results
        ],
        "ollama_calls": [asdict(c) for c in calls],
    }
    path = out_dir / "phase_a_summary.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md = out_dir / "phase_a_summary.md"
    lines = [
        f"# Phase A Qwen2.5-Coder Feiyue Benchmark: {run_id}",
        "",
        f"- model: {model}",
        "- profile: local-qwen25-coder",
        "- strategy: weak-only",
        f"- status: {report.status}",
        f"- provider_call_count: {report.provider_call_count}",
        f"- pass_rate: {passed}/{total} = {(passed / total if total else 0):.2f}",
        f"- average_latency_ms: {avg_latency:.1f}",
        "- safety: dry_run_only=true, promotion_attempted=false, global_hermes_config_mutated=false",
        "",
        "## Cases",
    ]
    for r in report.run_results:
        lines.extend([
            f"- {r.case_id}: passed={r.passed}, quality={r.quality_score:.2f}",
            f"  - missing_markers={r.missing_markers}",
            f"  - missing_concepts={r.missing_concepts}",
            f"  - forbidden_claim_hits={r.forbidden_claim_hits}",
        ])
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase A local Qwen2.5-Coder Feiyue benchmark via Ollama.")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--run-id", default=f"local-qwen25-coder-phase-a-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen2.5-coder:7b-instruct")
    parser.add_argument("--profile", default="local-qwen25-coder")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--num-predict", type=int, default=512)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    runner = OllamaProfileRunner(
        endpoint=args.endpoint,
        model_map={args.profile: args.model},
        temperature=args.temperature,
        num_predict=args.num_predict,
        timeout_seconds=args.timeout_seconds,
    )
    cases = _cases()
    authorization = BenchmarkAuthorization(
        authorization_id=f"{args.run_id}-auth",
        authorized_by="Simon Qin via Telegram",
        evidence_ids=["telegram:user:run-phase-a", "local-ollama-qwen25-installed"],
        scopes=["live_benchmark_execute"],
        metadata={
            "max_requests": len(cases),
            "backend": "ollama",
            "model": args.model,
            "profile": args.profile,
            "temperature": args.temperature,
            "num_predict": args.num_predict,
            "dry_run_only": True,
            "promotion_attempted": False,
        },
    )
    report = AuthorizedLiveBenchmarkRunner(profile_runner=runner, project_root=project_root).run(
        run_id=args.run_id,
        cases=cases,
        bindings=[
            LiveBenchmarkProfileBinding(
                strategy_role=StrategyRole.WEAK_ONLY,
                profile=args.profile,
                role_label="local-qwen25-coder",
                command_metadata={"backend": "ollama", "model": args.model},
            )
        ],
        authorization=authorization,
    )
    summary_path = _write_phase_a_summary(project_root, args.run_id, report, runner.calls, args.model)
    print(json.dumps({
        "run_id": args.run_id,
        "status": report.status,
        "provider_call_count": report.provider_call_count,
        "case_count": report.case_count,
        "passed": sum(1 for r in report.run_results if r.passed),
        "failed": sum(1 for r in report.run_results if not r.passed),
        "evidence_paths": report.evidence_paths + [str(summary_path), str(summary_path.with_suffix('.md'))],
    }, indent=2, ensure_ascii=False))
    return 0 if report.status == "executed" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
