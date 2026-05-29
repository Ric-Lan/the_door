"""Tests for Task 06 — L1_SYSTEM_PROMPT teaches LLM how to read edge.resolution."""
from __future__ import annotations

from the_door.core.llm.prompts import L1_SYSTEM_PROMPT


class TestPromptMentionsResolution:
    def test_prompt_mentions_resolution_field(self):
        assert "resolution" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_scope_rule_label(self):
        assert "scope_rule" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_import_alias_label(self):
        assert "import_alias" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_name_match_label(self):
        assert "name_match" in L1_SYSTEM_PROMPT

    def test_prompt_mentions_aggregate_call_hints_instead_of_skipped_dynamic(self):
        # skipped_dynamic edges are now folded into aggregate_call_hints;
        # the prompt no longer lists skipped_dynamic as a per-edge label.
        assert "`skipped_dynamic`" not in L1_SYSTEM_PROMPT
        assert "aggregate_call_hints" in L1_SYSTEM_PROMPT

    def test_prompt_distinguishes_high_low_confidence(self):
        """Prompt must teach LLM that scope_rule/import_alias are high confidence
        and name_match is low confidence."""
        # 高信心 / 低信心 必須在 prompt 內成對出現
        assert "高信心" in L1_SYSTEM_PROMPT
        assert "低信心" in L1_SYSTEM_PROMPT

    def test_prompt_tells_llm_to_skip_uncertain_name_match(self):
        """Prompt must instruct LLM to be conservative with name_match edges."""
        # "寧可不提" 或類似的保守指引必須在
        assert "寧可不提" in L1_SYSTEM_PROMPT or "不要" in L1_SYSTEM_PROMPT
