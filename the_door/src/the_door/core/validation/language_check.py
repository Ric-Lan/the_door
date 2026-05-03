"""Language check — scans L1 output for prohibited technical terms."""
from __future__ import annotations

import re

from the_door.models import CheckResult


# Prohibited technical terms (case-insensitive matching)
PROHIBITED_TERMS: list[str] = [
    "Service", "Handler", "Controller", "Loader", "IoC",
    "Middleware", "Decorator", "Class", "Module", "Import",
    "Endpoint", "Router", "Provider", "Factory", "Repository",
    "DAO", "ORM", "SDK", "API",
]

# Minimum word count for "functional description" context (relaxed rule for L1.5)
_MIN_FUNCTIONAL_WORDS = 4


class LanguageCheck:
    """Scan L1 feature labels and descriptions for prohibited technical terms."""

    def __init__(self):
        # Build regex pattern for word-boundary matching (case-insensitive)
        escaped = [re.escape(term) for term in PROHIBITED_TERMS]
        self._pattern = re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE)

    def check(self, llm_output: dict) -> CheckResult:
        """Scan all label and description fields for prohibited terms.

        Returns offending terms and their locations.
        """
        errors = []
        l1 = llm_output.get("l1", {})

        for i, feature in enumerate(l1.get("features", [])):
            feature_id = feature.get("feature_id", f"feature[{i}]")

            # Check label
            label = feature.get("label", "")
            matches = self._pattern.findall(label)
            for match in matches:
                errors.append(f"Prohibited term '{match}' found in label of {feature_id}")

            # Check description
            description = feature.get("description", "")
            matches = self._pattern.findall(description)
            for match in matches:
                errors.append(f"Prohibited term '{match}' found in description of {feature_id}")

        return CheckResult(passed=len(errors) == 0, errors=errors)

    def check_l1_5(self, llm_output: dict) -> CheckResult:
        """Scan L1.5 block labels for prohibited terms (relaxed rules).

        Relaxed rule: a technical term is allowed if accompanied by sufficient
        functional description (>= 4 words total in the label). A bare technical
        term (the label IS just the term) fails.
        """
        errors = []
        l1_5 = llm_output.get("l1_5", {})

        for i, block in enumerate(l1_5.get("blocks", [])):
            block_id = block.get("block_id", f"block[{i}]")
            label = block.get("label", "")

            matches = self._pattern.findall(label)
            if not matches:
                continue

            # Relaxed rule: if label has enough words, it's functional context
            word_count = len(label.split())
            if word_count < _MIN_FUNCTIONAL_WORDS:
                for match in matches:
                    errors.append(
                        f"Bare technical term '{match}' in label of {block_id} "
                        f"(needs functional description, got {word_count} words)"
                    )

        return CheckResult(passed=len(errors) == 0, errors=errors)
