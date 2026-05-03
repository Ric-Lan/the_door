# L2 Constraint Prompt — The Door Phase 1-full

## Purpose

You are producing an L2 module interaction analysis that identifies logical modules, their interactions, and structural anomalies in the codebase. This is the deepest analysis level.

## Output Format (⑨ L2 Output JSON Schema)

Your output MUST be valid JSON conforming to this structure:

```json
{
  "l2": {
    "modules": [
      {
        "module_id": "unique-module-id",
        "label": "Human-readable module name",
        "source_nodes": ["node_id_1", "node_id_2"],
        "confidence": "high | medium | low",
        "confidence_reason": "Why you grouped these nodes as a module"
      }
    ],
    "module_interactions": [
      {
        "from": "module_id",
        "to": "module_id",
        "description": "How these modules interact",
        "relation_type": "static | inferred",
        "inferred_reason": "Required when relation_type is inferred"
      }
    ],
    "anomalies": [
      {
        "anomaly_type": "dead_code | logic_dead_end | uncertain_boundary",
        "affected_node_ids": ["node_id_1"],
        "explanation": "Why this is flagged as an anomaly",
        "confidence": "high | medium | low"
      }
    ]
  }
}
```

## Required Fields Per Module

Every module MUST include ALL of these fields:
- `module_id`: unique identifier (e.g., "mod-auth", "mod-payments")
- `label`: human-readable module name
- `source_nodes`: at least one valid node_id from the Structure JSON
- `confidence`: one of `high`, `medium`, `low`
- `confidence_reason`: explanation for why these nodes form a module

## Module Interactions

- `relation_type: "static"`: Direct call/import relationship visible in AST edges
- `relation_type: "inferred"`: Reasoned from shared data, naming patterns, or architectural conventions. MUST include `inferred_reason`.

## Anomaly Detection Rules

Identify structural anomalies in the codebase. Valid anomaly types:

### `dead_code`
Nodes that appear to have no callers and no clear entry point:
- Functions with zero in-degree (no callers) that are NOT entry points
- Functions marked with deprecation decorators
- Test helpers that are never imported

### `logic_dead_end`
Nodes that start processing but have no observable output or side effect:
- Functions that compute values but never return or store them
- Event handlers that don't trigger any downstream action
- Incomplete implementations (empty bodies, pass-only functions)

### `uncertain_boundary`
Areas where module boundaries are unclear:
- Functions that could belong to multiple modules
- Shared utility code used across unrelated features
- Circular dependencies between modules

## Anomaly Constraints

- `affected_node_ids`: MUST reference valid node_ids from the Structure JSON
- `explanation`: MUST explain why this is flagged (not just restate the type)
- `confidence`: How certain you are this is a genuine anomaly
- Do NOT flag nodes as anomalies just because they have low confidence — anomalies are structural issues, not confidence issues

## Validation

Your L2 output will be validated:
1. Schema conformance (all required fields, correct types, valid enum values)
2. Anomaly reference integrity (all affected_node_ids exist in Structure JSON)
3. Module source_nodes must reference valid node_ids
