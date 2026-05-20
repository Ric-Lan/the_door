# L2 Anomaly Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the L2 anomaly prompt so it enforces a per-module checklist over the three AST-judgeable anomaly types, stopping the current "all 12 features produce `anomalies: []`" failure.

**Architecture:** Replace the body of `L2Generator._build_prompt` with a prompt that enumerates `dead_code`, `logic_dead_end`, `uncertain_boundary` by name with definitions, makes the per-module checklist mandatory (explicit "none found" required, not silent omission), and explicitly forbids fabricating `vuln_*` findings since vulnerability data is not injected.

**Tech Stack:** Python 3.12, pytest (existing test infrastructure under `the_door/tests/`).

---

## Background

Source investigation (2026-05-19 session):

**L2 anomaly prompt is weak** ([`l2_generator.py:99-113`](the_door/src/the_door/core/ui/l2_generator.py:99)). "any anomalies (dead code, uncertain boundaries, etc.)" is a soft directive. Only 2 of 5 `anomaly_type` values appear by name in the prompt. Observed result: 12/12 features in `the-door-v105` produce `anomalies: []`.

**Design principle:** L2 = developer territory (label + interactions); critical-need cross-cutting information such as anomalies must still surface here. See [README.md](README.md) for the full layer principle and shared out-of-scope list.

## Why `vuln_high` / `vuln_medium` are NOT enforced

`StructureJSON` ([`models.py:82-88`](the_door/src/the_door/models.py:82)) contains `files`, `nodes`, `edges`, `topology` — **no vulnerabilities field**. `L2Generator.generate(feature_id, structure)` ([`api_handlers.py:687-688`](the_door/src/the_door/core/ui/api_handlers.py:687)) receives only two parameters. `VulnerabilityEntry` and `ScanResult` exist in [`models.py:497-525`](the_door/src/the_door/models.py:497) but are produced upstream in `analyze_pipeline.py` and never plumbed to `L2Generator`. Without that plumbing the LLM has no vulnerability data to cite, so `vuln_*` types structurally cannot fire.

This task enforces only the three anomaly types the LLM can judge from AST data alone: `dead_code`, `logic_dead_end`, `uncertain_boundary`. The L2 prompt mentions `vuln_*` exists but explicitly says data is not currently injected. Plumbing vulnerability data is an out-of-plan follow-up — see [README.md](README.md).

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Modify | [`the_door/src/the_door/core/ui/l2_generator.py`](the_door/src/the_door/core/ui/l2_generator.py:73) (lines 73-113, `_build_prompt`) | Rewrite L2 prompt with per-module checklist for 3 anomaly types |
| Modify | `the_door/tests/unit/core/ui/test_l2_generator.py` | Assert prompt content |

---

## Task 1: Rewrite `_build_prompt` to enforce per-module anomaly checklist

**Files:**
- Modify: [`the_door/src/the_door/core/ui/l2_generator.py:73-113`](the_door/src/the_door/core/ui/l2_generator.py:73) (the `_build_prompt` method)
- Test:   `the_door/tests/unit/core/ui/test_l2_generator.py`

- [ ] **Step 1: Inspect existing test fixtures**

Run: `grep -nE "^(def|class).+test_|StructureJSON\(|L2Generator\(" the_door/tests/unit/core/ui/test_l2_generator.py | head -30`

Note the construction pattern used to build a `StructureJSON` and instantiate `L2Generator` in existing tests. Match that pattern. `L2Generator.__init__(self, project_root, llm_provider)` — provider can be `None` for tests that only exercise `_build_prompt`.

- [ ] **Step 2: Write the failing tests**

Append to `the_door/tests/unit/core/ui/test_l2_generator.py`:

```python
# Append to the_door/tests/unit/core/ui/test_l2_generator.py

import re

from the_door.core.ui.l2_generator import L2Generator
from the_door.models import StructureJSON


def _normalize(text: str) -> str:
    """Collapse whitespace runs and lowercase — prompt-content assertions
    must be robust to line-wrapping and casing inside the prompt literal.
    The L2 prompt is built from concatenated string literals, so multi-word
    phrases get newlines + indentation spliced into them."""
    return re.sub(r"\s+", " ", text).lower()


def _structure_with_one_node() -> StructureJSON:
    # Minimal StructureJSON with one node so the prompt build path
    # has non-empty nodes_summary; existing test patterns may already
    # provide a richer fixture — prefer that if present.
    return StructureJSON()


def test_l2_prompt_lists_three_ast_judgeable_anomaly_types(tmp_path):
    """Prompt must enumerate the 3 anomaly types LLM can judge from AST alone:
    dead_code, logic_dead_end, uncertain_boundary."""
    gen = L2Generator(tmp_path, llm_provider=None)
    prompt = gen._build_prompt("feat-x", _structure_with_one_node())
    for atype in ("dead_code", "logic_dead_end", "uncertain_boundary"):
        assert atype in prompt, f"L2 prompt missing anomaly_type: {atype}"


def test_l2_prompt_notes_vuln_types_unavailable(tmp_path):
    """vuln_high / vuln_medium are mentioned as known types but the prompt
    must explicitly state vulnerability data is not currently injected,
    so the LLM does not fabricate vulnerabilities."""
    gen = L2Generator(tmp_path, llm_provider=None)
    prompt = gen._build_prompt("feat-x", _structure_with_one_node())
    assert "vuln_high" in prompt and "vuln_medium" in prompt
    # Some explicit "not currently injected / do not fabricate" wording.
    # Normalized: the prompt wraps this phrase across lines and uses "Do NOT".
    norm = _normalize(prompt)
    assert any(
        token in norm
        for token in ("not currently injected", "尚未注入", "do not fabricate", "不要編造")
    ), "L2 prompt must explicitly forbid fabricating vulnerability anomalies"


def test_l2_prompt_enforces_per_module_checklist(tmp_path):
    """Prompt must instruct LLM to report findings per module, including
    'no anomaly found' for clean modules — silently omitting is forbidden."""
    gen = L2Generator(tmp_path, llm_provider=None)
    prompt = gen._build_prompt("feat-x", _structure_with_one_node())
    # Look for both per-module enforcement and explicit-no-finding requirement.
    # Normalized: the prompt uses "For each module" and hyphenated "per-module".
    norm = _normalize(prompt)
    assert any(
        token in norm
        for token in ("for each module", "per-module", "every module")
    ), "L2 prompt lacks per-module enforcement language"
    assert any(
        token in norm
        for token in (
            'explicitly state "none found"',
            "明示「無發現」",
            "no anomaly found",
        )
    ), "L2 prompt does not require explicit no-finding statement"


def test_l2_prompt_preserves_existing_schema(tmp_path):
    """Regression: existing module / module_interactions / anomalies schema
    must remain so _parse_response keeps working."""
    gen = L2Generator(tmp_path, llm_provider=None)
    prompt = gen._build_prompt("feat-x", _structure_with_one_node())
    for key in ("modules", "module_interactions", "anomalies"):
        assert key in prompt
    for field in ("anomaly_type", "affected_node_ids", "explanation", "confidence"):
        assert field in prompt
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest the_door/tests/unit/core/ui/test_l2_generator.py -v -k "anomaly or vuln or checklist"`
Expected: failures — current prompt only names 2 of 3 enforced types, has no per-module enforcement, doesn't mention vuln_* availability.

- [ ] **Step 4: Rewrite `_build_prompt`**

Replace the body of `_build_prompt` ([`l2_generator.py:73-113`](the_door/src/the_door/core/ui/l2_generator.py:73)) with:

```python
def _build_prompt(
    self,
    feature_id: str,
    structure_json: StructureJSON,
) -> str:
    """Build LLM prompt for L2 generation.

    Enforces:
    - per-module anomaly checklist (LLM must explicitly report "none found"
      for clean modules rather than silently omit anomaly entries)
    - all 3 AST-judgeable anomaly types listed by name with definitions:
      dead_code, logic_dead_end, uncertain_boundary
    - vuln_high / vuln_medium mentioned but explicitly flagged as
      "data not currently injected — do not fabricate"
    """
    nodes_summary = [
        {"node_id": n.node_id, "name": n.name, "type": n.type, "file": n.file}
        for n in structure_json.nodes
    ]
    edges_summary = [
        {"from_node": e.from_node, "to_node": e.to_node, "type": e.type}
        for e in structure_json.edges
    ]
    structure_data = json.dumps(
        {"nodes": nodes_summary, "edges": edges_summary},
        ensure_ascii=False,
        indent=2,
    )

    return (
        f"You are analysing the codebase structure for feature '{feature_id}'.\n\n"
        "Given the AST structure JSON below, identify the logical modules that "
        "implement this feature, the interactions between those modules, and "
        "any anomalies.\n\n"
        f"Structure JSON:\n{structure_data}\n\n"
        "## Anomaly inspection (MANDATORY per-module checklist)\n\n"
        "For each module you identify, you MUST consider all 3 anomaly types "
        'below and either (a) emit an anomaly entry if found, or (b) explicitly '
        'state "none found" for that type in your reasoning. Silently omitting '
        "a type is a protocol violation.\n\n"
        "Anomaly types you SHOULD evaluate (use these exact strings in anomaly_type):\n"
        "  - dead_code: node exists but has no caller and is not reachable from\n"
        "               any entry point\n"
        "  - logic_dead_end: call chain terminates without producing observable\n"
        "                    effect or return value used downstream\n"
        "  - uncertain_boundary: node could plausibly belong to multiple modules;\n"
        "                        clarify which and why\n\n"
        "Anomaly types you must NOT emit in this call:\n"
        "  - vuln_high / vuln_medium: vulnerability scan data is not currently\n"
        "                             injected into this prompt. Do NOT fabricate\n"
        "                             vulnerability findings from AST alone.\n\n"
        "## Response format\n\n"
        "Respond with a JSON object that has exactly these top-level keys:\n"
        "  - modules: list of {module_id, label, confidence, source_nodes}\n"
        "  - module_interactions: list of {from_module, to_module, description,\n"
        "                                  relation_type}\n"
        "  - anomalies: list of {anomaly_type, affected_node_ids, explanation,\n"
        "                        confidence}\n\n"
        "confidence values must be 'high', 'medium', or 'low'.\n"
        "relation_type values must be 'static' or 'inferred'.\n"
        "Return only the JSON object, no additional text."
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest the_door/tests/unit/core/ui/test_l2_generator.py -v`
Expected: all tests pass — existing tests still green, 4 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add the_door/src/the_door/core/ui/l2_generator.py the_door/tests/unit/core/ui/test_l2_generator.py
git commit -m "feat(l2): enforce per-module anomaly checklist over 3 AST-judgeable types"
```

---

## Done Criteria

This task document is complete when:

1. `pytest the_door/tests/unit/core/ui/test_l2_generator.py -v` → all existing tests still green, 4 new tests pass.
2. `pytest the_door/tests/ -x -q` → green (full Python suite still passes).
3. The commit landed.
