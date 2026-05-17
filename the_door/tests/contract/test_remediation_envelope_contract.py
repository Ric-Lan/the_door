"""Contract: F3 error envelope shape — producer is Task 02 (make_error_envelope),
consumers are Task 04 (CLI error renderer) AND Task 05 (viewer /api error handlers + ui error display).

This is a three-way seam. The contract is the JSON shape; all three sides MUST agree.
"""
import pytest


@pytest.mark.contract
def test_error_envelope_shape_satisfies_all_consumers():
    pytest.skip("blocked on 04-cli-ux Task 04.4 (CLI consumer) AND 05-viewer-frontend Task 05.8 (viewer consumer)")

    from the_door.core.guidance.remediation import Remediation, make_error_envelope
    from the_door.core.guidance.actions import NextAction
    rem = Remediation(code="x", message="m",
                      next_action=NextAction(id="a.b", title="t", rationale="r", priority=1,
                                             cli_command="ls"))
    envelope = make_error_envelope(code="x", message="m", remediation=rem, source="here")

    # CONSUMERS — what each side needs:
    # CLI renderer (04.4) needs:
    # assert "error" in envelope
    # assert envelope["error"]["remediation"]["message"]
    # assert envelope["error"]["remediation"]["next_action"]["cli_command"]
    #
    # Viewer error display (05.8) needs:
    # assert envelope["error"]["code"]
    # assert envelope["error"]["source"]
    # assert "remediation" in envelope["error"]
    # # remediation.next_action may be null:
    # assert envelope["error"]["remediation"]["next_action"] is None or \
    #        "id" in envelope["error"]["remediation"]["next_action"]
