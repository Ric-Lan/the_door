"""Contract: CLI side of the F3 remediation envelope (Task 04.4).

The viewer side (05.8) is still pending; this contract narrows to the CLI
consumer only — what `render_remediation` produces from a Remediation, and
the JSON shape that `make_error_envelope` produces so the CLI envelope-style
output can flow through the same producer.
"""
from __future__ import annotations

import io
import sys

import pytest


@pytest.mark.contract
def test_render_remediation_writes_error_prefix_and_try_line(monkeypatch):
    from the_door.core.guidance.remediation import Remediation
    from the_door.core.guidance.actions import NextAction
    from the_door.cli.next_action_renderer import render_remediation

    rem = Remediation(
        code="snapshot_not_found",
        message="找不到 snapshot",
        next_action=NextAction(
            id="system_status.show",
            title="查看狀態",
            rationale="r",
            priority=1,
            cli_command="the-door status .",
        ),
    )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    render_remediation(rem, json_mode=False)
    out = buf.getvalue()

    # CLI contract: human-readable Error: prefix + Try: suggestion
    assert "Error: 找不到 snapshot" in out
    assert "Try: the-door status ." in out


@pytest.mark.contract
def test_make_error_envelope_shape_for_cli_consumer():
    """The producer-side envelope shape that CLI (and later viewer) read."""
    from the_door.core.guidance.remediation import (
        Remediation,
        make_error_envelope,
    )
    from the_door.core.guidance.actions import NextAction

    rem = Remediation(
        code="snapshot_not_found",
        message="m",
        next_action=NextAction(
            id="a.b",
            title="t",
            rationale="r",
            priority=1,
            cli_command="ls",
        ),
    )
    envelope = make_error_envelope(
        code="snapshot_not_found", message="m", remediation=rem, source="cli"
    )

    # CLI renderer needs:
    assert "error" in envelope
    assert envelope["error"]["code"] == "snapshot_not_found"
    assert envelope["error"]["remediation"]["message"] == "m"
    assert envelope["error"]["remediation"]["next_action"]["cli_command"] == "ls"
    # source is recorded for the viewer-side consumer (later 05.8)
    assert envelope["error"]["source"] == "cli"


@pytest.mark.contract
def test_envelope_nullable_next_action():
    """next_action MAY be null when no follow-up is suggested."""
    from the_door.core.guidance.remediation import Remediation, make_error_envelope

    rem = Remediation(code="x", message="m", next_action=None)
    envelope = make_error_envelope(
        code="x", message="m", remediation=rem, source="cli"
    )
    assert envelope["error"]["remediation"]["next_action"] is None
