# L1 Constraint Prompt — The Door Phase 1-min

## Purpose

You are analyzing a codebase's AST structure to produce a functional overview (L1) readable by non-technical stakeholders. Your output must follow strict constraints.

## Input Format

You will receive Structure JSON containing:
- `files`: source files in the codebase
- `nodes`: functions, classes, and methods with their attributes
- `edges`: relationships (calls, imports, extends, implements)
- `topology`: pre-computed reading priority with batch assignments

## Reading Strategy (① Input Trimming)

- Process nodes in batches according to `topology.batch_assignment`
- Start with batch 1 (entry points — these are the most important business nodes)
- Maximum 5 batches per analysis session
- For L1 analysis, focus on node-level information: names, decorators, docstrings, edges
- Do NOT require function body details for L1 analysis
- If batch limit is reached with unprocessed nodes, mark them in `unclassified_nodes` with the understanding that they were not analyzed due to batch limits

## Output Format (② L1 Output JSON Schema)

Your output MUST be valid JSON conforming to this structure:

```json
{
  "l1": {
    "summary": "One paragraph describing what this system does (functional language only)",
    "features": [
      {
        "feature_id": "unique-id",
        "label": "Short functional label (NO technical terms)",
        "description": "Functional description of what this feature does for users",
        "trigger": "user_action | scheduled | auto_triggered",
        "trigger_description": "Human-readable description of when/how this is triggered",
        "confidence": "high | medium | low",
        "confidence_reason": "Why you assigned this confidence level",
        "source_nodes": ["node_id_1", "node_id_2"],
        "needs_source_review": false,
        "review_reason": null
      }
    ],
    "feature_relations": [
      {
        "from": "feature_id",
        "to": "feature_id",
        "relation": "Functional description of the causal relationship",
        "relation_type": "static | inferred",
        "inferred_reason": "Required when relation_type is inferred — explain your reasoning"
      }
    ],
    "unclassified_nodes": ["node_ids you cannot classify"],
    "infrastructure_nodes": ["node_ids that are infrastructure/utility, not business features"]
  }
}
```

## Required Fields Per Feature

Every feature MUST include ALL of these fields:
- `feature_id`: unique identifier (e.g., "feat-auth", "feat-billing")
- `label`: short name in functional language
- `description`: what this feature does for users
- `trigger`: one of `user_action`, `scheduled`, `auto_triggered`
- `trigger_description`: human-readable trigger explanation
- `confidence`: one of `high`, `medium`, `low`
- `confidence_reason`: explanation for confidence level
- `source_nodes`: at least one valid node_id from the Structure JSON

## Confidence Self-Assessment (④)

For EVERY feature node, you MUST:
1. Assign confidence: `high`, `medium`, or `low`
2. Provide a specific `confidence_reason`

Rules:
- `high`: You are certain about the feature's purpose based on clear evidence (descriptive names, docstrings, obvious patterns)
- `medium`: You have reasonable confidence but some ambiguity exists
- `low`: You are uncertain — limited information available

**PROHIBITION**: Do NOT use vague language to mask uncertainty in `high` confidence nodes. If you're not sure, mark it `medium` or `low`.

## Unclassified Nodes (⑤)

You MUST list ALL nodes you cannot assign to any feature in `unclassified_nodes`.

Rules:
- Do NOT force classification on nodes where functional purpose cannot be determined
- Do NOT silently drop nodes — every node must appear in either `source_nodes`, `unclassified_nodes`, or `infrastructure_nodes`
- Separately list infrastructure/utility nodes in `infrastructure_nodes`

## Anchor Point Constraint (⑥)

Every feature MUST reference at least one valid `node_id` in its `source_nodes` field.

Rules:
- Do NOT describe features that have no corresponding nodes in the Structure JSON
- Do NOT invent node_ids that don't exist in the input
- Static `feature_relations` must correspond to edges that exist in the Structure JSON
- Inferred `feature_relations` must include a non-empty `inferred_reason`

## Relation Types

- `static`: The relationship is directly visible in the AST edges (calls, imports, extends)
- `inferred`: The relationship is not directly in the AST but you can reason about it (e.g., event-driven, IoC injection, shared state). MUST include `inferred_reason`.


---

# Phase 1-full Extensions (Constraints ⑦–⑬)

## Infrastructure Consolidation (⑦)

When analyzing nodes, identify infrastructure/utility nodes that do NOT represent business features:

- Configuration loaders, logger setup, database connection pools
- Generic utility functions (string helpers, date formatters)
- Framework boilerplate (middleware registration, route setup)

Rules:
- Place all infrastructure node_ids in the `infrastructure_nodes` array
- Do NOT create features for infrastructure nodes
- Infrastructure nodes will be consolidated into a single `infrastructure_block` in L1.5 output
- Every infrastructure node must still appear in the coverage (via `infrastructure_nodes`)

## Output Validation Rules (⑩)

Your output will be validated against 5 checks. Ensure compliance:

1. **Schema Check**: Output must conform exactly to the L1 JSON schema (all required fields present, correct types)
2. **Coverage Check**: Every node_id from the Structure JSON must appear in exactly one of: `source_nodes` of a feature, `unclassified_nodes`, or `infrastructure_nodes`
3. **Language Check**: Labels and descriptions must NOT contain prohibited technical terms (Service, Handler, Controller, Middleware, Endpoint, Router, Provider, Factory, Repository, DAO, ORM, SDK, API, etc.)
4. **Anchor Check**: Every node_id in `source_nodes` must exist in the Structure JSON. Do NOT hallucinate node_ids.
5. **Relation Check**: Static relations must have a corresponding AST edge path. Inferred relations must have a non-empty `inferred_reason`.

## Source Code Review Trigger Conditions (⑪)

Mark a feature with `needs_source_review: true` when ANY of these conditions apply:

1. **Generic names**: The source node has a generic/ambiguous name (e.g., `process`, `handle`, `run`, `execute`, `do_something`)
2. **Unrecognized decorators**: The source node has decorators you cannot interpret from name alone
3. **Incomplete call relationships**: The node has outgoing calls to nodes not in the current batch, making its full purpose unclear
4. **Low confidence**: When you assign `confidence: "low"`, always set `needs_source_review: true`

When marking for review, provide a specific `review_reason` explaining what additional information would help.

## Anti-Hallucination (⑫)

**STRICT PROHIBITIONS:**

1. Do NOT describe features that have no corresponding nodes in the Structure JSON
2. Do NOT create `static` relations between features unless an AST edge path exists between their source_nodes
3. Do NOT invent capabilities not evidenced by the AST structure
4. Every `inferred` relation MUST include a non-empty `inferred_reason` explaining the reasoning
5. If you cannot determine a node's purpose, place it in `unclassified_nodes` — do NOT guess

**Evidence requirement**: Every claim in your output must be traceable to specific nodes, edges, or patterns in the Structure JSON.

## Anti-Over-Interpretation (⑬)

**PROPORTIONALITY RULES:**

1. **Description length proportional to evidence**: If a node has only a name and no docstring/comments, keep the description brief (1 sentence). Rich metadata (docstrings, multiple edges, clear patterns) allows longer descriptions.

2. **High-confidence language rules**:
   - For `high` confidence: Use definitive language ("This feature handles...", "Manages...")
   - Do NOT use speculative language ("might", "possibly", "seems to", "appears to") for high-confidence features
   - If you need speculative language, the confidence should be `medium` or `low`

3. **Sparse information handling**:
   - When a node has minimal metadata (no docstring, generic name, few edges): assign `low` or `medium` confidence
   - Keep description to one factual sentence
   - Mark for source review

4. **Do NOT extrapolate**: If the AST shows a function called `process_payment`, you may describe it as "Processes payment transactions" but do NOT elaborate on specific payment methods, error handling, or integration details unless evidenced in the AST.
