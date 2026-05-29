"""Source-level guard: nothing in core/diff/ reads edge.resolution.

This guarantees adding new resolution values (e.g. name_match_ambiguous)
cannot cause spurious diff churn between snapshots.

If a future diff module legitimately needs resolution, this test should
be updated alongside a deliberate decision about bucketing strategy
(see spec §6.4).
"""
from pathlib import Path

import the_door


DIFF_DIR = Path(the_door.__file__).resolve().parent / "core" / "diff"


def test_core_diff_does_not_reference_edge_resolution():
    assert DIFF_DIR.is_dir(), f"diff dir missing: {DIFF_DIR}"
    offenders: list[str] = []
    for py in DIFF_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        # Strip comments+docstrings? Too brittle. A plain substring match is
        # the contract: no code OR comment in core/diff/ may reference
        # edge.resolution. If someone wants to add it, they update this test.
        if ".resolution" in text:
            offenders.append(py.name)
    assert offenders == [], (
        f"core/diff modules reference .resolution: {offenders}. "
        f"Adding resolution-aware diff requires updating spec §6.4 and this test."
    )
