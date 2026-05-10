# The Door — AI Agent Instructions

This file tells MCP-compatible AI agents (Claude Code, Kiro, etc.) how to use
The Door's tools. Read this before calling any tool.

## MCP Server Setup

The Door MCP server exposes a set of tools (including `extract_structure`,
`snapshot_write`, `project_list`, and more). Start it with:

```json
{
  "mcpServers": {
    "the-door": {
      "command": "the-door",
      "args": ["mcp-serve"]
    }
  }
}
```

If running from source (dev environment):

```json
{
  "mcpServers": {
    "the-door": {
      "command": "python",
      "args": ["-m", "the_door", "mcp-serve"],
      "env": { "PYTHONPATH": "<repo>/the_door/src" }
    }
  }
}
```

---

## Two Analysis Modes

### Mode A — External LLM (user has API key)

Use `analyze` or `update`. They call OpenAI/Anthropic internally.

```
analyze(codebase_path="./my-project")
update(old_path="./v1", new_path="./v2")
```

### Mode B — Agent-as-LLM (no external API key needed, YOU are the LLM)

Use this sequence when no external API key is configured. You perform the feature
identification step yourself.

**Single version analysis:**

1. `extract_structure(codebase_path="./my-project")`
   → Returns: `files`, `nodes`, `edges`, `topology`, `analyzed_files`

2. YOU analyze the nodes/edges and produce L1 features.
   Required output format:
   ```json
   {
     "l1_features": [
       {
         "feature_id": "feat-<slug>",
         "label": "Short feature name",
         "description": "Plain-language description of what this feature does.",
         "source_node_count": 5,
         "confidence": "high",
         "source_nodes": ["ClassName.method_name", ...]
       }
     ],
     "relations": [
       { "from_feature": "feat-a", "to_feature": "feat-b", "relation": "depends_on" }
     ]
   }
   ```
   Rules: `feature_id` must start with `feat-`. `confidence` must be `high`, `medium`, or `low`.
   Group nodes by functional purpose, not file or class structure.

3. `snapshot_write(codebase_path="./my-project", l1_features=[...], relations=[...], label="v1.0.0")`
   → Returns: `version_id`, `label`

**Version diff analysis (comparing two versions):**

Run steps 1–3 for BOTH versions, then:

4. `diff(codebase_path="./new-project", baseline="v1.0.0", format="mermaid")`
   → Returns: mermaid diagram of what changed

   > **Cross-directory note:** `diff` reads snapshots from `<codebase_path>/.the-door/snapshots/`.
   > Both versions' snapshots must be in the **same** directory. If you analyzed them in separate
   > directories, copy the old version's snapshot file into the new version's snapshot directory:
   > ```
   > cp ./old-project/.the-door/snapshots/<old-id>.json ./new-project/.the-door/snapshots/
   > ```
   > Then run `diff` against `./new-project`.

5. Start UI: `the-door ui ./new-project`
   → Opens browser workbench with diff visualization

**L2 module detail (after L1 analysis):**

Use `the-door ui ./my-project` and click "Generate L2" on any feature node.
L2 generation in the UI uses its own LLM call — it requires an API key configured
in `~/.the-door/config.toml`.

---

## Snapshot Reference Format

When calling `diff --baseline`, the `baseline` argument can be:
- A git tag: `"v1.0.0"`
- A snapshot label: `"my-label"`
- A date: `"2026-05-06"` (finds most recent snapshot on or before that date)
- A commit SHA (≥7 chars): `"8de9b18"`

---

## Key Constraints

- `snapshot_write` saves under `<codebase_path>/.the-door/snapshots/` — both old and new
  versions must use different `codebase_path` values, OR use different `label`/`git_tags`
  to distinguish them.
- The UI (`the-door ui <path>`) reads snapshots from `<path>/.the-door/`. Pass the **new**
  version path to see the diff in UI.
- `analyzed_files` in `extract_structure` response lists all files scanned. Pass this to
  `snapshot_write` as the `analyzed_files` argument if you want file coverage tracking.
