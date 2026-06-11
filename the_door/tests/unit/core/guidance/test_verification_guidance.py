import json
from the_door.core.guidance.verification_guidance import verification_guidance
from the_door.mcp.server import REGISTERED_TOOL_NAMES


def test_guidance_is_json_serializable_and_stable():
    g = verification_guidance()
    json.dumps(g)                      # JSON-safe
    assert g == verification_guidance()  # 決定性、無狀態


def test_guidance_covers_both_causes_of_trigger_state():
    # 觸發處境兩成因須分清且各帶「相異」動作（未評估→補做評估；中/低→補強證據）
    causes = {c["cause"]: c for c in verification_guidance()["causes"]}
    assert set(causes) == {"unassessed", "low_or_medium"}
    assert "補做" in causes["unassessed"]["action"]         # 補做評估（鑑別 token）
    assert "補強" in causes["low_or_medium"]["action"]       # 補強證據（鑑別 token）
    assert causes["unassessed"]["action"] != causes["low_or_medium"]["action"]  # 兩成因不混


def test_guidance_evidence_tools_are_registered():
    # invariant：指向的工具名必為已註冊工具（不指向不存在工具）
    tools = {t["tool"] for t in verification_guidance()["evidence_tools"]}
    assert tools                                   # 非空
    assert tools <= REGISTERED_TOOL_NAMES
    assert "extract_structure" in tools            # 第一版證據源


def test_guidance_tone_is_suggestive_not_imperative():
    blob = json.dumps(verification_guidance(), ensure_ascii=False)
    assert "可選" in blob and "非強制" in blob     # 建議語氣的有鑑別力 token
    assert "必須" not in blob and "務必" not in blob
