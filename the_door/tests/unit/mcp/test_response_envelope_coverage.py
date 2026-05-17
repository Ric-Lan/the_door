"""S2 meta-test: every MCP tool injects ``next_actions`` on success responses.

For each tool listed in ``_invocation_recipes.RECIPES``:

* If the tool returns a success dict → assert ``next_actions`` is present and a
  list. Failing this assertion catches regressions where a new tool author
  forgot to wrap their payload with :mod:`_response_envelope`.

* If the tool returns a top-level ``error`` envelope → skipped. Error-envelope
  shape is covered by F3 tests (test_response_envelope.py).

* If the tool raises (genuinely cannot be exercised without heavy mocking, e.g.
  needs a real LLM provider) → skipped, but only when the tool is listed in
  ``RAISING_TOOLS``. Any unexpected exception fails the test loudly.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from tests.unit.mcp._invocation_recipes import RAISING_TOOLS, RECIPES


# ---------------------------------------------------------------------------
# Isolation fixture: prevent any tool from touching production state.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_production_state(tmp_path, monkeypatch):
    """Redirect ``Path.home()`` and stub ``ProjectRegistry.register``.

    Some tools (``analyze_tool``, ``snapshot_create_tool``, ``snapshot_write_tool``)
    call ``ProjectRegistry().register(...)`` which would write to
    ``~/.the-door/registry.json``. We point ``Path.home`` at a per-test tmp dir
    AND stub ``register`` to a no-op so even if the redirect leaks, no real
    files are touched.
    """
    fake_home = tmp_path / "_fake_home"
    fake_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    from the_door.core.registry import ProjectRegistry

    monkeypatch.setattr(ProjectRegistry, "register", lambda self, codebase_path: "000")
    yield


# ---------------------------------------------------------------------------
# Meta-test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_module_name", sorted(RECIPES.keys()))
async def test_every_tool_returns_next_actions(tool_module_name, tmp_path):
    module = importlib.import_module(f"the_door.mcp.tools.{tool_module_name}")
    args, _setup = RECIPES[tool_module_name](tmp_path)

    try:
        result = await module.execute(args)
    except Exception as exc:
        if tool_module_name in RAISING_TOOLS:
            pytest.skip(
                f"{tool_module_name} raised {type(exc).__name__}: {exc!r} — "
                "tool requires environment (LLM provider / real source files) "
                "not available in unit test seed; see recipe docstring."
            )
        raise

    assert isinstance(result, dict), (
        f"{tool_module_name} returned {type(result).__name__}, expected dict"
    )

    if "error" in result:
        # Error envelopes are well-formed per F3 tests; they intentionally do
        # not carry top-level next_actions (guidance lives inside
        # remediation.next_action).
        pytest.skip(
            f"{tool_module_name} returned error envelope "
            f"(keys={sorted(result.keys())}); "
            "error-envelope coverage lives in F3 tests."
        )

    assert "next_actions" in result, (
        f"{tool_module_name} success response missing 'next_actions' key. "
        f"Got keys: {sorted(result.keys())}. Wrap the payload with "
        "the_door.mcp.tools._response_envelope.wrap(...)."
    )
    assert isinstance(result["next_actions"], list), (
        f"{tool_module_name} 'next_actions' is "
        f"{type(result['next_actions']).__name__}, expected list."
    )
