"""L2Generator — generate L2Output for a feature using LLM, then persist.

Responsibilities:
- Build prompt from feature_id + StructureJSON
- Call LLMProvider.complete()
- Parse LLM response into L2Output
- Persist to .the-door/l2-outputs/<feature_id>.json
- Load persisted L2Output from disk (staticmethod)

Does NOT manage job state — that is the caller's responsibility.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from the_door.core.llm.provider import LLMProvider
from the_door.models import Anomaly, L2Module, L2Output, ModuleInteraction, StructureJSON


class L2GenerationError(Exception):
    """Raised when L2 generation fails (LLM error or parse error)."""

    pass


class L2Generator:
    """Generate L2Output for a feature using LLM, then persist to disk.

    Responsibilities:
    - Build prompt from feature_id + relevant StructureJSON nodes
    - Call LLMProvider.complete()
    - Parse LLM response into L2Output
    - Persist to .the-door/l2-outputs/<feature_id>.json

    Does NOT manage job state — that is the caller's responsibility.
    """

    def __init__(self, project_root: Path, llm_provider: LLMProvider) -> None:
        self._project_root = project_root
        self._llm_provider = llm_provider

    async def generate(
        self,
        feature_id: str,
        structure_json: StructureJSON,
    ) -> L2Output:
        """Generate L2Output for the given feature.

        Steps:
        1. Build prompt from feature_id + full StructureJSON
        2. Call LLMProvider.complete()
        3. Parse response into L2Output
        4. Persist to .the-door/l2-outputs/<feature_id>.json
        5. Return L2Output

        Raises L2GenerationError on LLM failure or parse failure.
        """
        prompt = self._build_prompt(feature_id, structure_json)

        try:
            raw = await self._llm_provider.complete(prompt)
        except Exception as exc:
            raise L2GenerationError(
                f"LLM call failed for feature '{feature_id}': {exc}"
            ) from exc

        l2_output = self._parse_response(raw)
        self._persist(feature_id, l2_output)
        return l2_output

    def _build_prompt(
        self,
        feature_id: str,
        structure_json: StructureJSON,
    ) -> str:
        """Build LLM prompt for L2 generation.

        Prompt includes feature_id and full StructureJSON (nodes + edges + topology).
        Instructs LLM to identify modules, interactions, and anomalies for the feature.
        Returns prompt string.
        """
        nodes_summary = [
            {"node_id": n.node_id, "name": n.name, "type": n.type, "file": n.file}
            for n in structure_json.nodes
        ]
        edges_summary = [
            {"from_node": e.from_node, "to_node": e.to_node, "type": e.type}
            for e in structure_json.edges
        ]

        structure_data = json.dumps(
            {"nodes": nodes_summary, "edges": edges_summary},
            ensure_ascii=False,
            indent=2,
        )

        return (
            f"You are analysing the codebase structure for feature '{feature_id}'.\n\n"
            "Given the following AST structure JSON, identify the logical modules "
            "that implement this feature, the interactions between those modules, "
            "and any anomalies (dead code, uncertain boundaries, etc.).\n\n"
            "Structure JSON:\n"
            f"{structure_data}\n\n"
            "Respond with a JSON object that has exactly these top-level keys:\n"
            "  - modules: list of {module_id, label, confidence, source_nodes}\n"
            "  - module_interactions: list of {from_module, to_module, description, relation_type}\n"
            "  - anomalies: list of {anomaly_type, affected_node_ids, explanation, confidence}\n\n"
            "confidence values must be 'high', 'medium', or 'low'.\n"
            "relation_type values must be 'static' or 'inferred'.\n"
            "Return only the JSON object, no additional text."
        )

    def _parse_response(self, raw: str) -> L2Output:
        """Parse LLM response JSON into L2Output.

        Raises L2GenerationError if JSON is invalid or required fields are missing.
        """
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove opening fence (```json or ```)
            lines = lines[1:]
            # Remove closing fence
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise L2GenerationError(
                f"LLM response is not valid JSON: {exc}\nRaw response: {raw[:200]}"
            ) from exc

        try:
            modules = [
                L2Module(
                    module_id=m["module_id"],
                    label=m["label"],
                    confidence=m.get("confidence", "medium"),
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
                    confidence=a.get("confidence", "medium"),
                )
                for a in data.get("anomalies", [])
            ]
        except (KeyError, TypeError) as exc:
            raise L2GenerationError(
                f"LLM response missing required fields: {exc}\nData: {data}"
            ) from exc

        return L2Output(
            modules=modules,
            module_interactions=interactions,
            anomalies=anomalies,
        )

    def _persist(self, feature_id: str, l2_output: L2Output) -> None:
        """Persist L2Output to .the-door/l2-outputs/<feature_id>.json."""
        output_dir = self._project_root / ".the-door" / "l2-outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{feature_id}.json"

        data = {
            "modules": [
                {
                    "module_id": m.module_id,
                    "label": m.label,
                    "confidence": m.confidence,
                    "source_nodes": list(m.source_nodes),
                }
                for m in l2_output.modules
            ],
            "module_interactions": [
                {
                    "from_module": i.from_module,
                    "to_module": i.to_module,
                    "description": i.description,
                    "relation_type": i.relation_type,
                }
                for i in l2_output.module_interactions
            ],
            "anomalies": [
                {
                    "anomaly_type": a.anomaly_type,
                    "affected_node_ids": list(a.affected_node_ids),
                    "explanation": a.explanation,
                    "confidence": a.confidence,
                }
                for a in l2_output.anomalies
            ],
        }

        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
                confidence=m.get("confidence", "medium"),
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
                confidence=a.get("confidence", "medium"),
            )
            for a in data.get("anomalies", [])
        ]

        return L2Output(
            modules=modules,
            module_interactions=interactions,
            anomalies=anomalies,
        )
