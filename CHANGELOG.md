# Changelog

All notable changes to The Door are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

---

## [1.0.6] — 2026-05-10

### Added
- `snapshot_write` MCP tool: AI agents can now write their own L1 analysis results
  directly into the snapshot store without requiring an external LLM API key.
  Enables the full MCP agent-mode pipeline: `extract_structure` → analyze → `snapshot_write` → `diff` → UI.
- `CLAUDE.md`: Defines the MCP multi-tool orchestration sequence for AI platforms
  (Claude Code, Kiro IDE, etc.) acting as the analysis LLM.
- `extract_structure` response now includes `analyzed_files` field (list of analyzed file paths).
- `ProjectRegistry`: Auto-registers analyzed projects in `~/.the-door/registry.json`.
- `the-door projects` CLI command: lists all registered projects.
- `project_list` MCP tool: AI can query registered projects via MCP.
- `the-door ui` now supports interactive project picker when called without a path argument.

### Changed
- README MCP Quick Start: Added reference to `CLAUDE.md` for tool orchestration details.

### Fixed
- MCP agent-mode pipeline was previously undocumented, causing AI platforms to fail
  to chain tools correctly when attempting no-API-key analysis.

---

## [1.0.5] — 2026-05-09

### Changed
- License: Switched from AGPL-3.0 + Commons Clause to dual licensing
  (AGPL-3.0 Community Edition + Commercial License on request).
- README: Split into English (`README.md`) and Traditional Chinese (`README.zh-TW.md`)
  with language switcher. Restructured into Quick Start / Detailed Reference sections.
  Added MCP path documentation.

### Fixed
- L2 graph view model now exposes `confidence_reason` field.

---

## [1.0.4] — 2026-05-09

### Fixed
- L2 mindmap boxes now auto-size with CJK-aware text measurement.
- Anomaly nodes show orange border and badge on all L2 nodes when parent has anomalies.
- L2 source count and confidence displayed as pill badges; removed grey dot indicator.
- Richer L1/L2 node content, dynamic SVG width, reduced whitespace padding.
- Mindmap popup layout redesigned: auto-scale SVG, slide-in detail panel, toolbar legend.

### Added
- Info panel and legend in mindmap popup.
- Project name now displays as basename in mindmap popup header.
- Diff type tags on L1 feature list on the main page.

---

## [1.0.3] — 2026-05-09

### Added
- `mindmap-popup.html`: New dedicated popup window with SVG column tree view and
  visual indicators (anomaly, diff type, confidence).
- Mindmap navigation rewritten to use `sessionStorage` + `window.open` for popup mode.

### Removed
- V1 inline mindmap view removed from `index.html`, `styles.css`, `app.js`, and tests.

---

## [1.0.2] — 2026-05-09

### Added
- `renderMindmap`: Full mindmap render pipeline (all 10 unit assertions green).
- `loadMindmapL2`: Progressive L2 data loading with client-side cache.
- `switchToMindmap`: Navigation function with breadcrumb layer support.
- Mindmap View CSS styles.
- Topbar buttons and `mindmap-view` div in `index.html`.

---

## [1.0.1] — 2026-05-09

### Added
- Mindmap unit test harness (TDD scaffold, all tests initially failing).
- `createMindmapL1Node`: Renders L1 feature nodes in mindmap (T1–T3 pass).
- `_renderMindmapL2Section`: Renders L2 sub-feature sections (T4–T7 pass).
- `mindmapL2Cache` state, element refs, and button event listeners wired up.

---

## [1.0.0] — 2026-05-06

### Added
- Phase UI-1: Local Report Viewer — `ViewModelConverter`, static HTML/CSS/JS viewer.
- Phase UI-2: Local API Server — `UIServer` with 7 REST API endpoints, `JobStore`
  for async analysis jobs.
- Phase UI-3: Interactive Graph — Cytoscape.js-based graph with L1/L2/L3 navigation,
  `GraphViewModel_Converter`, `L2Generator`, 6 additional API endpoints.
- Integration tests: 36 end-to-end tests covering all 13 API endpoints.
- Self-analysis: The Door analyzed its own source (541 nodes, 13 features).
- `the-door ui` CLI command to launch the local UI server.
- `__init__.py` version bumped from 0.1.0 to 1.0.0.
- LICENSE copyright year updated to 2025–2026.

---

## Version History Reference

| Version | Release Date | Key Change |
|---------|-------------|-----------|
| 1.0.6 | 2026-05-10 | `snapshot_write` MCP tool + `CLAUDE.md` agent orchestration + ProjectRegistry |
| 1.0.5 | 2026-05-09 | Dual license + bilingual README + `confidence_reason` |
| 1.0.4 | 2026-05-09 | Mindmap popup polish: CJK sizing, anomaly badges, SVG layout |
| 1.0.3 | 2026-05-09 | Mindmap V2 popup window (SVG column tree, sessionStorage navigation) |
| 1.0.2 | 2026-05-09 | Full mindmap render pipeline (renderMindmap, loadMindmapL2, CSS) |
| 1.0.1 | 2026-05-09 | Mindmap TDD scaffold + L1/L2 node builders |
| 1.0.0 | 2026-05-06 | Full release: Phase UI-1/2/3 Interactive Graph + 36 integration tests |
