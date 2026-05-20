"""Tests assert L1_SYSTEM_PROMPT content satisfies the project's
non-technical-reader contract. The tests are inline string assertions —
no separate validator module — see plan's "Why no validator module" note.
"""
from the_door.core.llm.prompts import L1_SYSTEM_PROMPT


def test_l1_system_prompt_targets_non_technical_reader():
    """Prompt must explicitly name the audience."""
    assert "非技術讀者" in L1_SYSTEM_PROMPT


def test_l1_system_prompt_lists_forbidden_jargon_categories():
    """Prompt must enumerate the forbidden categories by name so the LLM
    knows what to avoid."""
    for token in ("函式名", "API endpoint", "檔名", "縮寫", "camelCase"):
        assert token in L1_SYSTEM_PROMPT, f"L1 prompt missing forbidden token: {token}"


def test_l1_system_prompt_requires_feature_schema_fields():
    """Prompt must request all required Feature dataclass fields."""
    for field in ("feature_id", "label", "description", "trigger_description",
                  "confidence", "confidence_reason", "source_nodes"):
        assert field in L1_SYSTEM_PROMPT, f"L1 prompt missing schema field: {field}"


def test_l1_system_prompt_requires_feature_relations_top_level_key():
    """Existing parser (_process_batch line 287) reads data['feature_relations'];
    prompt must produce that exact key at top level."""
    assert "feature_relations" in L1_SYSTEM_PROMPT


def test_l1_system_prompt_good_example_avoids_forbidden_tokens():
    """The prompt's own ✅ example must not violate its own rules.
    Inline jargon spot-check on the example description text."""
    # Find the good example block — everything between ✅ and ❌
    assert "✅" in L1_SYSTEM_PROMPT, "missing good example"
    good_block = L1_SYSTEM_PROMPT.split("✅", 1)[1].split("❌", 1)[0]
    # Spot-check: example must not contain obvious jargon, including the
    # abbreviation category the prompt's own rule 2 forbids.
    forbidden_substrings = ("/api/", ".py", ".js", "JSON-RPC", "AST",
                            "UI", "API", "HTTP", "URL", "DOM")
    for forbidden in forbidden_substrings:
        assert forbidden not in good_block, (
            f"L1 prompt good example contains forbidden substring: {forbidden}"
        )


def test_l1_system_prompt_bad_example_present():
    """Negative example must be present to anchor the contrast."""
    assert "❌" in L1_SYSTEM_PROMPT
