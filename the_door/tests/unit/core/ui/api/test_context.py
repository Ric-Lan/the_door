from pathlib import Path
from the_door.core.ui.api.context import APIContext


def test_project_root_reflects_current_fn_value(tmp_path):
    current = {"root": tmp_path / "a"}
    ctx = APIContext(
        _project_root_fn=lambda: current["root"],
        _switch_project_fn=lambda p, f: {"status": "ok"},
    )
    assert ctx.project_root == tmp_path / "a"
    current["root"] = tmp_path / "b"
    assert ctx.project_root == tmp_path / "b"


def test_switch_delegate():
    # T5-A: job_store removed from context (analysis jobs retired).
    ctx = APIContext(lambda: Path("."), lambda p, f: {"r": (p, f)})
    assert ctx.switch_project("x", True) == {"r": ("x", True)}
