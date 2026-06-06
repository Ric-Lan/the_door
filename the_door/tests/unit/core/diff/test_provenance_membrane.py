"""S7 P3/P4：provenance 膜詞彙（current/legacy/unknown Signal）。

derive_provenance＝戳 vs 當前契約的純事實比對（fact-finder、不裁決）；
unknown＝格內哨兵真值（§390）⟹ 純 3-Signal、無 None 分支、無 NoisePosition。
"""
from __future__ import annotations

import pytest

from the_door.core.diff.provenance_membrane import (
    PROVENANCE_CONTRASTS,
    derive_provenance,
    provenance_element,
    provenance_element_for,
    provenance_signal,
)
from the_door.models.snapshot import SNAPSHOT_CONTRACT_VERSION


class TestDeriveProvenance:
    """P3：==→current／present且!=→legacy／None→unknown。"""

    def test_current_contract_version_is_current(self):
        assert derive_provenance(SNAPSHOT_CONTRACT_VERSION) == "current"

    def test_different_contract_version_is_legacy(self):
        # 構造一個保證 != 當前的戳
        other = SNAPSHOT_CONTRACT_VERSION + "-old"
        assert derive_provenance(other) == "legacy"
        assert derive_provenance("0") == "legacy"

    def test_none_is_unknown(self):
        assert derive_provenance(None) == "unknown"


class TestProvenanceContrasts:
    def test_contrasts_are_the_closed_three_set(self):
        assert PROVENANCE_CONTRASTS == ("current", "legacy", "unknown")

    def test_derive_always_lands_in_contrasts(self):
        for v in (SNAPSHOT_CONTRACT_VERSION, "0", None):
            assert derive_provenance(v) in PROVENANCE_CONTRASTS


class TestProvenanceMembrane:
    """P4：每值 → 格內 SignalPosition；unknown 是真值（signal 非 noise）。"""

    def test_signal_carries_full_contrast_set_and_gloss(self):
        sig = provenance_signal("current")
        assert sig.contrasts == PROVENANCE_CONTRASTS
        assert sig.gloss

    @pytest.mark.parametrize("value", ["current", "legacy", "unknown"])
    def test_element_projects_to_signal(self, value):
        j = provenance_element(value).to_json()
        assert j["value"] == value
        assert j["position"]["kind"] == "signal"
        assert j["position"]["contrasts"] == list(PROVENANCE_CONTRASTS)
        assert j["position"]["gloss"]

    def test_unknown_is_in_grid_signal_not_noise(self):
        """P4 關鍵：unknown 走 signal（格內真值），不退 NoisePosition。"""
        j = provenance_element("unknown").to_json()
        assert j["position"]["kind"] == "signal"

    def test_element_for_none_is_unknown_signal(self):
        j = provenance_element_for(None).to_json()
        assert j["value"] == "unknown"
        assert j["position"]["kind"] == "signal"

    def test_element_for_current_stamp_is_current(self):
        j = provenance_element_for(SNAPSHOT_CONTRACT_VERSION).to_json()
        assert j["value"] == "current"

    def test_bogus_value_raises(self):
        with pytest.raises(KeyError):
            provenance_element("bogus")
