"""L1 prompt teaches LLM about resolution labels + aggregate_call_hints."""
from the_door.core.llm.prompts import L1_SYSTEM_PROMPT as L1_FEATURE_EXTRACTION_PROMPT


def test_prompt_does_not_list_ambiguous_as_per_edge_label():
    """The prompt may explain ambiguous-edges-are-aggregated in prose,
    but must NOT include name_match_ambiguous as a bulleted per-edge label
    the LLM is told to interpret. Heuristic: it shouldn't appear with
    backtick formatting like other per-edge labels (`scope_rule` etc.)."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    assert "`name_match_ambiguous`" not in text


def test_prompt_explains_aggregate_call_hints():
    """Prompt teaches LLM what aggregate_call_hints means."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    assert "aggregate_call_hints" in text


def test_prompt_forbids_dependency_inference_from_hints():
    """Prompt explicitly forbids treating hint method names as dependencies."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    # Loose contract — exact wording can evolve, but the prohibition must be present.
    assert "不可" in text or "禁止" in text or "不要" in text
    assert "依賴" in text


def test_prompt_still_lists_three_resolution_labels_llm_sees():
    """LLM-facing resolutions after projection are exactly:
    scope_rule, import_alias, name_match."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    for label in ("scope_rule", "import_alias", "name_match"):
        assert label in text


def test_prompt_no_longer_lists_skipped_dynamic_as_per_edge_label():
    """skipped_dynamic edges are also folded into hints — should not appear
    as a per-edge label in the prompt's resolution explanation section."""
    text = L1_FEATURE_EXTRACTION_PROMPT
    # skipped_dynamic may still be mentioned in passing (e.g. in the hints
    # explanation), but should not appear as a standalone bulleted resolution
    # label the LLM is told to interpret per-edge.
    # Heuristic: it should not appear with backticks like `skipped_dynamic`
    # which is the existing per-label formatting.
    assert "`skipped_dynamic`" not in text
