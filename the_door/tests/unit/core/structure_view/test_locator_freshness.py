import json
from pathlib import Path

from the_door.core.structure_view import locator


def _write_checklist(root: Path, source_files: dict) -> None:
    door = root / ".the-door"
    door.mkdir(parents=True, exist_ok=True)
    (door / "checklist.json").write_text(
        json.dumps({"stages": {"edge_residue": {"source_files": source_files}}}),
        encoding="utf-8",
    )


def test_freshness_unknown_when_no_checklist(tmp_path):
    assert locator.compute_freshness(tmp_path)["status"] == "unknown"


def test_freshness_fresh_when_fingerprint_matches(tmp_path):
    src = tmp_path / "a.py"
    src.write_text("print(1)\n", encoding="utf-8")
    st = src.stat()
    _write_checklist(tmp_path, {"a.py": [st.st_mtime_ns, st.st_size]})
    assert locator.compute_freshness(tmp_path)["status"] == "fresh"


def test_freshness_stale_when_file_changed(tmp_path):
    src = tmp_path / "a.py"
    src.write_text("print(1)\n", encoding="utf-8")
    # 蓋一個不可能相符的 fingerprint → 視為已變動
    _write_checklist(tmp_path, {"a.py": [1, 999]})
    out = locator.compute_freshness(tmp_path)
    assert out["status"] == "stale"
    assert "a.py" in out["changed_files"]
    assert out["changed_count"] == 1


def test_freshness_stale_when_file_deleted(tmp_path):
    _write_checklist(tmp_path, {"gone.py": [1, 1]})
    out = locator.compute_freshness(tmp_path)
    assert out["status"] == "stale"
    assert "gone.py" in out["changed_files"]


def test_freshness_skips_malformed_fingerprint(tmp_path):
    # fingerprint 結構壞掉（非 [mtime_ns, size]）→ fail-soft 跳過，不計為變動
    src = tmp_path / "a.py"
    src.write_text("print(1)\n", encoding="utf-8")
    _write_checklist(tmp_path, {"a.py": [1]})
    out = locator.compute_freshness(tmp_path)
    assert out["changed_count"] == 0
    assert out["status"] == "fresh"
