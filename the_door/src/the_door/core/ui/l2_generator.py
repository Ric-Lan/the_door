"""L2Generator — display-only remnant after T5-V.

L2 generation (LLM-backed) was retired in T5-V (viewer generation退場, 丙案 D1):
the headless viewer cannot host an agent-as-LLM at click time, so click-to-generate
was removed. This class now exists **only** to load persisted L2Output from disk for
the read/display path (GET /api/l2/<feature_id>). The "Generator" name is kept to
avoid churning the `get_l2` call site; renaming is deferred to a display-面 cut.
"""
from __future__ import annotations

import json
from pathlib import Path

from the_door.models import Anomaly, L2Module, L2Output, ModuleInteraction


class L2Generator:
    """Display-only loader for persisted L2Output (generation retired in T5-V)."""

    @staticmethod
    def load(project_root: Path, feature_id: str) -> L2Output | None:
        """Load persisted L2Output from disk. Returns None if not found."""
        output_path = (
            project_root / ".the-door" / "l2-outputs" / f"{feature_id}.json"
        )
        if not output_path.exists():
            return None

        try:
            data = json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        modules = [
            L2Module(
                module_id=m["module_id"],
                label=m["label"],
                confidence=m.get("confidence"),
                source_nodes=list(m.get("source_nodes", [])),
            )
            for m in data.get("modules", [])
        ]

        interactions = [
            ModuleInteraction(
                from_module=i["from_module"],
                to_module=i["to_module"],
                description=i.get("description", ""),
                relation_type=i.get("relation_type", "inferred"),
            )
            for i in data.get("module_interactions", [])
        ]

        anomalies = [
            Anomaly(
                anomaly_type=a["anomaly_type"],
                affected_node_ids=list(a.get("affected_node_ids", [])),
                explanation=a.get("explanation", ""),
                confidence=a.get("confidence"),
            )
            for a in data.get("anomalies", [])
        ]

        return L2Output(
            modules=modules,
            module_interactions=interactions,
            anomalies=anomalies,
        )
