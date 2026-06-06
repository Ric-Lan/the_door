"""S5 C2：scope_verifier 產出 scope_state 值域 == SCOPE_CONTRASTS（雙向單源釘樁）。"""
from the_door.core.scope.scope_membrane import SCOPE_CONTRASTS
from the_door.core.scope.scope_verifier import ScopeVerifier
from the_door.models import (
    Feature, L1Output, ScopeDefinition, ScopeFeatureEntry,
)


def test_verify_state_domain_equals_single_source():
    """C2 雙向：⊆ 抓 producer 冒新值、⊇ 抓 SCOPE_CONTRASTS 死值。"""
    # feat-both（complete）／feat-l1（out_of_scope）／feat-scope（in_scope_incomplete）
    scope_def = ScopeDefinition(scope_name="s", features=[
        ScopeFeatureEntry(feature_id="feat-both"),
        ScopeFeatureEntry(feature_id="feat-scope"),
    ])
    l1 = L1Output(features=[
        Feature(feature_id="feat-both", label="B", description="", trigger="user_action",
                trigger_description="", confidence="high", confidence_reason=""),
        Feature(feature_id="feat-l1", label="L", description="", trigger="user_action",
                trigger_description="", confidence="high", confidence_reason=""),
    ])
    result = ScopeVerifier().verify(scope_def, l1)
    assert {e.scope_state for e in result.entries} == set(SCOPE_CONTRASTS)   # 雙向 ==
