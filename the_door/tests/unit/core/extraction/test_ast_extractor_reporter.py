"""Tests for ASTExtractor reporter hook."""
from the_door.core.extraction.ast_extractor import ASTExtractor
from the_door.core.pipeline.progress_reporter import ProgressReporter


def test_extract_calls_reporter_per_file(tmp_path):
    (tmp_path / "a.py").write_text("def f(): pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def g(): pass\n", encoding="utf-8")
    captured = []
    reporter = ProgressReporter(sink=lambda d: captured.append(d["current_file"]))
    reporter.set_total(2, root="new")
    ASTExtractor().extract(str(tmp_path), reporter=reporter)
    assert sorted(c.replace("\\", "/").split("/")[-1] for c in captured) == ["a.py", "b.py"]
