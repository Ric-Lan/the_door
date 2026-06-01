from pathlib import Path
from the_door.core.ui.api.context import APIContext


def test_project_root_reflects_current_fn_value(tmp_path):
    current = {"root": tmp_path / "a"}
    ctx = APIContext(
        _project_root_fn=lambda: current["root"],
        _job_store_fn=lambda: "JOB",
        _switch_project_fn=lambda p, f: {"status": "ok"},
    )
    assert ctx.project_root == tmp_path / "a"
    current["root"] = tmp_path / "b"
    assert ctx.project_root == tmp_path / "b"


def test_job_store_and_switch_delegate():
    ctx = APIContext(lambda: Path("."), lambda: "JOB", lambda p, f: {"r": (p, f)})
    assert ctx.job_store == "JOB"
    assert ctx.switch_project("x", True) == {"r": ("x", True)}
