English | [繁體中文](README.zh-TW.md)

# The Door

Translates code structure and changes into functional-language diagrams — so non-technical stakeholders can verify what was actually built.

Vibe coding as the technical backbone. Requirements drive the entire development flow.

> Translation direction: technical language → functional language. Diagrams are not decoration — they are the verification interface.

---

## What Is This

The Door is a CLI tool + MCP Server + local UI. It reads your codebase and uses an LLM to translate it into "functional language" — plain descriptions of what the system does, what changed, and whether anything looks wrong.

**Who it's for:** PMs, project managers, release managers, QA, clients — anyone who needs to confirm that deliverables match commitments, without reading code.

**Core capabilities:**

| Capability | Description |
|---|---|
| Feature translation | Code → functional-language diagram (interactive + Mermaid fallback) + natural-language narrative |
| Version diff | What changed between two versions, risks surfaced first |
| Scope verification | PM defines sprint scope → auto-compare → flag out-of-scope items |
| Vulnerability scan | Known CVEs in dependencies, integrated into the feature diagram |
| Feature evolution | Multi-version timeline tracking when features appeared and how often they changed |
| Doubt tracking | Anomaly detected → flagged → assigned → resolved (with escalation on timeout) |
| Local UI | Browser workbench, interactive diagrams, three-layer navigation (L1 → L2 → L3) |

---

## I. Quick Start

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python ≥ 3.10** | Required. [python.org/downloads](https://www.python.org/downloads/) |
| **pip** | Comes with Python |
| **osv-scanner** _(optional)_ | Required for `the-door scan`. Install via `go install golang.org/x/vuln/cmd/osv-scanner@latest` or download from [google.github.io/osv-scanner](https://google.github.io/osv-scanner/) |
| **Ollama** _(optional)_ | Required if using local LLM mode. Install from [ollama.com](https://ollama.com) |

> **MCP mode only** (no API key): also requires a compatible AI platform such as Claude Code or Kiro IDE.

---

### No API Key? Use an AI Platform Directly

If you use **Claude Code**, **Kiro IDE**, or any other MCP-compatible AI platform, you don't need your own API key — the platform's AI handles the analysis, and The Door just reads the code and produces the diagrams.

**Steps:**

1. Install the package:
   ```bash
   pip install the-door
   ```

2. Add The Door to your AI platform's MCP configuration:
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

3. Talk to the AI directly, for example:
   > "Analyze `./my-project` and give me the L1 feature diagram."
   > "Compare `./old` and `./new` — what changed?"

The AI calls The Door's tools via MCP and returns results directly in the conversation.
For the exact multi-tool sequence the AI follows, see [`CLAUDE.md`](CLAUDE.md).

---

### Have an API Key? Drive the CLI Yourself

### Install (one-time)

```bash
pip install the-door
the-door config init    # Create config file and fill in your LLM API key
```

> Config file is at `~/.the-door/config.toml`. Supports OpenAI / Anthropic / Ollama (see [Detailed Reference → LLM Configuration](#llm-configuration)).

---

### Project Path

`<path>` is the directory of the project you want to analyze. Analysis artifacts are saved automatically under `.the-door/` inside that directory — your source code is not modified.

> **Path restrictions for diff analysis** vary by usage mode (UI vs CLI vs MCP). See [Detailed Reference → Diff Path Rules](#diff-path-rules).

---

### Workflow: Analyze → Snapshot → Diff

**Diff analysis requires snapshots from two points in time.** Recommended flow:

```
First run (establish baseline):  the-door analyze ./my-project
                                  ↓ snapshot created automatically (.the-door/snapshots/)

Development continues…

Second run (after new changes):  the-door analyze ./my-project
                                  ↓ new snapshot created automatically

Compare the two snapshots:       the-door diff ./my-project --baseline <label or git tag>
```

> `the-door analyze` creates a snapshot automatically every time — **no need to run** `snapshot create` manually.  
> To compare two separate directories, use `the-door update` directly — it analyzes both sides and diffs them in one step.

---

### L1 Feature Overview

**One-command L1 analysis** — reads the project, outputs a full feature diagram and natural-language description:

```bash
the-door analyze ./my-project
```

**One-command L1 diff** — shows what changed between two versions, risks first:

```bash
# Option 1: compare two directories directly
the-door update <old-path> <new-path>

# Option 2: compare against a snapshot (requires two prior analyze runs)
the-door diff <path> --baseline v1.0
```

> Path restrictions vary by usage mode. See [Detailed Reference → Diff Path Rules](#diff-path-rules).

---

### L2 Module Detail

**One-command L2 analysis** — open the browser workbench to explore module-level diagrams (requires L1 analysis first):

```bash
the-door ui ./my-project
```

> Once open, click any feature node in the left panel, then click "Generate L2" in the right panel to expand the module diagram.

**One-command L2 diff** — run a diff and immediately view L2-level changes in the UI:

```bash
the-door update <old-path> <new-path> && the-door ui <new-path>
```

> In diff mode, nodes are color-coded for added / modified / deleted. Click any node to see Before/After details.

---

## II. Detailed Reference

### LLM Configuration

`the-door config init` creates a config file at `~/.the-door/config.toml`. Three providers are supported:

```toml
# OpenAI (default)
[provider]
default = "openai"
[provider.openai]
api_key = "sk-..."
model = "gpt-4o"

# or Anthropic
[provider]
default = "anthropic"
[provider.anthropic]
api_key = "..."
model = "claude-sonnet-4-20250514"

# or Ollama (local model, free)
[provider]
default = "ollama"
[provider.ollama]
url = "http://localhost:11434"
model = "qwen3:8b"
```

Environment variables `THE_DOOR_OPENAI_KEY`, `THE_DOOR_ANTHROPIC_KEY`, `THE_DOOR_OLLAMA_URL` take precedence over the config file.

### Analysis & Rendering

```bash
the-door analyze <path>                    # Full analysis (AST + LLM + vulnerability scan + auto-snapshot)
the-door analyze <path> --provider ollama  # Specify provider
the-door render <path>                     # Output Mermaid feature diagram
the-door estimate <path>                   # Estimate LLM call cost
```

### Local UI Workbench

```bash
the-door ui <path>                         # Start local UI server, auto-open browser
the-door ui <path> --port 9000             # Custom port (default: 8765)
the-door ui <path> --no-browser            # Don't auto-open browser
```

Opens a three-panel workbench at `http://127.0.0.1:8765`:

- **Left**: Feature list / change list (risk-prioritized)
- **Center**: Interactive diagram (Cytoscape.js — click, zoom, drag)
- **Right**: Detail panel (Before/After, data source, confidence markers)

Three-layer navigation: L1 feature overview → L2 module diagram → L3 source node graph. Diff mode shows color-coded change nodes.

### Diff Path Rules

Diff analysis takes two paths (`old_path` / `new_path`), but the constraints differ by usage mode:

| Usage mode | Absolute path required | Must be under the same root |
|---|---|---|
| **UI (browser workbench)** | Yes | **Yes** — both paths must be subdirectories of the project root passed to `the-door ui` |
| **CLI** (`the-door update`) | No, relative paths are resolved automatically | No — any two directories on the system |
| **MCP tool** | No | No — any two directories on the system |

**UI directory structure example:**

```
C:\projects\my-app\          ← root passed to the-door ui
├── v1\                      ← old path (must be inside root)
└── v2\                      ← new path (must be inside root)
```

**CLI / MCP example (no such restriction):**

```bash
# Completely separate directories work fine
the-door update C:\projects\old-app C:\projects\new-app
```

### Version Diff

```bash
# Compare two directories (full pipeline: analyze → diff → report)
the-door update <old-path> <new-path>
the-door update <old> <new> --scope sprint-12   # With scope verification
the-door update <old> <new> --json               # JSON output
the-door update <old> <new> --render             # Mermaid diagram
the-door update <old> <new> -o report.md         # Write to file

# Compare against a snapshot
the-door diff <path> --baseline <ref>            # ref = git tag / SHA / date / label
```

### Snapshot Management

```bash
the-door snapshot create <path> --label "v2.1"
the-door snapshot list <path>
the-door snapshot prune <path>              # Remove old snapshots
the-door snapshot prune <path> --dry-run    # Preview before pruning
```

### Scope Verification

```bash
the-door scope create sprint-12             # Define a scope
the-door scope verify <path> --scope sprint-12
the-door scope list
```

### Doubt Tracking

```bash
the-door doubt list
the-door doubt assign <id> <assignee>
the-door doubt resolve <id> --as explained --reason "..."
the-door doubt escalate <id> --reason "..."
```

### Vulnerability Scan

```bash
the-door scan <path>
the-door scan <path> --offline              # Offline mode
```

### Feature Evolution

```bash
the-door timeline <path>
the-door timeline <path> --render           # Mermaid Gantt diagram
the-door timeline <path> --feature <id>     # Single feature history
```

### MCP Server

```bash
the-door mcp-serve                          # Start MCP Server (18 tools)
```

Works with all MCP-compatible AI tools (Claude Desktop, Cursor, etc.).

## Architecture

```
Code → AST extraction (tree-sitter, 305+ languages)
     → Topology analysis (dependency ordering, fully local)
     → LLM translation (feature identification + functional-language description)
     → Output validation (schema + semantic checks)
     → Mermaid diagram + JSON report
     → Local UI (interactive diagram workbench)
```

- **LLM-Centric:** Feature identification and translation are handled by the LLM; the system constrains its inputs and outputs
- **AI-Medium-Agnostic:** CLI + MCP Server dual core — any AI medium that can read local files can drive it
- **Local-first:** All analysis, storage, and rendering happen locally except for the LLM call itself — no cloud account needed
- **Trust architecture:** What the LLM doesn't know is marked as unknown; hallucination is prohibited; confidence markers are visible

## Local UI API

`the-door ui` exposes 14 local API endpoints (bound to `127.0.0.1` only):

| Method | Path | Description |
|---|---|---|
| GET | `/api/project` | Project path and available data status |
| GET | `/api/snapshots` | Version snapshot list |
| GET | `/api/report/latest` | Latest diff report |
| POST | `/api/update` | Trigger diff pipeline |
| GET | `/api/update/status/<job_id>` | Poll pipeline progress |
| GET | `/api/doubts` | Doubt list |
| GET | `/api/timeline` | Timeline analysis results |
| GET | `/api/l1?version_id=<id>` | L1 feature diagram ViewModel (optional version) |
| GET | `/api/diff?baseline=<id>&current=<id>` | Diff two snapshots by version ID |
| GET | `/api/l2/<feature_id>` | L2 module diagram ViewModel |
| POST | `/api/l2/<feature_id>/generate` | Trigger L2 LLM generation |
| GET | `/api/structure` | AST structure data |
| GET | `/api/layer-explanation/<fid>/<layer>` | Layer explanation cache |
| POST | `/api/layer-explanation/<fid>/<layer>/generate` | Trigger layer explanation LLM generation |

## Tech Stack

**Runtime requirement:** Python ≥ 3.10. All Python dependencies below are installed automatically by `pip install the-door`.

| Component | Purpose | License |
|---|---|---|
| tree-sitter-language-pack | AST extraction (305+ languages) | MIT |
| networkx | Topology analysis | BSD-3 |
| jsonschema | Output validation (Draft 2020-12) | MIT |
| mcp | MCP Server SDK | Apache 2.0 |
| click | CLI framework | BSD-3 |
| httpx | LLM API calls | BSD-3 |
| pathspec | `.gitignore`-style file filtering | MPL-2.0 |
| tomli | TOML config parsing (Python < 3.11 only) | MIT |
| Cytoscape.js | Interactive diagrams (locally bundled, no CDN) | MIT |
| osv-scanner | Vulnerability scanning — **external binary, install separately** (see Prerequisites) | Apache 2.0 |

## Project Data

Analysis artifacts are stored in `.the-door/` inside the target project:

```
.the-door/
├── snapshots/                    # Version snapshots (JSON)
├── fingerprints/                 # File fingerprints (for smart skipping)
├── doubts/                       # Doubt records
├── l2-outputs/                   # L2 module analysis cache
│   └── <feature_id>.json
├── layer-explanations/           # Layer explanation cache
│   └── <feature_id>/
│       └── <layer>.json
├── structure.json                # AST structure data (produced by the-door extract)
├── scope-config.json             # Scope verification config
├── retention-config.json         # Snapshot retention policy
└── update-report-<timestamp>.json # Diff report
```

Add `.the-door/` to your `.gitignore`.

## Development

```bash
git clone <repo>
cd the_door
pip install -e ".[dev]"
python -m pytest tests/ -x -q
```

526 tests (unit + property-based + integration) using pytest + Hypothesis.

## License

Dual-licensed:

- **Community Edition** — [AGPL-3.0](LICENSE). Free to use and modify. If you distribute or run a modified version as a network service, you must open-source your modifications under the same terms.
- **Commercial Edition** — If you need to use The Door in a proprietary product or closed-source service without the AGPL-3.0 copyleft obligation, contact the maintainer via the issue tracker to obtain a commercial license.

## Documentation

- [User Guide](docs/USER-GUIDE.md) — Full usage documentation
- [Product Spec](the-door-spec-v4.1.md) — Design philosophy and architecture decisions
- [Diagram Language Spec](docs/phase-0a/) — L1/L2 diagram language definition
- [Frontend Spec](docs/frontend-local-version-viewer/spec.md) — Local UI design spec
