"""Shared Mermaid utilities — functions used by multiple rendering modules."""
from __future__ import annotations


def escape_mermaid_label(text: str) -> str:
    """Escape characters that are unsafe in Mermaid node labels.

    Replaces characters that break Mermaid flowchart syntax with their
    Mermaid entity equivalents (e.g., ``"`` → ``#quot;``).
    """
    text = text.replace('"', "#quot;")
    text = text.replace("[", "#lbrack;")
    text = text.replace("]", "#rbrack;")
    text = text.replace("|", "#124;")
    text = text.replace("{", "#lbrace;")
    text = text.replace("}", "#rbrace;")
    text = text.replace("(", "#lpar;")
    text = text.replace(")", "#rpar;")
    return text
