# Feiyue

Feiyue is a private research/design repository for an AI self-improvement system.

## Implementation

- Core package: `packages/feiyue-core`
- Current slice: Pydantic schema contracts, recovery-runtime data contracts, command execution, JSONL trace writing, and pytest verification
- Local test command:

```bash
cd packages/feiyue-core
python3 -m pytest tests/ -q
```

## Documents

- [`docs/Feiyue-PRD.md`](docs/Feiyue-PRD.md) — product requirements for a verifiable feedback-driven AI self-improvement system.
- [`docs/Feiyue-development-outline.md`](docs/Feiyue-development-outline.md) — detailed development outline, dependencies, parallelization plan, serial blockers, risks, and solution paths.
- [`docs/resilient-session-runtime.md`](docs/resilient-session-runtime.md) — feature design for anti-amnesia runtime recovery across model fallback, network/power loss, and unknown side effects.
- [`docs/AI递归自我提升现状讨论 2026-06-12.md`](docs/AI递归自我提升现状讨论%202026-06-12.md) — discussion notes on practical Recursive Self-Improvement (RSI), synthetic data, self-play, AI feedback, inference-time self-correction, environment-driven feedback, and agent loops.

## Status

Private repository. Current baseline contains the RSI discussion note, PRD, and development outline.
