"""Contract: SystemState JSON shape from Task 02 (to_json_dict) matches what
Task 05 (viewer /api/status handler + onboarding card consumer) reads.

Producer side: 02-guidance-engine.md Task 02.2 — defines to_json_dict.
Consumer side: 05-viewer-frontend.md Task 05.3 — emits via /api/status; Task 05.6 consumes
in the onboarding card (state.has_snapshots, state.project_path, ...).
"""
import pytest


@pytest.mark.contract
def test_systemstate_json_keys_match_viewer_consumer():
    from the_door.core.guidance.state import SystemState, to_json_dict
    from pathlib import Path
    state = SystemState(project_path=Path("/x"), has_dot_the_door=False,
                        has_structure_json=False, snapshots=(),
                        l2_features_analyzed=frozenset(), warnings=())
    produced = to_json_dict(state)

    # CONSUMER SIDE — what the viewer's onboarding card reads (05.6) MUST be present.
    # has_api_key / api_provider were removed in T5-A (丙案): zero API-key terminal
    # state, single agent-as-LLM path — the viewer no longer reads provider state.
    required_keys = {
        "project_path", "has_dot_the_door", "has_snapshots", "latest_snapshot",
        "snapshots", "warnings",
    }
    missing = required_keys - set(produced.keys())
    assert missing == set(), f"viewer consumer needs {missing} but producer doesn't emit them"
