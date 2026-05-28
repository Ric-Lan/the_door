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


class TestContextModeAwareness:
    def test_prompt_mentions_both_context_modes(self):
        assert "context_mode" in L1_SYSTEM_PROMPT
        assert "minimal" in L1_SYSTEM_PROMPT
        assert "detail" in L1_SYSTEM_PROMPT

    def test_prompt_describes_minimal_format(self):
        assert "節點 ID" in L1_SYSTEM_PROMPT or "node id" in L1_SYSTEM_PROMPT.lower()

    def test_prompt_describes_detail_format(self):
        assert "docstring" in L1_SYSTEM_PROMPT
        assert "signature" in L1_SYSTEM_PROMPT or "簽名" in L1_SYSTEM_PROMPT


class TestDocstringPassthroughRule:
    def test_prompt_has_rule_5_forbidding_docstring_passthrough(self):
        assert ("5." in L1_SYSTEM_PROMPT and "docstring" in L1_SYSTEM_PROMPT)

    def test_rule_explicitly_says_dont_copy(self):
        text = L1_SYSTEM_PROMPT
        forbidden_action_phrases = ["不可", "禁止", "不得"]
        copy_phrases = ["複製", "引用", "抄錄"]
        has_forbid = any(p in text for p in forbidden_action_phrases)
        has_copy = any(p in text for p in copy_phrases)
        assert has_forbid and has_copy

    def test_rule_covers_all_implementation_hints(self):
        text = L1_SYSTEM_PROMPT
        markers = ["docstring", "comments", "decorators", "signature"]
        hits = sum(1 for m in markers if m in text or m.lower() in text.lower())
        assert hits >= 3, f"Rule 5 should mention at least 3 of {markers}, got {hits}"
