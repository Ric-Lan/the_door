from dataclasses import dataclass
from the_door.core.guidance.actions import NextAction, to_json_dict as action_to_json


@dataclass(frozen=True)
class Remediation:
    code: str
    message: str
    next_action: NextAction | None = None
    docs_url: str | None = None


REMEDIATION_CATALOGUE: dict[str, str] = {
    "no_persisted_structure_for_baseline": "Baseline 缺少持久化的 AST 結構，無法做增量分析。",
    "baseline_not_found": "找不到對應的 baseline snapshot。",
    "snapshot_not_found": "找不到指定的 snapshot 參考。",
    "no_snapshot_for_baseline": "尚未為這個專案寫入任何 snapshot。",
    "source_nodes_drift": "Snapshot 內 source_node_count 與 source_nodes 列表不一致。",
    "node_id_collision": "AST 抽取階段偵測到同名節點碰撞，已加 #N 後綴消歧。",
    "structure_corrupted": "持久化的 structure 檔損毀，已忽略。",
    "snapshot_corrupted": "Snapshot JSON 檔損毀，已略過。",
    "conflicting_flags": "傳入的旗標互斥。",
    "baseline_project_mismatch": "extract --as-version 的 source-path 與 baseline 的 project root 不一致。",
}


def make_error_envelope(
    code: str,
    message: str,
    remediation: "Remediation | None",
    source: str,
) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "remediation": _remediation_to_json(remediation) if remediation else None,
            "source": source,
        }
    }


def _remediation_to_json(r: Remediation) -> dict:
    return {
        "code": r.code,
        "message": r.message,
        "next_action": action_to_json(r.next_action) if r.next_action else None,
        "docs_url": r.docs_url,
    }
