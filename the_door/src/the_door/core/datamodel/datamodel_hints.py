"""Cross-language heuristics for locating data-model touch points (Tier 0).

刻意不掛 language_configs.py（那是 per-language scope rules）；這裡是跨語言
name/dir 啟發式。集合小而明確，便於審視與擴充。
"""
from __future__ import annotations

PERSIST_NAME_HINTS = ("save", "create", "insert", "update", "persist", "repository", "dao")
PERSIST_DIR_HINTS = ("models", "schema", "migrations", "entities")
SCHEMA_FILE_SUFFIXES = (".sql", ".csv")
SCHEMA_JSON_NAME_HINTS = ("schema", "model")


def code_site_reason(name: str, file: str) -> str | None:
    """Return a human-readable reason if this node looks persistence-related, else None."""
    lname = name.lower()
    for hint in PERSIST_NAME_HINTS:
        if hint in lname:
            return f"name contains '{hint}'"
    lfile = file.replace("\\", "/").lower()
    for d in PERSIST_DIR_HINTS:
        if f"/{d}/" in lfile or lfile.startswith(f"{d}/"):
            return f"file under '{d}/'"
    return None


def schema_file_reason(path: str) -> str | None:
    """Return a reason if this file path looks like a declared schema artifact, else None."""
    lpath = path.replace("\\", "/").lower()
    for suf in SCHEMA_FILE_SUFFIXES:
        if lpath.endswith(suf):
            return f"schema file ({suf})"
    if lpath.endswith(".json"):
        name = lpath.rsplit("/", 1)[-1]
        for hint in SCHEMA_JSON_NAME_HINTS:
            if hint in name:
                return f"schema-like json (name contains '{hint}')"
    return None
