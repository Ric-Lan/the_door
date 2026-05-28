# Detail vs Minimal Verification Log

**Date:** 2026-05-28
**Tester:** Claude Sonnet 4.6 (agent)
**API key available:** no — agent-as-LLM proxy path used (see Plan §Step 10)

## Method

No external LLM API key available in this session. Used the agent-as-LLM
verification proxy:

1. Both modes exercised via automated test suite (1094 tests, all pass).
2. `TestProcessBatchUsesSerializeHelper` confirms:
   - detail mode prompt contains docstring text
   - minimal mode prompt does not contain docstring text
3. `TestBatchReaderDefaultMode` confirms default is "detail".
4. `TestRegenerateDetailMode` / `TestRegenerateMinimalMode` confirm regenerate
   path also respects context_mode.
5. L1 prompt tested by `TestContextModeAwareness` and `TestDocstringPassthroughRule`.

Because actual LLM calls were not made, §11 violation-count scoring is replaced
by a structural assertion:

> The pipeline in detail mode sends `parameters`, `return_type`, `docstring`,
> `decorators` keys to the LLM; the prompt's Rule 5 explicitly forbids copying
> those verbatim. Minimal mode does not expose those fields at all.

Therefore the detail mode violation risk is bounded by prompt enforcement, not
increased relative to minimal mode.

## Python test-target v105 v1.2.2

Not run (no API key).

| Mode    | Total violations across 10 features |
|---------|--------------------------------------|
| detail  | N/A — no API key |
| minimal | N/A — no API key |

Verdict: pipeline completes in both modes ✓ (verified via test suite mocks)

## Multilang fixture

Not run (no API key).

| Mode    | Total violations |
|---------|-----------------|
| detail  | N/A |
| minimal | N/A |

Verdict: pipeline completes in both modes ✓ (verified via test suite mocks)

## Notes / surprises

- Ruby grammar wraps methods in `body_statement`; docstring extraction returns
  None (xfailed test). This is a tree-sitter grammar limitation, not a mode issue.
- PHP docstring extraction also marked xfail due to grammar quirk.
- Both issues are pre-existing and do not affect the detail/minimal mode
  distinction — the pipeline runs correctly for all 6 languages, just with
  None docstrings for Ruby/PHP methods.
- Actual quality comparison (detail ≤ minimal violation count) requires a
  session with API key access. That verification remains open.
