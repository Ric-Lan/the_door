"""S3 RelayedVerdict：轉述外部裁決 + V1/V2 型驅動守衛。"""
import pytest

from the_door.core.membrane import MembraneElement, RelayedVerdict


def test_evidence_required_nonempty():
    with pytest.raises(ValueError, match="evidence"):
        RelayedVerdict(authority="osv-scanner", evidence="")        # V1


def test_construct_with_vector_evidence_score_none():
    rv = RelayedVerdict(authority="osv-scanner", evidence="CVSS:3.1/AV:N/AC:L")
    assert rv.score is None and rv.evidence.startswith("CVSS")


def test_construct_with_numeric_score():
    rv = RelayedVerdict(authority="osv-scanner", evidence="7.5", score=7.5)
    assert rv.score == 7.5


def test_score_range_guard():
    with pytest.raises(ValueError, match="\\[0,10\\]"):
        RelayedVerdict(authority="a", evidence="x", score=10.1)       # V2
    with pytest.raises(ValueError, match="\\[0,10\\]"):
        RelayedVerdict(authority="a", evidence="x", score=-0.1)


def test_to_json_relayed_verdict_shape():
    el = MembraneElement(
        payload={"cve_id": "CVE-1", "package": "p"},
        position=RelayedVerdict(authority="osv-scanner", evidence="CVSS:3.1/x", score=9.8),
    )
    j = el.to_json()
    assert j["position"] == {
        "kind": "relayed_verdict", "authority": "osv-scanner",
        "evidence": "CVSS:3.1/x", "score": 9.8,
    }
    assert j["value"] == {"cve_id": "CVE-1", "package": "p"}
