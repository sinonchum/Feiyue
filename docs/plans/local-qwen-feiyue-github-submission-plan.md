# Local Qwen / Feiyue GitHub Submission Plan

Status: draft for branch preparation  
Current branch: `feat/feiyue-frontend-hermes-embed`  
Base commit observed locally: `dc9fa83 docs: record wave10-13 execution batch`

## Submission principle

Do not push Phase A-F as one large mixed commit. Split the work into reviewable layers:

1. reusable code and tests;
2. reproducible local scripts;
3. evidence summaries / ignore rules;
4. frontend/Hermes-embedding architecture;
5. frontend dogfood scaffold.

Large local `.hermes` evidence directories should stay out of git. They contain generated sandboxes, nested `.git` directories, pycache files, and machine-local execution artifacts. Commit only code, docs, tests, and small reproducible scripts. Reference evidence paths and run ids in docs/PR body instead of committing raw artifacts.

## Proposed commit stack

### Commit 1 — Local Ollama profile runner

Suggested subject:

```text
feat: add local ollama profile runner
```

Files:

```text
packages/feiyue-core/feiyue_core/providers/ollama_runner.py
packages/feiyue-core/feiyue_core/providers/__init__.py
packages/feiyue-core/tests/test_ollama_runner.py
```

Purpose:

- add `OllamaProfileRunner` as a Feiyue `ProfileRunRequest` adapter;
- add `CandidateWriteRepairingProfileRunner` for strict candidate-writes JSON repair;
- keep Hermes global config untouched;
- test HTTP injection, failure handling, and repair retry behavior.

Verification:

```bash
cd packages/feiyue-core
PYTHONPATH=. python -m pytest tests/test_ollama_runner.py -q
```

### Commit 2 — Local Qwen dogfood scripts and ignore rules

Suggested subject:

```text
chore: add local qwen dogfood phase scripts
```

Files:

```text
.gitignore
scripts/local_qwen25_feiyue_benchmark.py
scripts/local_qwen25_phase_b_workflow.py
scripts/local_qwen25_phase_c_workflow.py
scripts/local_qwen25_phase_d_wave9.py
scripts/local_qwen25_phase_e_routing.py
scripts/local_qwen25_phase_f_apply_routing.py
```

Purpose:

- make Phase A-F reproducible without committing `.hermes` generated artifacts;
- explicitly ignore generated local benchmark/evidence/sandbox directories;
- preserve safety invariants: no global Hermes config mutation, no production mutation, project-local routing only.

Verification:

```bash
cd packages/feiyue-core
python -m py_compile ../../scripts/local_qwen25_feiyue_benchmark.py \
  ../../scripts/local_qwen25_phase_b_workflow.py \
  ../../scripts/local_qwen25_phase_c_workflow.py \
  ../../scripts/local_qwen25_phase_d_wave9.py \
  ../../scripts/local_qwen25_phase_e_routing.py \
  ../../scripts/local_qwen25_phase_f_apply_routing.py
```

### Commit 3 — Frontend/Hermes embedding architecture

Suggested subject:

```text
docs: plan feiyue frontend hermes embedding
```

Files:

```text
README.md
docs/feiyue-frontend-hermes-embedding.md
docs/plans/feiyue-frontend-dogfood-real-task.md
```

Purpose:

- document why Feiyue should not directly iframe/embed Hermes UI;
- choose Feiyue Backend + Hermes Bridge sidecar;
- define frontend as a real Feiyue dogfood task;
- keep browser away from secrets, tools, and provider decisions.

Verification:

```bash
cd packages/feiyue-core
PYTHONPATH=. python -m pytest tests/test_frontend_architecture.py -q
```

Note: if commit 4 is not included yet, move the doc tests into commit 4 or run doc grep manually.

### Commit 4 — Frontend scaffold and safety tests

Suggested subject:

```text
feat: scaffold feiyue operator console
```

Files:

```text
packages/feiyue-web/package.json
packages/feiyue-web/src/index.html
packages/feiyue-web/src/styles.css
packages/feiyue-web/src/app.js
packages/feiyue-web/scripts/build-static.mjs
packages/feiyue-web/scripts/validate-static-app.mjs
packages/feiyue-core/tests/test_frontend_architecture.py
```

Purpose:

- add dependency-free static frontend shell;
- establish restrained dark institutional baseline;
- add disabled Hermes/routing controls;
- test that no forms, POST controls, localStorage/sessionStorage, or enabled write controls exist.

Verification:

```bash
cd packages/feiyue-web
npm run validate
npm run build
cd ../feiyue-core
PYTHONPATH=. python -m pytest tests/test_frontend_architecture.py tests/test_review_inbox_ui.py -q
```

## PR strategy

Preferred GitHub strategy: one feature PR with stacked commits.

PR title:

```text
feat: add local qwen dogfood and feiyue frontend architecture
```

PR body should include:

- Phase A-F run ids and outcomes as text, not raw evidence files;
- explicit note that `.hermes` generated evidence is intentionally ignored;
- safety summary:
  - no global Hermes config mutation;
  - no production mutation;
  - no provider secrets committed;
  - Phase F only applied project-local `.hermes/model-routing.yaml`, which remains ignored;
- verification commands and outputs.

Alternative if review size feels too large:

1. PR 1: `feat: add local ollama profile runner`
2. PR 2: `chore: add local qwen dogfood phase scripts`
3. PR 3: `feat: scaffold feiyue operator console`

Do not put frontend work on `main` directly; keep it on `feat/feiyue-frontend-hermes-embed` or split a child branch after Phase A-F commits are safely landed.

## Files that should not be committed

```text
.hermes/** generated evidence/sandboxes
packages/feiyue-web/dist/
node_modules/
__pycache__/
*.pyc
```

## Pre-push checklist

```bash
git status --short
cd packages/feiyue-core
PYTHONPATH=. python -m pytest tests/test_ollama_runner.py tests/test_frontend_architecture.py tests/test_review_inbox_ui.py -q
cd ../feiyue-web
npm run validate
npm run build
cd ../..
git status --short
```

Remove `packages/feiyue-web/dist/` after build verification unless the repository later decides to publish static build artifacts.
