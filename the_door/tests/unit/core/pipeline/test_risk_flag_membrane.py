"""risk_flag_membrane：詞彙單一來源＋工廠（P3）。

詞彙＝封閉 3-set，對齊 update-report.schema.json risk_flags enum。
absence 守界（spec §0）：未舉旗標＝「未帶此旗標」、非「已驗證 clear」。
"""
import json
from pathlib import Path

import pytest

from the_door.core.pipeline.risk_flag_membrane import (
    RISK_FLAG_VOCABULARY,
    risk_flags_element,
)


def test_vocabulary_is_closed_3_set():
    assert RISK_FLAG_VOCABULARY == ("out_of_scope", "vulnerability", "semantic_drift")


def test_vocabulary_aligns_with_schema_enum():
    """詞彙單一來源對齊 schema risk_flags items enum（防漂移）。"""
    schema_path = (
        Path(__file__).resolve().parents[4] / "schemas" / "update-report.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum = (
        schema["properties"]["l1_changes"]["items"]["properties"]
        ["risk_flags"]["items"]["enum"]
    )
    assert set(enum) == set(RISK_FLAG_VOCABULARY)


def test_element_single_present_flag():
    j = risk_flags_element(["out_of_scope"]).to_json()
    assert j["value"] == ["out_of_scope"]
    assert j["position"]["kind"] == "presence_flag"
    assert j["position"]["vocabulary"] == list(RISK_FLAG_VOCABULARY)
    assert set(j["position"]["glosses"]) == set(RISK_FLAG_VOCABULARY)


def test_element_empty_present_exposes_full_vocabulary():
    """空 present（未舉任何旗）→ value:[]＋vocabulary 全曝（可能性空間）。"""
    j = risk_flags_element([]).to_json()
    assert j["value"] == []
    assert j["position"]["vocabulary"] == list(RISK_FLAG_VOCABULARY)


def test_element_multi_present_preserves_order():
    """多選共現、保序。"""
    j = risk_flags_element(["out_of_scope", "vulnerability"]).to_json()
    assert j["value"] == ["out_of_scope", "vulnerability"]


def test_element_out_of_vocabulary_raises():
    """防呆：present 含詞彙外值 → 子集不變量 ValueError。"""
    with pytest.raises(ValueError, match="vocabulary 外旗標"):
        risk_flags_element(["bogus_flag"])
