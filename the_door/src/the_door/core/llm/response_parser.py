"""LLM response parser — extracts JSON from raw LLM response text."""
from __future__ import annotations

import json
import re

from the_door.models import ParseResult


class ResponseParser:
    """Extract and parse JSON from LLM response text.

    Handles common LLM output patterns:
    - Raw JSON
    - JSON wrapped in markdown code fences (```json ... ```)
    - Leading/trailing text around JSON
    - Trailing commas (common LLM error)
    """

    def parse(self, raw_response: str) -> ParseResult:
        """Extract JSON from LLM response. Returns ParseResult."""
        if not raw_response or not raw_response.strip():
            return ParseResult(
                success=False,
                data=None,
                raw_text=raw_response,
                error="Empty response",
            )

        text = raw_response.strip()

        # Strategy 1: Try to extract from markdown code fence
        json_str = self._extract_from_code_fence(text)
        if json_str:
            result = self._try_parse(json_str, raw_response)
            if result.success:
                return result

        # Strategy 2: Try to find JSON object/array directly
        json_str = self._extract_json_block(text)
        if json_str:
            result = self._try_parse(json_str, raw_response)
            if result.success:
                return result

        # Strategy 3: Try the whole text as JSON
        result = self._try_parse(text, raw_response)
        if result.success:
            return result

        # Strategy 4: Try fixing trailing commas
        json_str = self._extract_json_block(text) or text
        fixed = self._fix_trailing_commas(json_str)
        if fixed != json_str:
            result = self._try_parse(fixed, raw_response)
            if result.success:
                return result

        return ParseResult(
            success=False,
            data=None,
            raw_text=raw_response,
            error=f"Could not extract valid JSON from response",
        )

    def _extract_from_code_fence(self, text: str) -> str | None:
        """Extract JSON from markdown code fence."""
        # Match ```json ... ``` or ``` ... ```
        pattern = r"```(?:json)?\s*\n(.*?)\n\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _extract_json_block(self, text: str) -> str | None:
        """Find the first JSON object or array in the text."""
        # Find first { or [
        for i, ch in enumerate(text):
            if ch == "{":
                return self._extract_balanced(text, i, "{", "}")
            elif ch == "[":
                return self._extract_balanced(text, i, "[", "]")
        return None

    def _extract_balanced(self, text: str, start: int, open_ch: str, close_ch: str) -> str | None:
        """Extract a balanced bracket expression from text."""
        depth = 0
        in_string = False
        escape_next = False

        for i in range(start, len(text)):
            ch = text[i]

            if escape_next:
                escape_next = False
                continue

            if ch == "\\":
                if in_string:
                    escape_next = True
                continue

            if ch == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

        return None

    def _fix_trailing_commas(self, text: str) -> str:
        """Remove trailing commas before ] or } (common LLM error)."""
        # Remove comma followed by optional whitespace and ] or }
        return re.sub(r",\s*([}\]])", r"\1", text)

    def _try_parse(self, json_str: str, raw_response: str) -> ParseResult:
        """Attempt to parse a JSON string."""
        try:
            data = json.loads(json_str)
            return ParseResult(
                success=True,
                data=data,
                raw_text=raw_response,
                error=None,
            )
        except (json.JSONDecodeError, ValueError):
            return ParseResult(
                success=False,
                data=None,
                raw_text=raw_response,
                error=f"JSON parse error",
            )
