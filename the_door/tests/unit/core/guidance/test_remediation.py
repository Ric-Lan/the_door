def test_remediation_allows_null_next_action_and_docs():
    from the_door.core.guidance.remediation import Remediation
    r = Remediation(code="x", message="y")
    assert r.next_action is None
    assert r.docs_url is None


def test_make_error_envelope_matches_design_shape():
    from the_door.core.guidance.remediation import Remediation, make_error_envelope
    from the_door.core.guidance.actions import NextAction
    rem = Remediation(
        code="snapshot_not_found",
        message="找不到 baseline=v1.0.0",
        next_action=NextAction(id="system_status.show", title="查看狀態", rationale="r", priority=1, cli_command="the-door status"),
        docs_url=None,
    )
    env = make_error_envelope(code="snapshot_not_found", message="...", remediation=rem, source="api_handlers.handle_diff_versions")
    assert env["error"]["code"] == "snapshot_not_found"
    assert env["error"]["remediation"]["code"] == "snapshot_not_found"
    assert env["error"]["remediation"]["next_action"]["id"] == "system_status.show"
    assert env["error"]["source"] == "api_handlers.handle_diff_versions"


def test_remediation_catalogue_codes_are_unique():
    from the_door.core.guidance.remediation import REMEDIATION_CATALOGUE
    codes = list(REMEDIATION_CATALOGUE.keys())
    assert len(codes) == len(set(codes))
