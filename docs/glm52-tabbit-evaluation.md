# GLM-5.2 Capability Evaluation via Tabbit (Free Provider)

**Date:** 2026-06-23
**Model:** GLM-5.2 (Z.AI, 744B MoE, 1M context)
**Provider:** Tabbit International Edition (free tier, no quota)
**Tooling:** [tabbit-gl52-eval](https://github.com/sinonchum/tabbit-gl52-eval)

---

## Summary

GLM-5.2 was evaluated using the Feiyue capability framework (`capability/rules.py`)
through Tabbit's free Chat interface. All tasks used **real pytest verification**,
not keyword matching.

### Classification: **STRONG (PROMOTE)** ✅

```
Passed:  6/6 (100%)
Failed:  0
Blocked: 0

Independent successes: 6 ≥ 3 (PROMOTE threshold)
Teacher call rate:      0.0 ≤ 0.0
Repeated mistakes:      0
```

---

## Methodology

### Provider Setup

GLM-5.2 was accessed via Tabbit International Edition's AI Panel using
Chrome DevTools Protocol (CDP) automation. This requires:

1. Tabbit browser launched with `--remote-debugging-port=9222`
2. AI Panel webview open at `web.tabbit.ai/panel?mode=mi`
3. GLM-5.2 selected in the model picker

Prompts are sent by manipulating the `[role="textbox"]` DOM element and
dispatching a synthetic `KeyboardEvent('keydown', {key: 'Enter'})`.
Responses are read via body innerText diffing to extract only new content.

### Tasks

6 programming tasks spanning Feiyue capability levels L1–L6:

| # | Task ID | Feiyue Level | Description | Tests |
|---|---------|-------------|-------------|-------|
| 1 | L1.slugify | L1 Documentation/Code | URL slug function | 5 |
| 2 | L2.bsearch | L2 Single-File Change | Binary search off-by-one fix | 6 |
| 3 | L2.average | L2 Single-File Change | Zero-division fix for empty list | 4 |
| 4 | L4.palindrome | L4 Bounded Debug | Case-insensitive palindrome check | 6 |
| 5 | L5.ratelimiter | L5 Module Feature Slice | Thread-safe sliding window rate limiter | 3 |
| 6 | L6.async_fetch | L6 Complex Refactor | Sync→async conversion with aiohttp | 5 |

### Pipeline

```
Prompt → CDP → Tabbit Chat → GLM-5.2 Response → Code Extraction
→ Syntax Check → pytest → CapabilityRecord → classify()
```

### Code Extraction

GLM-5.2 responses come in two formats:
1. Markdown fenced blocks: ` ```python ... ``` `
2. Tabbit proprietary format: `PYTHON\nCopy\n ... `

The extractor handles both, plus a heuristic fallback. Tabbit UI chrome
(e.g., "New Tab", "Select text or screenshot", "GLM-5.2") is stripped
from extracted code.

---

## Results Detail

### L1.slugify — ✅ 5/5 PASSED

```python
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text
```

All 5 test cases passed: basic, special chars, multiple spaces, empty string, already-slugged.

### L2.bsearch — ✅ 6/6 PASSED

```python
def binary_search(arr, target):
    left, right = 0, len(arr) - 1  # FIX: right = len(arr) → len(arr)-1
    while left <= right:           # FIX: left < right → left <= right
        ...
```

Fixed the classic off-by-one: `right = len(arr)` and `while left < right` both corrected.

### L2.average — ✅ 4/4 PASSED

```python
def calculate_average(numbers):
    if not numbers:
        return 0
    ...
```

Added empty-list guard before division.

### L4.palindrome — ✅ 6/6 PASSED

```python
def is_palindrome(s: str) -> bool:
    s = ''.join(c.lower() for c in s if c.isalnum())
    return s == s[::-1]
```

Correctly handles case-insensitivity and non-alphanumeric filtering.

### L5.ratelimiter — ✅ 3/3 PASSED

Implemented a thread-safe sliding window rate limiter with `threading.Lock`
and `collections.deque`. All tests passed including the window-reset timing test.

### L6.async_fetch — ✅ 5/5 PASSED

Successfully converted synchronous `requests`-based HTTP fetching to
`async/await` with `aiohttp.ClientSession` and `asyncio.gather`.
All 5 static analysis tests passed (async def, await, aiohttp, gather, ClientSession).

---

## Lessons Learned

### 1. Keyword matching is worthless for capability evaluation

Initial keyword-based evaluation produced "WEAK (DEMOTE)" because keywords
like `right = len(arr) - 1` failed to match `right = len(arr)-1` (missing space).
The code was correct but the evaluation method was wrong. **Always use real
code execution (pytest) for programming capability evaluation.**

### 2. Code extraction must handle UI chrome

Tabbit's page body includes UI elements ("New Tab", "Select text...", "GLM-5.2")
that appear after the model's response. Early extraction attempts included these
in the code, causing `SyntaxError`. The fix: strip known UI markers from extracted
code, and detect natural-language instruction boundaries.

### 3. CDP multi-turn requires body-length diffing

Reading `document.body.innerText` returns the ENTIRE chat history. Without
tracking the body length before each send, the extraction would pick up code
from previous tasks. The fix: record `body_len_before` → after send, extract
only `body[body_len_before:]`.

### 4. Tabbit architecture detection is critical

Downloading the wrong Tabbit binary (arm64 vs x86_64) causes silent failures.
The `tabbit-gl52` CLI auto-detects platform and warns about mismatch recovery.

---

## Provider Rate Limits

Tabbit's FAQ states: *"The browser and all integrated models are free with
no daily quotas or hidden paywalls."*

**No rate limits apply.** However, practical constraints:
- ~15-25 seconds per request (inference + CDP overhead)
- Sequential only (single Chat UI turn)
- Glic bridge may disconnect after idle periods

For comparison, Z.AI's paid API costs **$1.40/1M input, $4.40/1M output** tokens.

---

## Related

- [tabbit-gl52-eval](https://github.com/sinonchum/tabbit-gl52-eval) — Provider adapter
- [capability/rules.py](../packages/feiyue-core/feiyue_core/capability/rules.py) — Classification rules
- [capability/ladder.py](../packages/feiyue-core/feiyue_core/capability/ladder.py) — Capability ladder (L0-L8)
