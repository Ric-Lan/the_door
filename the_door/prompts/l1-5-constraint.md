# L1.5 Constraint Prompt — The Door Phase 1-full

## Purpose

You are producing an L1.5 structural overview that groups L1 features into higher-level architectural blocks. This provides a mid-level view between individual features (L1) and module interactions (L2).

## Output Format (⑧ L1.5 Output JSON Schema)

Your output MUST be valid JSON conforming to this structure:

```json
{
  "l1_5": {
    "blocks": [
      {
        "block_id": "unique-block-id",
        "label": "Module name + functional description (technical term allowed IF accompanied by functional context)",
        "responsibility": "What this block is responsible for in the system",
        "trigger_mechanism": "Human-readable description of what activates this block",
        "related_features": ["feat-id-1", "feat-id-2"]
      }
    ],
    "block_relations": [
      {
        "from": "block_id",
        "to": "block_id",
        "relation": "Functional description of how these blocks interact",
        "relation_type": "static | inferred",
        "inferred_reason": "Required when relation_type is inferred"
      }
    ],
    "infrastructure_block": {
      "label": "System Infrastructure",
      "components": ["node_id_1", "node_id_2"]
    }
  }
}
```

## Required Fields Per Block

Every block MUST include ALL of these fields:
- `block_id`: unique identifier (e.g., "blk-auth", "blk-payments")
- `label`: module name + functional description (see Language Rules below)
- `responsibility`: what this block handles in the system
- `trigger_mechanism`: human-readable trigger description
- `related_features`: list of L1 feature_ids that belong to this block

## Block Relations

- `relation_type: "static"`: The relationship is directly visible in AST edges between the blocks' source nodes. Requires an AST edge path to exist.
- `relation_type: "inferred"`: The relationship is reasoned from context. MUST include a non-empty `inferred_reason` field explaining the reasoning.

## Infrastructure Block

- Exactly ONE `infrastructure_block` in the output
- Its `components` array must contain every node_id from L1's `infrastructure_nodes`
- Label should be "System Infrastructure" or similar functional description
- Do NOT create separate blocks for infrastructure — consolidate into one

## Language Rules (Relaxed for L1.5)

L1.5 labels follow a **relaxed** language rule compared to L1:
- A bare technical term alone (e.g., "Controller", "Service") is **PROHIBITED**
- A technical term WITH functional description (e.g., "Authentication Controller handling user identity verification") is **ALLOWED**
- The label must contain at least 4 words to qualify as having functional context
- Descriptions and responsibilities follow the same rule

## Validation

Your L1.5 output will be validated:
1. Schema conformance (all required fields, correct types)
2. Cross-reference integrity (all block_ids in relations exist in blocks, all feature_ids in related_features exist in L1 output)
3. Language check (relaxed rules as described above)
4. Relation check (static requires edge path, inferred requires reason)
